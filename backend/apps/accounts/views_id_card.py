"""
Employee ID cards — Settings → ID Card configuration, and the per-employee
card data used by the front/back print template.

The uploaded PDF is a design reference only (a flattened export with one
person's details baked in — it cannot be re-filled for another employee),
so cards are rendered by the frontend's HTML/CSS template from the data
returned here. Company logo and website are read from Company — never
uploaded or stored again here.

Deliberately its own file, not views.py (already far past the 300-line
convention) — mirrors views_profile_photo.py.
"""
from __future__ import annotations

import logging

from django.db import transaction
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import HasSettingsPermission, has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, EmployeeProfile, IdCardSettings

logger = logging.getLogger(__name__)

MAX_REFERENCE_PDF_BYTES = 10 * 1024 * 1024
MAX_SIGNATURE_BYTES     = 2 * 1024 * 1024
_SIGNATURE_FORMATS      = {'PNG', 'JPEG', 'WEBP'}
DATE_FORMAT             = '%d/%m/%Y'

DEFAULT_TERMS = (
    'This ID card is the property of {company}.',
    'This ID card is non-transferable.',
    'If found, please return to the above address.',
)


def _file_url(field_file) -> str | None:
    # Both files use AuthenticatedRawMediaCloudinaryStorage, whose url() is
    # a short-lived signed URL — never a permanent public link.
    if not field_file:
        return None
    try:
        return field_file.url
    except Exception:
        logger.warning('Could not build URL for ID card file %s', field_file.name)
        return None


def validate_reference_pdf(upload) -> str | None:
    """Returns an error message, or None when the upload is an acceptable PDF."""
    if not upload.name.lower().endswith('.pdf'):
        return 'The reference file must be a PDF.'
    if upload.size > MAX_REFERENCE_PDF_BYTES:
        return 'The reference PDF must be under 10 MB.'
    head = upload.read(5)
    upload.seek(0)
    if head != b'%PDF-':
        return 'The file is not a valid PDF.'
    return None


def validate_signature_image(upload) -> str | None:
    if upload.size > MAX_SIGNATURE_BYTES:
        return 'The signature image must be under 2 MB.'
    try:
        with Image.open(upload) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return 'The signature must be a PNG, JPEG, or WebP image.'
    finally:
        upload.seek(0)
    if fmt not in _SIGNATURE_FORMATS:
        return 'The signature must be a PNG, JPEG, or WebP image.'
    return None


class IdCardSettingsSerializer(serializers.ModelSerializer):
    reference_pdf_url = serializers.SerializerMethodField()
    signature_url     = serializers.SerializerMethodField()
    updated_by_name   = serializers.SerializerMethodField()
    default_terms     = serializers.SerializerMethodField()

    class Meta:
        model  = IdCardSettings
        fields = [
            'signatory_label', 'terms', 'default_terms',
            'show_date_of_birth', 'show_residential_address', 'show_contact_details',
            'reference_pdf_name', 'reference_pdf_size', 'reference_pdf_url',
            'signature_url', 'updated_at', 'updated_by_name',
        ]
        read_only_fields = ['reference_pdf_name', 'reference_pdf_size', 'updated_at']

    def get_reference_pdf_url(self, obj) -> str | None:
        return _file_url(obj.reference_pdf)

    def get_signature_url(self, obj) -> str | None:
        return _file_url(obj.signature_image)

    def get_updated_by_name(self, obj) -> str | None:
        return obj.updated_by.full_name if obj.updated_by_id else None

    def get_default_terms(self, obj) -> str:
        return '\n'.join(DEFAULT_TERMS)

    def validate_signatory_label(self, value: str) -> str:
        return value.strip() or IdCardSettings.DEFAULT_SIGNATORY_LABEL

    def validate_terms(self, value: str) -> str:
        lines = [ln.strip() for ln in (value or '').splitlines() if ln.strip()]
        if len(lines) > 6:
            raise serializers.ValidationError('Use at most 6 conditions so they fit on the card.')
        if any(len(ln) > 160 for ln in lines):
            raise serializers.ValidationError('Each condition must be 160 characters or fewer.')
        return '\n'.join(lines)


def _truthy(value) -> bool:
    return str(value or '').lower() in ('1', 'true', 'yes')


class IdCardSettingsView(APIView):
    """
    GET /api/settings/id-card/  — settings.view
    PUT /api/settings/id-card/  — settings.edit (multipart; partial update)
        files:  reference_pdf, signature_image
        flags:  remove_reference_pdf, remove_signature
    """
    permission_classes = [IsAuthenticated, HasSettingsPermission]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return success('ID card settings retrieved.', data=IdCardSettingsSerializer(IdCardSettings.get()).data)

    def put(self, request):
        pdf       = request.FILES.get('reference_pdf')
        signature = request.FILES.get('signature_image')
        for upload, check in ((pdf, validate_reference_pdf), (signature, validate_signature_image)):
            message = upload and check(upload)
            if message:
                return error(message)

        with transaction.atomic():
            cfg = IdCardSettings.objects.select_for_update().get_or_create(pk=1)[0]
            serializer = IdCardSettingsSerializer(cfg, data=request.data, partial=True)
            if not serializer.is_valid():
                return error(first_error(serializer.errors), data=serializer.errors)
            cfg = serializer.save(updated_by=request.user)

            changes = {k: v for k, v in serializer.validated_data.items()}
            if pdf or _truthy(request.data.get('remove_reference_pdf')):
                if cfg.reference_pdf:
                    cfg.reference_pdf.delete(save=False)
                cfg.reference_pdf, cfg.reference_pdf_name, cfg.reference_pdf_size = None, '', None
                if pdf:
                    cfg.reference_pdf.save(pdf.name, pdf, save=False)
                    cfg.reference_pdf_name, cfg.reference_pdf_size = pdf.name[:255], pdf.size
                changes['reference_pdf'] = cfg.reference_pdf_name or 'removed'
            if signature or _truthy(request.data.get('remove_signature')):
                if cfg.signature_image:
                    cfg.signature_image.delete(save=False)
                cfg.signature_image = None
                if signature:
                    cfg.signature_image.save(signature.name, signature, save=False)
                changes['signature_image'] = 'updated' if signature else 'removed'
            cfg.save()

        AuditLog.objects.create(
            user=request.user,
            action='id_card_settings_updated',
            module='settings',
            object_id='1',
            changes=changes,
            ip_address=get_client_ip(request),
        )
        logger.info('ID card settings updated by %s', request.user.email)
        return success('ID card settings saved.', data=IdCardSettingsSerializer(cfg).data)

    def patch(self, request):
        return self.put(request)


