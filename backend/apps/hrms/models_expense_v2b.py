"""Phase 8B gap-closure — travel requests/advances, remaining expense policy rules (mileage, per-diem, deadline, duplicate detection)."""
import uuid

from django.db import models


class TravelRequest(models.Model):
    STATUS_DRAFT    = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_SETTLED  = 'settled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_APPROVED, 'Approved'), (STATUS_REJECTED, 'Rejected'), (STATUS_SETTLED, 'Settled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='travel_requests')
    purpose = models.CharField(max_length=200)
    itinerary = models.JSONField(default=list, help_text='[{"from": "...", "to": "...", "date": "...", "mode": "..."}]')
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2)
    advance_requested = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_paid_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_travel_requests_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee_id}: {self.purpose}'


class TravelExpenseClaimLink(models.Model):
    """Links an ExpenseClaim to the trip it settles against — advance
    balance = travel_request.advance_requested - sum(linked claims' total_base_amount)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    travel_request = models.ForeignKey(TravelRequest, on_delete=models.CASCADE, related_name='claim_links')
    claim = models.OneToOneField('hrms.ExpenseClaim', on_delete=models.CASCADE, related_name='travel_link')

    class Meta:
        db_table = 'hrms_travel_expense_claim_links_v2'

    def __str__(self):
        return f'{self.claim_id} settles {self.travel_request_id}'
