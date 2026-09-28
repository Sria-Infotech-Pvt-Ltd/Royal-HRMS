"""
Stage 2 of the two-stage Hire flow — "Hire employee" on the Review step.
Creates the real User (using the employee number already reserved on the
HireAction) and runs the same follow-on steps EmployeeListCreateView.post
already runs today for a normal hire: position assignment, manager
auto-assignment, leave-balance allocation, weekly-off assignment, welcome
email — plus, new to this flow, an EmployeeSalaryConfig and the first
EmployeeTaxDeclaration row if the wizard collected CTC/tax-regime data.
"""
import logging
import re
import secrets
import string
from collections import defaultdict

from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from core.permissions import has_perm as _has_perm
from core.responses import error, success, get_client_ip
from apps.accounts.models import AuditLog, EmployeeDocument, HireAction, HireActionDocument, Role, User
from apps.accounts.services_placement import assign_position
from apps.accounts.views_hire import _hire_action_dict, _DENIED

logger = logging.getLogger(__name__)

_PAN_RE = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
_IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')


def _missing_hire_requirements(action, draft):
    """Everything the wizard's own sidebar badges advertise as required,
    re-checked here so "Hire employee" can't succeed just because HR jumped
    straight to Review without ever visiting the steps that enforce these
    client-side — free-jump navigation between steps means those per-step
    checks are opt-in, not a real gate, so this is the one that actually is.
    Returns a list of human-readable missing-item descriptions, empty if
    nothing is missing."""
    missing = []

    # Personal identity — the 7 fields STEPS[0].required already advertises.
    if not (draft.get('first_name') or '').strip():
        missing.append('First name')
    if not (draft.get('last_name') or '').strip():
        missing.append('Last name')
    if not draft.get('date_of_birth'):
        missing.append('Date of birth')
    if not draft.get('gender'):
        missing.append('Gender')
    if not (draft.get('nationality') or '').strip():
        missing.append('Nationality')
    if not (draft.get('email') or '').strip():
        missing.append('Personal email')
    if not (draft.get('phone') or '').strip():
        missing.append('Mobile number')

    # Statutory & accounts — the 5 fields STEPS[3].required already advertises.
    pan = (draft.get('pan_number') or '').strip().upper()
    if not pan:
        missing.append('PAN')
    elif not _PAN_RE.match(pan):
        missing.append('a valid PAN')
    aadhaar = (draft.get('aadhaar_number') or '').strip()
    if not aadhaar:
        missing.append('Aadhaar')
    elif len(aadhaar) != 12:
        missing.append('a valid 12-digit Aadhaar number')
    if not (draft.get('account_holder_name') or '').strip():
        missing.append('Account holder name')
    if not (draft.get('account_number') or '').strip():
        missing.append('Account number')
    ifsc = (draft.get('ifsc_code') or '').strip().upper()
    if not ifsc:
        missing.append('IFSC code')
    elif not _IFSC_RE.match(ifsc):
        missing.append('a valid IFSC code')

    # Documents — whichever DocumentTypeConfig rows are actually marked
    # required, checked against what's really been uploaded to this action
    # (not the client's own copy of which types are required, which can
    # drift from this table — see DocumentTypeConfig itself).
    from apps.accounts.models import DocumentTypeConfig
    uploaded_types = set(action.documents.values_list('document_type', flat=True))
    for type_key, label in DocumentTypeConfig.objects.filter(required=True).values_list('type_key', 'label'):
        if type_key not in uploaded_types:
            missing.append(label)

    # Nominee shares — a scheme's shares can never validly exceed 100%,
    # regardless of whether Family & nomination (an otherwise optional step)
    # was even visited.
    totals = defaultdict(float)
    for entry in draft.get('nominee_entries') or []:
        scheme = entry.get('scheme') or 'epf_eps'
        try:
            totals[scheme] += float(entry.get('share_percentage') or 0)
        except (TypeError, ValueError):
            pass
    for scheme, total in totals.items():
        if total > 100:
            missing.append(f'nominee shares for {scheme} exceed 100% ({total:g}%) — adjust before hiring')

    # Annual CTC is optional at hire time (HR can set it later from the
    # employee's own Salary tab), but if one was entered it must be a real
    # positive amount — the normal Salary Setup screen already rejects
    # zero/negative via EmployeeSalaryConfigSerializer.validate_annual_ctc;
    # this wizard writes the model directly, bypassing that serializer, so
    # the same rule is re-checked here.
    annual_ctc = draft.get('annual_ctc')
    if annual_ctc not in (None, ''):
        try:
            if float(annual_ctc) <= 0:
                missing.append('a positive Annual fixed CTC (or leave it blank)')
        except (TypeError, ValueError):
            missing.append('a valid Annual fixed CTC (or leave it blank)')

    return missing