# ─── Per-employee card data ───────────────────────────────────────────────────

def _fmt_date(value) -> str | None:
    return value.strftime(DATE_FORMAT) if value else None


def _display_website(url: str) -> str:
    v = (url or '').strip()
    for scheme in ('https://', 'http://'):
        if v.lower().startswith(scheme):
            v = v[len(scheme):]
    return v.rstrip('/')


def _company_address(company) -> str:
    tail = ' '.join(p for p in (company.state, company.pin_code) if p)
    return ', '.join(p.strip() for p in (company.address, company.city, tail) if p and p.strip())


def _employee_branch(employee):
    from apps.branch.models import Branch
    if not employee.branch:
        return None
    return Branch.objects.select_related('city').filter(branch_name__iexact=employee.branch.strip()).first()


def build_id_card(employee, request) -> dict:
    """
    Everything the front/back template prints, from existing records only.
    Blank or hidden values are returned as None (never placeholders) and the
    labels of blank ones are listed in `missing` so the UI can flag them.
    """
    from core.cache_service import CompanyCacheService
    cfg     = IdCardSettings.get()
    company = CompanyCacheService.get()
    profile = EmployeeProfile.objects.filter(user=employee).first()
    branch  = _employee_branch(employee)

    company_name = (company.trade_name or company.company_name) if company else ''
    logo_url = None
    if company and company.logo:
        logo_url = request.build_absolute_uri(company.logo.url)

    if branch and branch.address.strip():
        office_address = branch.address.strip()
    elif company:
        office_address = _company_address(company) or None
    else:
        office_address = None

    photo_url = request.build_absolute_uri(employee.profile_photo.url) if employee.profile_photo else None
    residential = ((profile.current_address or profile.permanent_address).strip() or None) if profile else None
    terms_source = cfg.terms.splitlines() if cfg.terms.strip() else DEFAULT_TERMS
    terms = [t.replace('{company}', company_name or 'the company') for t in terms_source if t.strip()]

    employee_data = {
        'employee_id':         employee.employee_id or None,
        'full_name':           employee.full_name or None,
        'designation':         employee.designation or None,
        'department':          employee.department or None,
        'date_of_joining':     _fmt_date(employee.date_of_joining),
        'date_of_birth':       _fmt_date(profile.date_of_birth) if profile and cfg.show_date_of_birth else None,
        'blood_group':         (profile.blood_group or None) if profile else None,
        'location':            (branch.city.name if branch and branch.city_id else (employee.branch or None)),
        'photo_url':           photo_url,
        'residential_address': residential if cfg.show_residential_address else None,
        'phone':               (employee.phone or None) if cfg.show_contact_details else None,
        'email':               employee.email if cfg.show_contact_details else None,
    }
    company_data = {
        'name':           company_name or None,
        'logo_url':       logo_url,
        'website':        _display_website(company.website) if company else None,
        'website_url':    (company.website or None) if company else None,
        'office_address': office_address,
    }
    card = {
        'terms':                    terms,
        'signature_url':            _file_url(cfg.signature_image),
        'signatory_label':          cfg.signatory_label or IdCardSettings.DEFAULT_SIGNATORY_LABEL,
        'show_date_of_birth':       cfg.show_date_of_birth,
        'show_residential_address': cfg.show_residential_address,
        'show_contact_details':     cfg.show_contact_details,
    }

    checks = [
        ('Company logo',        company_data['logo_url'], True),
        ('Company website',     company_data['website'], True),
        ('Employee photo',      photo_url, True),
        ('Designation',         employee_data['designation'], True),
        ('Employee code',       employee_data['employee_id'], True),
        ('Date of birth',       employee_data['date_of_birth'], cfg.show_date_of_birth),
        ('Date of joining',     employee_data['date_of_joining'], True),
        ('Department',          employee_data['department'], True),
        ('Blood group',         employee_data['blood_group'], True),
        ('Location',            employee_data['location'], True),
        ('Residential address', employee_data['residential_address'], cfg.show_residential_address),
        ('Office address',      office_address, True),
        ('Phone',               employee_data['phone'], cfg.show_contact_details),
        ('Authorised signature', card['signature_url'], True),
    ]
    missing = [label for label, value, shown in checks if shown and not value]

    return {'employee': employee_data, 'company': company_data, 'card': card, 'missing': missing}


class EmployeeIdCardView(APIView):
    """
    GET /api/employees/<employee_id>/id-card/

    Same access rule as the employee detail endpoint (employees.view plus
    branch scope) — the card shows nothing that page doesn't already show.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        from apps.accounts.views import _employee_out_of_branch_scope, _get_employee
        if not has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('ID card data retrieved.', data=build_id_card(employee, request))
