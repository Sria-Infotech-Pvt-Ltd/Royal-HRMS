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




# ─── Referrals ────────────────────────────────────────────────────────────────

class ReferralListCreateView(APIView):
   
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = (
            Candidate.objects
            .select_related('branch', 'interviewer', 'referral_by', 'added_by')
            .filter(referral_by=request.user)
        )
        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = CandidateListSerializer(page_obj.object_list, many=True)
        return success('Referrals fetched.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        
        serializer = ReferralSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        candidate = serializer.save(
            referral_by=request.user,
            added_by=request.user,
            status=Candidate.STATUS_PENDING,
        )
        from apps.recruitment.tasks import send_referral_submission_emails_task

        def _dispatch(candidate_id=candidate.pk):
            try:
                # ignore_result=True — nothing here ever calls .get() on the
                # returned AsyncResult, but apply_async() still subscribes to
                # a Redis pub/sub channel for the result by default (so a
                # later .get() would work), and retries that subscription up
                # to 20 times against the *result backend* if Redis is
                # unreachable — a completely separate retry loop from the
                # broker-connection one that retry=False/CELERY_BROKER_*
                # below bound. ignore_result=True skips it entirely.
                # retry=False — a single, capped-timeout attempt (see
                # CELERY_BROKER_TRANSPORT_OPTIONS) so a down/unreachable
                # broker fails in ~1s instead of blocking this request for
                # up to 20s on Kombu's default connection retry loop.
                send_referral_submission_emails_task.apply_async(
                    args=[candidate_id], retry=False, ignore_result=True,
                )
            except Exception as exc:
                logger.error(
                    'Failed to queue referral-submission email for candidate %s: %s',
                    candidate_id, exc, exc_info=True,
                )

        transaction.on_commit(_dispatch)
        logger.info('Referral submitted by %s for %s', request.user.email, candidate.email)
        return success(
            'Referral submitted successfully.',
            CandidateListSerializer(candidate).data,
            http_status=status.HTTP_201_CREATED,
        )


class ReferralAllView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'recruitment.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        _pipeline_statuses = [
            Candidate.STATUS_PENDING,
            Candidate.STATUS_SCREENING,
            Candidate.STATUS_INTERVIEW_SCHEDULED,
            Candidate.STATUS_INTERVIEW_DONE,
            Candidate.STATUS_OFFER_SENT,
        ]

        base_qs = Candidate.objects.filter(referral_by__isnull=False)

        stats = base_qs.aggregate(
            total_referred=Count('id'),
            in_pipeline=Count('id', filter=Q(status__in=_pipeline_statuses)),
            selected=Count('id', filter=Q(status=Candidate.STATUS_SELECTED)),
            converted=Count('id', filter=Q(status=Candidate.STATUS_CONVERTED)),
        )

        queryset = base_qs.select_related('branch', 'interviewer', 'referral_by', 'added_by')
        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = CandidateListSerializer(page_obj.object_list, many=True)
        data = paginated_data(paginator, page_obj, serializer.data)
        data['stats'] = {
            'total_referred': stats['total_referred'],
            'in_pipeline':    stats['in_pipeline'],
            'selected':       stats['selected'],
            'converted':      stats['converted'],
        }
        return success('Referrals fetched.', data)


# ─── Referral Rules ───────────────────────────────────────────────────────────