def _assign_salary_and_tax(user, draft, actor):
    """Best-effort — a hire wizard that never reached Basic pay (e.g. a
    minimal draft completed early) still produces a valid employee; CTC/tax
    regime are exactly the kind of thing HR can assign afterwards from the
    employee's own Salary tab, same as today."""
    annual_ctc = draft.get('annual_ctc')
    if annual_ctc and float(annual_ctc) > 0:
        from decimal import Decimal
        from apps.payroll.models import EmployeeSalaryConfig, SalaryStructure
        structure = None
        if draft.get('salary_structure'):
            structure = SalaryStructure.objects.filter(pk=draft['salary_structure']).first()
        EmployeeSalaryConfig.objects.create(
            # draft_data is raw JSON — annual_ctc arrives as a plain str, not
            # a Decimal. Passed through unconverted, the in-memory instance's
            # annual_ctc is still that str the moment post_save fires (before
            # any DB round trip normalizes it), which crashes
            # notifications.signals._on_salary_config_created's ':,.0f'
            # format spec ("Unknown format code 'f' for object of type
            # 'str'") — a 500 on every hire wizard completion that has an
            # Annual CTC set. Cast here, matching the float() check just above.
            employee=user, annual_ctc=Decimal(str(annual_ctc)), salary_structure=structure,
            effective_from=user.date_of_joining, reason=EmployeeSalaryConfig.REASON_OTHER,
            reason_note='Set at hire',
        )

    tax_regime = draft.get('tax_regime')
    if tax_regime:
        from apps.payroll.models import EmployeeTaxDeclaration
        fy_start = user.date_of_joining.year if user.date_of_joining.month >= 4 else user.date_of_joining.year - 1
        EmployeeTaxDeclaration.objects.get_or_create(
            employee=user, financial_year_start=fy_start,
            defaults={'tax_regime': tax_regime, 'status': EmployeeTaxDeclaration.STATUS_DRAFT},
        )


_PROFILE_FIELDS = (
    'salutation', 'middle_name', 'display_name', 'nationality', 'place_of_birth',
    'date_of_birth', 'gender', 'marital_status', 'father_name', 'blood_group',
    'current_address', 'current_address_line2', 'current_village', 'current_district',
    'current_state', 'current_pin_code', 'permanent_address', 'permanent_address_line2',
    'permanent_village', 'permanent_district', 'permanent_state', 'permanent_pin_code',
    'emergency_name', 'emergency_relationship', 'emergency_phone', 'emergency_email',
    'account_number', 'ifsc_code', 'bank_name', 'account_holder_name',
    'pan_number', 'aadhaar_number', 'uan_number', 'passport_number', 'passport_expiry',
    'passport_issue_date', 'passport_place_of_issue', 'passport_country_of_issue',
    'core_skills', 'certifications',
)


def _copy_hire_action_documents(user, action):
    """Every file uploaded during the wizard (PAN/Aadhaar on the Statutory
    step, any item on the Documents step) becomes a real EmployeeDocument now
    that a real employee exists — same storage backend/path pattern as
    action.photo -> user.profile_photo above, just for a whole set of files
    instead of one. The HireActionDocument rows are deleted afterward since
    the real EmployeeDocument row is what matters from this point on; the
    file itself is not re-uploaded, just re-pointed."""
    for doc in action.documents.all():
        new_doc = EmployeeDocument(
            user=user, document_type=doc.document_type,
            file_name=doc.file_name, file_size=doc.file_size,
        )
        new_doc.file.name = doc.file.name
        new_doc.save()
    action.documents.all().delete()


