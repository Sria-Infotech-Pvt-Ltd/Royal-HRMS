import logging

from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.utils import send_template_email
from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success
from core.template_context import expense_context, universal_context

from ..models import (
    Expense, ExpenseReceipt,
    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED,
)
from ..serializers import (
    ExpenseCreateSerializer,
    ExpenseSerializer,
    validate_receipt_file,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _resolve_branch(user):
    branch_name = getattr(user, 'branch', None)
    if not branch_name:
        return None
    from apps.branch.models import Branch
    return Branch.objects.filter(branch_name__iexact=branch_name).first()


def _can_access_expense(user, expense) -> bool:
    """
    True for the submitter always. Otherwise the user must hold
    expenses.approve AND be scoped to this expense's employee — managers via
    the reporting chain, everyone else (e.g. hr_admin) via branch — mirroring
    the scoping conventions used for leave requests/balances.
    """
    if expense.employee_id == user.id:
        return True
    if not _has_perm(user, 'expenses.approve'):
        return False
    role = user.role.name if user.role else ''
    if role == 'system_admin':
        return True
    if role == 'manager__team_lead':
        return expense.employee.reporting_manager_id == user.id
    branch = getattr(user, 'branch', '') or ''
    return not branch or (getattr(expense.employee, 'branch', '') or '') == branch


class ExpenseListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        has_approve = _has_perm(request.user, 'expenses.approve')
        queryset = (
            Expense.objects.select_related('employee', 'branch')
                           .prefetch_related('receipts')
        )

        if not has_approve:
            queryset = queryset.filter(employee=request.user)
        else:
            # Mirrors _can_access_expense's per-record scoping, which was never
            # applied here — without it, any approver saw every expense
            # company-wide instead of just the employees they're allowed to act on.
            role = request.user.role.name if request.user.role else ''
            if role == 'system_admin':
                pass
            elif role == 'manager__team_lead':
                queryset = queryset.filter(employee__reporting_manager_id=request.user.id)
            else:
                user_branch = getattr(request.user, 'branch', '') or ''
                if user_branch:
                    queryset = queryset.filter(employee__branch=user_branch)

        branch = request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(branch_id=branch)

        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = ExpenseSerializer(page_obj.object_list, many=True, context={'request': request})
        return success('Expenses retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        receipt_files = request.FILES.getlist('receipts') or request.FILES.getlist('receipt')
        if not receipt_files:
            return error('At least one receipt is required.')

        for receipt_file in receipt_files:
            try:
                validate_receipt_file(receipt_file)
            except Exception as exc:
                return error(str(exc))

        serializer = ExpenseCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        with transaction.atomic():
            branch   = _resolve_branch(request.user)
            last_num = Expense.objects.select_for_update().aggregate(n=Max('expense_number'))['n'] or 0
            expense  = serializer.save(
                employee=request.user,
                branch=branch,
                expense_number=last_num + 1,
            )
            for receipt_file in receipt_files:
                ExpenseReceipt.objects.create(expense=expense, file=receipt_file)

        logger.info('Expense submitted: %s by %s (%d receipts)', expense.title, request.user.email, len(receipt_files))

        out = ExpenseSerializer(
            Expense.objects.select_related('employee', 'branch')
                           .prefetch_related('receipts')
                           .get(pk=expense.pk),
            context={'request': request},
        )
        return success('Expense submitted successfully.', out.data, http_status=status.HTTP_201_CREATED)


class ExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def _get_expense(self, expense_number: int, user):
        try:
            expense = (
                Expense.objects.select_related('employee', 'branch')
                               .prefetch_related('receipts')
                               .get(expense_number=expense_number)
            )
        except Expense.DoesNotExist:
            return None, error('Expense not found.', http_status=status.HTTP_404_NOT_FOUND)
        if not _can_access_expense(user, expense):
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return expense, None

    def _fresh(self, pk, request):
        return ExpenseSerializer(
            Expense.objects.select_related('employee', 'branch')
                           .prefetch_related('receipts')
                           .get(pk=pk),
            context={'request': request},
        ).data

    def _validate_receipts(self, files):
        for f in files:
            try:
                validate_receipt_file(f)
            except Exception as exc:
                return str(exc)
        return None

    # ── READ ─────────────────────────────────────────────────────────────────

    def get(self, request, expense_number: int):
        expense, err = self._get_expense(expense_number, request.user)
        if err:
            return err
        return success('Expense retrieved.', ExpenseSerializer(expense, context={'request': request}).data)

    # ── APPROVAL — if status field sent, treat as approve/reject ─────────────

    def _handle_approval(self, request, expense, expense_number: int):
        if not _has_perm(request.user, 'expenses.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        if expense.employee_id == request.user.id:
            return error('You cannot approve or reject your own expense.', http_status=status.HTTP_403_FORBIDDEN)
        if expense.status != STATUS_PENDING:
            return error(
                f'Expense is already {expense.status}. Only pending expenses can be actioned.',
                http_status=status.HTTP_409_CONFLICT,
            )
        status_val = request.data.get('status', '').strip().lower()
        if status_val not in (STATUS_APPROVED, STATUS_REJECTED):
            return error('status must be "approved" or "rejected".')
        expense.status = status_val
        expense.save(update_fields=['status', 'updated_at'])
        logger.info('Expense %s %s by %s', expense_number, status_val, request.user.email)

        # Optional notification email — the approve/reject modal lets the
        # approver pick a template and fill in its variables; previously this
        # was accepted and silently discarded, so nothing was ever sent.
        template_name = request.data.get('template_name')
        if template_name:
            self._send_decision_email(expense, template_name, request.data.get('extra_context') or {})

        return success(f'Expense {status_val}.', self._fresh(expense.pk, request))

    def _send_decision_email(self, expense, template_name: str, extra_context: dict) -> None:
        # Server-computed values win over whatever the client sent — the
        # client's copy is only a preview; re-deriving it here guarantees the
        # email always matches the real record, not a stale client-side echo.
        context = {**universal_context(), **extra_context, **expense_context(expense)}
        try:
            send_template_email(
                recipient_email=expense.employee.email,
                template_name=template_name,
                context=context,
            )
        except LookupError:
            logger.warning('Expense %s: unknown/inactive template "%s" — no email sent.',
                            expense.expense_number, template_name)
        except Exception:
            logger.exception('Failed to send "%s" email for expense %s', template_name, expense.expense_number)

    # ── UPDATE (full) — PUT replaces all receipts if files are sent ───────────

    def put(self, request, expense_number: int):
        expense, err = self._get_expense(expense_number, request.user)
        if err:
            return err

        if 'status' in request.data:
            return self._handle_approval(request, expense, expense_number)

        has_approve = _has_perm(request.user, 'expenses.approve')
        if not has_approve and expense.employee_id != request.user.id:
            return error('Only the submitter can edit an expense.', http_status=status.HTTP_403_FORBIDDEN)
        if expense.status != STATUS_PENDING:
            return error('Only pending expenses can be edited.', http_status=status.HTTP_409_CONFLICT)

        serializer = ExpenseCreateSerializer(expense, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()

        new_receipts = request.FILES.getlist('receipts') or request.FILES.getlist('receipt')
        if new_receipts:
            receipt_err = self._validate_receipts(new_receipts)
            if receipt_err:
                return error(receipt_err)
            with transaction.atomic():
                expense.receipts.all().delete()
                for f in new_receipts:
                    ExpenseReceipt.objects.create(expense=expense, file=f)

        logger.info('Expense %s updated by %s', expense_number, request.user.email)
        return success('Expense updated.', self._fresh(expense.pk, request))

    # ── UPDATE (partial) — PATCH appends receipts, does not replace ───────────

    def patch(self, request, expense_number: int):
        expense, err = self._get_expense(expense_number, request.user)
        if err:
            return err

        if 'status' in request.data:
            return self._handle_approval(request, expense, expense_number)

        has_approve = _has_perm(request.user, 'expenses.approve')
        if not has_approve and expense.employee_id != request.user.id:
            return error('Only the submitter can edit an expense.', http_status=status.HTTP_403_FORBIDDEN)
        if expense.status != STATUS_PENDING:
            return error('Only pending expenses can be edited.', http_status=status.HTTP_409_CONFLICT)

        serializer = ExpenseCreateSerializer(expense, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()

        new_receipts = request.FILES.getlist('receipts') or request.FILES.getlist('receipt')
        if new_receipts:
            receipt_err = self._validate_receipts(new_receipts)
            if receipt_err:
                return error(receipt_err)
            for f in new_receipts:
                ExpenseReceipt.objects.create(expense=expense, file=f)

        logger.info('Expense %s patched by %s', expense_number, request.user.email)
        return success('Expense updated.', self._fresh(expense.pk, request))

    def post(self, request, expense_number: int):
        return self.patch(request, expense_number)

    # ── DELETE — expense or single receipt (?receipt_id=<uuid>) ──────────────

    def delete(self, request, expense_number: int):
        expense, err = self._get_expense(expense_number, request.user)
        if err:
            return err

        has_approve = _has_perm(request.user, 'expenses.approve')

        receipt_id = request.query_params.get('receipt_id', '').strip()
        if receipt_id:
            try:
                receipt = expense.receipts.get(id=receipt_id)
            except ExpenseReceipt.DoesNotExist:
                return error('Receipt not found.', http_status=status.HTTP_404_NOT_FOUND)
            if not has_approve and expense.status != STATUS_PENDING:
                return error('Receipts on non-pending expenses cannot be removed.', http_status=status.HTTP_409_CONFLICT)
            if expense.receipts.count() <= 1:
                return error('An expense must have at least one receipt.', http_status=status.HTTP_409_CONFLICT)
            receipt.delete()
            logger.info('Receipt %s removed from expense %s by %s', receipt_id, expense_number, request.user.email)
            return success('Receipt deleted.', self._fresh(expense.pk, request))

        if expense.status == STATUS_APPROVED:
            return error('Approved expenses cannot be deleted.', http_status=status.HTTP_409_CONFLICT)
        expense.delete()
        logger.info('Expense %s deleted by %s', expense_number, request.user.email)
        return success('Expense deleted.')


class ExpenseCategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categories = [
            {'value': key, 'label': label}
            for key, label in Expense.CATEGORY_CHOICES
        ]
        return success('Categories retrieved.', categories)


class ExpenseStatusListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        statuses = [
            {'value': key, 'label': label}
            for key, label in Expense.STATUS_CHOICES
        ]
        return success('Statuses retrieved.', statuses)


class ExpenseStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        has_approve = _has_perm(request.user, 'expenses.approve')
        queryset = (
            Expense.objects.all()
            if has_approve
            else Expense.objects.filter(employee=request.user)
        )

        stats = queryset.aggregate(
            total           = Count('id'),
            pending_count   = Count('id', filter=Q(status='pending')),
            approved_count  = Count('id', filter=Q(status='approved')),
            rejected_count  = Count('id', filter=Q(status='rejected')),
            total_amount    = Sum('amount'),
            pending_amount  = Sum('amount', filter=Q(status='pending')),
            approved_amount = Sum('amount', filter=Q(status='approved')),
        )

        return success('Stats retrieved.', {
            'total':           stats['total']           or 0,
            'pending':         stats['pending_count']   or 0,
            'approved':        stats['approved_count']  or 0,
            'rejected':        stats['rejected_count']  or 0,
            'total_amount':    float(stats['total_amount']    or 0),
            'pending_amount':  float(stats['pending_amount']  or 0),
            'approved_amount': float(stats['approved_amount'] or 0),
        })
