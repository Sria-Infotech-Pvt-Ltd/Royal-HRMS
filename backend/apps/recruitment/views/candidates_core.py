import csv
import io
import logging
import secrets
import smtplib
import string
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from core.date_utils import format_date_display
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, Company, User
from apps.accounts.utils import send_template_email
from core.pagination import paginate, paginated_data
from core.template_context import candidate_context, candidate_interview_location, company_name, universal_context
from ..models import Candidate, CandidateEmail, CandidateLog, ReferralBonus, ReferralRule
from ..serializers import (
    CandidateBulkImportRowSerializer,
    CandidateCreateSerializer,
    CandidateDetailSerializer,
    CandidateEmailSerializer,
    CandidateListSerializer,
    CandidateUpdateSerializer,
    ReferralBonusSerializer,
    ReferralRuleSerializer,
    ReferralSubmitSerializer,
)

logger = logging.getLogger(__name__)

from apps.recruitment.views.shared import *  # noqa: F401,F403







_DENIED = 'You do not have permission to perform this action.'

# ─── Email helper ─────────────────────────────────────────────────────────────



# ─── Referral email helpers ───────────────────────────────────────────────────









_ICS_ESCAPE = str.maketrans({',': '\\,', ';': '\\;', '\n': '\\n'})








# ─── Candidate List + Create ──────────────────────────────────────────────────

class CandidateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        qs = Candidate.objects.select_related('interviewer', 'referral_by', 'added_by', 'branch').all()

        # Non-admin users are locked to their own branch — the branch query
        # param (used for the admin branch-picker dropdown) is only honoured
        # for settings.edit holders, mirroring leave/expense list scoping.
        is_admin = _has_perm(request.user, 'settings.edit')
        user_branch = (getattr(request.user, 'branch', '') or '').strip()
        if not is_admin and user_branch:
            qs = qs.filter(branch__branch_name__iexact=user_branch)

        if s := request.query_params.get('status'):
            if s in {Candidate.STATUS_PENDING, Candidate.STATUS_SELECTED, Candidate.STATUS_REJECTED}:
                qs = qs.filter(status=s)

        if b := request.query_params.get('branch'):
            if is_admin:
                try:
                    qs = qs.filter(branch_id=int(b))
                except (ValueError, TypeError):
                    pass

        if q := request.query_params.get('search'):
            qs = qs.filter(
                Q(name__icontains=q) | Q(email__icontains=q) | Q(position_applied__icontains=q)
            )

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 10

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Candidates retrieved.', data={
            'count':          paginator.count,
            'page':           page_obj.number,
            'page_size':      page_size,
            'total_pages':    paginator.num_pages,
            'status_choices': CandidateStatusView._STATUS_CHOICES,
            'results':        CandidateListSerializer(page_obj.object_list, many=True).data,
        })

    def post(self, request):
        if not _has_perm(request.user, 'recruitment.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        # Non-admin users are locked to their own branch — same scoping as
        # get() above (see _scoped_candidate_branch).
        data, branch_err = _scoped_candidate_branch(request)
        if branch_err:
            return branch_err

        serializer = CandidateCreateSerializer(data=data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        with transaction.atomic():
            candidate = serializer.save(added_by=request.user)
            _advance_status_on_interview_scheduled(candidate)

            CandidateLog.objects.create(
                candidate=candidate,
                log_type=CandidateLog.TYPE_INFO,
                title='Added to interview list',
                description=f'Added by {request.user.full_name or request.user.email}',
            )
            AuditLog.objects.create(
                user=request.user, action='candidate_created', module='recruitment',
                object_id=str(candidate.pk),
                changes={'name': candidate.name, 'position': candidate.position_applied},
                branch=candidate.branch.branch_name if candidate.branch else '',
                ip_address=get_client_ip(request),
            )
        _fire_interview_date_emails_if_needed(candidate, old_interview_date=None)
        logger.info('Candidate %s created by %s', candidate.id, request.user.email)
        return success('Candidate added to interview list.', data=CandidateListSerializer(candidate).data,
                  http_status=status.HTTP_201_CREATED)

    def put(self, request):
        return error(
            f'PUT is not supported on {request.path}. '
            'Use PUT /candidates/<id>/ to update a specific candidate.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def patch(self, request):
        return error(
            f'PATCH is not supported on {request.path}. '
            'Use PATCH /candidates/<id>/ to partially update a specific candidate.',
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def delete(self, request):
        """Bulk delete candidates by ID list. Skips converted / portal-credentials-sent candidates."""
        if not _has_perm(request.user, 'recruitment.delete'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get('ids')
        if not ids or not isinstance(ids, list):
            return error('Provide a non-empty list of candidate IDs in "ids".',
                         http_status=status.HTTP_400_BAD_REQUEST)
        try:
            ids = [int(i) for i in ids]
        except (ValueError, TypeError):
            return error('All values in "ids" must be integers.',
                         http_status=status.HTTP_400_BAD_REQUEST)
        if len(ids) > 100:
            return error('Cannot delete more than 100 candidates at once.',
                         http_status=status.HTTP_400_BAD_REQUEST)

        qs        = Candidate.objects.filter(pk__in=ids)
        deletable = qs.exclude(status=Candidate.STATUS_CONVERTED).exclude(portal_credentials_sent=True)
        skipped   = qs.count() - deletable.count()

        if deletable.count() == 0:
            return error(
                'No deletable candidates found. Converted candidates and those with '
                'portal credentials already sent cannot be deleted.',
                http_status=status.HTTP_409_CONFLICT,
            )

        for candidate in deletable:
            AuditLog.objects.create(
                user=request.user, action='candidate_deleted', module='recruitment',
                object_id=str(candidate.pk),
                changes={'name': candidate.name},
                branch=candidate.branch.branch_name if candidate.branch else '',
                ip_address=get_client_ip(request),
            )
        count = deletable.count()
        deletable.delete()

        msg = f'{count} candidate(s) deleted.'
        if skipped:
            msg += f' {skipped} skipped (converted or portal credentials sent).'
        logger.info('%s by %s', msg, request.user.email)
        return success(msg)


# ─── Candidate Detail ─────────────────────────────────────────────────────────

class CandidateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Candidate.objects.select_related(
                'interviewer', 'referral_by', 'added_by', 'branch'
            ).prefetch_related('logs').get(pk=pk)
        except Candidate.DoesNotExist:
            return None

    def get(self, request, pk):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        return success('Candidate retrieved.', data=CandidateDetailSerializer(candidate).data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        if candidate.status == Candidate.STATUS_CONVERTED:
            return error('Cannot edit a candidate who has already been converted to an employee.')

        data, branch_err = _scoped_candidate_branch(request, required=False)
        if branch_err:
            return branch_err

        serializer = CandidateUpdateSerializer(candidate, data=data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        old_interview_date = candidate.interview_date
        old_interview_time = candidate.interview_time
        old_meeting_link   = candidate.meeting_link
        try:
            updated = serializer.save()
        except Exception as exc:
            logger.error('CandidateDetailView PUT failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to update candidate. Please try again.',
                         http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        _advance_status_on_interview_scheduled(updated)
        AuditLog.objects.create(
            user=request.user, action='candidate_updated', module='recruitment',
            object_id=str(updated.pk),
            changes={k: v for k, v in request.data.items()},
            branch=updated.branch.branch_name if updated.branch else '',
            ip_address=get_client_ip(request),
        )
        _fire_interview_date_emails_if_needed(updated, old_interview_date, old_interview_time, old_meeting_link)
        logger.info('Candidate %s fully updated by %s', pk, request.user.email)
        return success('Candidate updated.', data=CandidateDetailSerializer(updated).data)

    def patch(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        if candidate.status == Candidate.STATUS_CONVERTED:
            return error('Cannot edit a candidate who has already been converted to an employee.')

        data, branch_err = _scoped_candidate_branch(request, required=False)
        if branch_err:
            return branch_err

        serializer = CandidateUpdateSerializer(candidate, data=data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors,
                         http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        old_interview_date = candidate.interview_date
        old_interview_time = candidate.interview_time
        old_meeting_link   = candidate.meeting_link
        try:
            updated = serializer.save()
        except Exception as exc:
            logger.error('CandidateDetailView PATCH failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to update candidate. Please try again.',
                         http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        _advance_status_on_interview_scheduled(updated)
        AuditLog.objects.create(
            user=request.user, action='candidate_updated', module='recruitment',
            object_id=str(updated.pk),
            changes={k: v for k, v in request.data.items()},
            branch=updated.branch.branch_name if updated.branch else '',
            ip_address=get_client_ip(request),
        )
        _fire_interview_date_emails_if_needed(updated, old_interview_date, old_interview_time, old_meeting_link)
        logger.info('Candidate %s partially updated by %s', pk, request.user.email)
        return success('Candidate updated.', data=CandidateDetailSerializer(updated).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'recruitment.delete'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = self._get(pk)
        if not candidate:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_candidate(request.user, candidate):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        if candidate.status == Candidate.STATUS_CONVERTED:
            return error(
                'Cannot delete a candidate who has been converted to an employee.',
                http_status=status.HTTP_409_CONFLICT,
            )
        if candidate.portal_credentials_sent:
            return error(
                'Cannot delete a candidate whose portal login has already been sent. '
                'Deactivate their portal account first.',
                http_status=status.HTTP_409_CONFLICT,
            )
        name = candidate.name
        cand_branch = candidate.branch.branch_name if candidate.branch else ''
        try:
            candidate.delete()
        except Exception as exc:
            logger.error('CandidateDetailView DELETE failed pk=%s: %s', pk, exc, exc_info=True)
            return error('Failed to delete candidate. Please try again.',
                         http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        AuditLog.objects.create(
            user=request.user, action='candidate_deleted', module='recruitment',
            object_id=str(pk),
            changes={'name': name},
            branch=cand_branch,
            ip_address=get_client_ip(request),
        )
        logger.info('Candidate "%s" (pk=%s) deleted by %s', name, pk, request.user.email)
        return success(f'Candidate "{name}" deleted successfully.')

    def post(self, request, pk):
        return self.put(request, pk)