def _apply_wizard_records(user, draft):
    """Everything the wizard's Personal identity/Statutory & accounts/Family &
    nomination/Education & experience/Assets steps collected into draft_data,
    applied to real rows now that a real employee exists to attach them to."""
    from apps.accounts.models import CompanyAsset, EducationRecord, EmployeeProfile, EPFNominee, FamilyMember, WorkExperienceRecord

    profile_fields = {k: draft[k] for k in _PROFILE_FIELDS if draft.get(k)}
    if 'pf_covered' in draft:
        profile_fields['pf_covered'] = str(draft['pf_covered']).lower() == 'true'
    if 'esi_covered' in draft:
        profile_fields['esi_covered'] = str(draft['esi_covered']).lower() == 'true'
    if profile_fields:
        EmployeeProfile.objects.update_or_create(user=user, defaults=profile_fields)

    family_id_map = {}
    for i, entry in enumerate(draft.get('family_entries') or []):
        if not (entry.get('name') or '').strip():
            continue
        member = FamilyMember.objects.create(
            employee=user, name=entry['name'].strip(), relationship=entry.get('relationship') or 'child',
            date_of_birth=entry.get('date_of_birth') or None, gender=entry.get('gender') or '',
            blood_group=entry.get('blood_group') or '', is_dependent=str(entry.get('is_dependent')).lower() == 'true',
            order=i,
        )
        family_id_map[entry.get('id')] = member

    for i, entry in enumerate(draft.get('nominee_entries') or []):
        member = family_id_map.get(entry.get('family_member'))
        if member is None:
            continue
        EPFNominee.objects.create(
            employee=user, family_member=member, scheme=entry.get('scheme') or 'epf_eps',
            share_percentage=entry.get('share_percentage') or 0, order=i,
        )

    for i, entry in enumerate(draft.get('education_entries') or []):
        if not (entry.get('institution') or '').strip():
            continue
        EducationRecord.objects.create(
            employee=user, level=entry.get('level') or 'other', custom_level_label=entry.get('custom_level_label') or '',
            institution=entry['institution'].strip(), specialization=entry.get('specialization') or '',
            percentage=entry.get('percentage') or '', start_date=entry.get('start_date') or None,
            end_date=entry.get('end_date') or None, order=i,
        )

    for i, entry in enumerate(draft.get('experience_entries') or []):
        if not (entry.get('previous_employer') or entry.get('employer_name') or '').strip():
            continue
        WorkExperienceRecord.objects.create(
            employee=user, employer_name=(entry.get('previous_employer') or entry.get('employer_name') or '').strip(),
            designation=entry.get('previous_designation') or entry.get('designation') or '',
            employment_type=entry.get('employment_type') or '', start_date=entry.get('start_date') or None,
            end_date=entry.get('end_date') or None, reason_for_leaving=entry.get('leaving_reason') or entry.get('reason_for_leaving') or '',
            order=i,
        )

    for i, entry in enumerate(draft.get('asset_entries') or []):
        if not entry.get('asset_type'):
            continue
        CompanyAsset.objects.create(
            employee=user, asset_type=entry['asset_type'], tag_number=entry.get('tag_number') or '',
            condition=entry.get('condition') or 'new', order=i,
        )


class HireActionCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        action = HireAction.objects.select_related('position', 'position__org_unit').filter(
            pk=pk, status=HireAction.STATUS_DRAFT,
        ).first()
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)
        if not action.employment_type or not action.reserved_employee_id:
            return error('Set Employment type (step 2) before hiring — the employee number has not been reserved yet.')

        draft = action.draft_data
        first_name = (draft.get('first_name') or '').strip()
        last_name  = (draft.get('last_name')  or '').strip()
        email      = (draft.get('email')      or '').strip().lower()
        role_id    = draft.get('role')
        branch     = (draft.get('branch')     or '').strip()
        if not all([first_name, last_name, email, role_id, branch]):
            return error('First name, last name, email, role and company code are required before hiring.')

        missing = _missing_hire_requirements(action, draft)
        if missing:
            return error(f'Complete these before hiring: {", ".join(missing)}.')
        if User.objects.filter(email=email).exists():
            return error('A user with this email already exists.')
        role = Role.objects.filter(pk=role_id).first()
        if not role:
            return error('Selected role not found.')
        if role.role_permissions.filter(permission__codename='settings.edit').exists():
            return error('System Admin accounts cannot be created through the Hire flow.')

        # Same inline generation EmployeeListCreateView.post already uses —
        # there's no shared helper for this today (duplicated at 3 existing
        # call sites), so this follows the same pattern rather than
        # introducing a new one of its own.
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        full_name = f'{first_name} {last_name}'

        with transaction.atomic():
            user = User.objects.create_user(
                email=email, password=temp_password, full_name=full_name, role=role,
                employee_id=action.reserved_employee_id, department='', designation='',
                branch=branch, phone=(draft.get('phone') or '').strip(),
                employee_type=action.employment_type, date_of_joining=action.effective_from,
                must_change_password=True, onboarding_status=User.ONBOARDING_PENDING,
                work_location=(draft.get('work_location') or '').strip(),
                work_mode=(draft.get('work_mode') or '').strip(),
                probation_period_months=draft.get('probation_period_months') or None,
                notice_period_days=draft.get('notice_period_days') or None,
                pay_group=(draft.get('pay_group') or User.PAY_GROUP_MONTHLY),
                attendance_scheme=(draft.get('attendance_scheme') or User.ATTENDANCE_SCHEME_STANDARD),
                payment_method=(draft.get('payment_method') or User.PAYMENT_METHOD_BANK_TRANSFER),
                leave_plan_id=(draft.get('leave_plan') or None),
            )
            assign_position(user, action.position, effective_from=action.effective_from, created_by=request.user)
            user.refresh_from_db()

            update_fields = []
            # Copies the file uploaded on the Personal Identity step onto the
            # now-real employee — same storage backend/upload path as
            # User.profile_photo itself (see HireAction.photo's own field
            # definition), so this just points the new field at the same
            # already-stored file rather than re-uploading it.
            if action.photo:
                user.profile_photo.name = action.photo.name
                update_fields.append('profile_photo')
            if draft.get('reporting_manager_id'):
                user.reporting_manager = User.objects.filter(pk=draft['reporting_manager_id']).first()
                user.reporting_manager_from_org_chart = False
                update_fields += ['reporting_manager', 'reporting_manager_from_org_chart']
            if draft.get('dotted_line_manager_id'):
                user.dotted_line_manager = User.objects.filter(pk=draft['dotted_line_manager_id']).first()
                update_fields.append('dotted_line_manager')
            if draft.get('hr_id'):
                user.hr = User.objects.filter(pk=draft['hr_id']).first()
                update_fields.append('hr')

            from apps.accounts.views import _auto_assign_managers
            auto_fields = _auto_assign_managers(user)
            auto_fields = list(dict.fromkeys(update_fields + auto_fields))
            if auto_fields:
                user.save(update_fields=[*auto_fields, 'updated_at'])

            from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
            _allocate_leaves_for_employee(user, user.date_of_joining)

            from apps.attendance.models import WeeklyDayPolicy
            from apps.attendance.services_hr import assign_weekly_off
            policy = None
            if draft.get('weekly_off_policy'):
                policy = WeeklyDayPolicy.objects.filter(pk=draft['weekly_off_policy'], is_active=True).first()
            policy = policy or WeeklyDayPolicy.objects.filter(is_default=True, is_active=True).first()
            if policy is not None:
                assign_weekly_off(action.reserved_employee_id, policy, action.effective_from, actor=request.user)

            _assign_salary_and_tax(user, draft, request.user)
            _apply_wizard_records(user, draft)
            _copy_hire_action_documents(user, action)

            action.status = HireAction.STATUS_COMPLETED
            action.created_employee = user
            action.save(update_fields=['status', 'created_employee', 'updated_at'])

            AuditLog.objects.create(
                user=request.user, action='employee_created', module='accounts',
                object_id=str(user.id),
                changes={
                    'name': full_name, 'email': email, 'role': role.name,
                    'employee_id': action.reserved_employee_id, 'via': 'hire_action',
                },
                branch=user.branch, ip_address=get_client_ip(request),
            )

        try:
            from apps.accounts.utils import (
                _get_smtp_connection, _build_message, _company_email_wrapper,
                _get_company_branding,
            )

            company_name, logo_url, website, address = _get_company_branding()
            company_name = company_name or 'Aira HRMS'
            body = (
                f'<p>Hi <strong>{full_name}</strong>,</p>'
                f'<p>Your {company_name} account has been created.'
                f' Use the credentials below to log in:</p>'
                f'<p>'
                f'<strong>Employee ID:</strong> {action.reserved_employee_id}<br>'
                f'<strong>Login Email:</strong> {email}<br>'
                f'<strong>Temporary Password:</strong> {temp_password}'
                f'</p>'
                f'<p>You will be asked to change your password on first login.</p>'
                f'<p>— HR Team</p>'
            )
            html_body = _company_email_wrapper(body, company_name, logo_url, website, address)
            connection, from_email, _smtp = _get_smtp_connection()
            msg = _build_message(
                subject=f'Welcome to {company_name} — Your Login Credentials',
                html_body=html_body, from_email=from_email, to=[email], connection=connection,
            )
            msg.send(fail_silently=False)
        except Exception as exc:
            logger.error('Welcome email failed for %s: %s', email, exc)

        logger.info('Employee %s (%s) hired via HireAction %s by %s', action.reserved_employee_id, email, action.id, request.user.email)
        return success('Employee hired.', _hire_action_dict(action), http_status=201)