class ReferralRuleListCreateView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ReferralRule.objects.all().order_by('order', 'id')

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 20

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Rules fetched.', {
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     ReferralRuleSerializer(page_obj.object_list, many=True).data,
        })

    def post(self, request):
        if not _has_perm(request.user, 'settings.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = ReferralRuleSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        rule = serializer.save()
        logger.info('ReferralRule "%s" created by %s', rule.title, request.user.email)
        return success('Rule created.', ReferralRuleSerializer(rule).data, http_status=status.HTTP_201_CREATED)


class ReferralRuleDetailView(APIView):
   
    permission_classes = [IsAuthenticated]

    def _get_rule(self, pk):
        try:
            return ReferralRule.objects.get(pk=pk)
        except ReferralRule.DoesNotExist:
            return None

    def patch(self, request, pk):
        if not _has_perm(request.user, 'settings.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        rule = self._get_rule(pk)
        if not rule:
            return error('Rule not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = ReferralRuleSerializer(rule, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        logger.info('ReferralRule "%s" updated by %s', rule.title, request.user.email)
        return success('Rule updated.', ReferralRuleSerializer(rule).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'settings.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        rule = self._get_rule(pk)
        if not rule:
            return error('Rule not found.', http_status=status.HTTP_404_NOT_FOUND)
        title = rule.title
        rule.delete()
        logger.info('ReferralRule "%s" deleted by %s', title, request.user.email)
        return success('Rule deleted.', None)


# ─── Referral Bonuses ──────────────────────────────────────────────────────────

class ReferralBonusListView(APIView):
   
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = request.query_params.get('scope', '')
        has_approve = _has_perm(request.user, 'recruitment.edit')

        if scope == 'my' or not has_approve:
            qs = (
                ReferralBonus.objects
                .select_related('candidate', 'referrer', 'approved_by', 'paid_by')
                .filter(referrer=request.user)
            )
        else:
            qs = (
                ReferralBonus.objects
                .select_related('candidate', 'referrer', 'approved_by', 'paid_by')
                .all()
            )

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        page_obj, paginator = paginate(qs, request, default_page_size=20)
        serializer = ReferralBonusSerializer(page_obj.object_list, many=True)
        return success('Referral bonuses retrieved.', paginated_data(paginator, page_obj, serializer.data))


class ReferralBonusDetailView(APIView):
    
    permission_classes = [IsAuthenticated]

    def _get_bonus(self, pk):
        try:
            return ReferralBonus.objects.select_related(
                'candidate', 'referrer', 'approved_by', 'paid_by'
            ).get(pk=pk)
        except ReferralBonus.DoesNotExist:
            return None

    def get(self, request, pk):
        bonus = self._get_bonus(pk)
        if not bonus:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)
        has_approve = _has_perm(request.user, 'recruitment.edit')
        if not has_approve and bonus.referrer_id != request.user.id:
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        return success('Referral bonus retrieved.', ReferralBonusSerializer(bonus).data)

    def patch(self, request, pk):
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        bonus = self._get_bonus(pk)
        if not bonus:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)
        if bonus.status == ReferralBonus.STATUS_PAID:
            return error('Cannot edit a bonus that has already been paid.')

        if 'bonus_amount' in request.data:
            try:
                amount = Decimal(str(request.data['bonus_amount']))
                if amount < 0:
                    raise ValueError
            except (TypeError, ValueError, InvalidOperation):
                return error('bonus_amount must be a non-negative number.')
            bonus.bonus_amount = amount

        if 'notes' in request.data:
            bonus.notes = str(request.data['notes']).strip()

        bonus.save(update_fields=['bonus_amount', 'notes', 'updated_at'])
        logger.info('Referral bonus %s updated by %s', pk, request.user.email)
        return success('Referral bonus updated.', ReferralBonusSerializer(bonus).data)

    def put(self, request, pk):
        return self.patch(request, pk)


class ReferralBonusApproveView(APIView):
   
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone as tz
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            bonus = ReferralBonus.objects.select_related('candidate', 'referrer').get(pk=pk)
        except ReferralBonus.DoesNotExist:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)

        if bonus.status != ReferralBonus.STATUS_PENDING:
            return error(
                f'Bonus is already {bonus.get_status_display()}. Only pending bonuses can be approved.',
                http_status=status.HTTP_409_CONFLICT,
            )

        if 'bonus_amount' in request.data:
            try:
                amount = Decimal(str(request.data['bonus_amount']))
                if amount < 0:
                    raise ValueError
                bonus.bonus_amount = amount
            except (TypeError, ValueError, InvalidOperation):
                return error('bonus_amount must be a non-negative number.')

        if 'notes' in request.data:
            bonus.notes = str(request.data['notes']).strip()

        bonus.status      = ReferralBonus.STATUS_APPROVED
        bonus.approved_by = request.user
        bonus.approved_at = tz.now()
        bonus.save(update_fields=['bonus_amount', 'notes', 'status', 'approved_by', 'approved_at', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='referral_bonus_approved', module='recruitment',
            object_id=str(bonus.pk),
            changes={'referrer': bonus.referrer.employee_id, 'amount': str(bonus.bonus_amount)},
            branch=bonus.referrer.branch,
            ip_address=get_client_ip(request),
        )
        logger.info('Referral bonus %s approved by %s (amount: %s)', pk, request.user.email, bonus.bonus_amount)
        return success(
            f'Bonus of ₹{bonus.bonus_amount} approved for {bonus.referrer.full_name}.',
            ReferralBonusSerializer(bonus).data,
        )


class ReferralBonusPayView(APIView):
    
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone as tz
        if not _has_perm(request.user, 'recruitment.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        try:
            bonus = ReferralBonus.objects.select_related('candidate', 'referrer').get(pk=pk)
        except ReferralBonus.DoesNotExist:
            return error('Referral bonus not found.', http_status=status.HTTP_404_NOT_FOUND)

        if bonus.status != ReferralBonus.STATUS_APPROVED:
            return error(
                'Only approved bonuses can be marked as paid.',
                http_status=status.HTTP_409_CONFLICT,
            )

        if 'notes' in request.data:
            bonus.notes = str(request.data['notes']).strip()

        bonus.status  = ReferralBonus.STATUS_PAID
        bonus.paid_by = request.user
        bonus.paid_at = tz.now()
        bonus.save(update_fields=['notes', 'status', 'paid_by', 'paid_at', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='referral_bonus_paid', module='recruitment',
            object_id=str(bonus.pk),
            changes={'referrer': bonus.referrer.employee_id, 'amount': str(bonus.bonus_amount)},
            branch=bonus.referrer.branch,
            ip_address=get_client_ip(request),
        )
        logger.info('Referral bonus %s marked paid by %s', pk, request.user.email)
        return success(
            f'Bonus of ₹{bonus.bonus_amount} marked as paid for {bonus.referrer.full_name}.',
            ReferralBonusSerializer(bonus).data,
        )
