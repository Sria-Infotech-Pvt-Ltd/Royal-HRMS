"""Phase 7B Task G — salary splits and payment instructions."""
import uuid

from django.db import models


class PaymentInstruction(models.Model):
    MODE_BANK_TRANSFER = 'bank_transfer'
    MODE_CHEQUE        = 'cheque'
    MODE_CASH          = 'cash'
    MODE_CHOICES = [
        (MODE_BANK_TRANSFER, 'Bank transfer'), (MODE_CHEQUE, 'Cheque'), (MODE_CASH, 'Cash'),
    ]

    STATUS_PENDING  = 'pending'
    STATUS_SENT     = 'sent'
    STATUS_PAID     = 'paid'
    STATUS_FAILED   = 'failed'
    STATUS_RETURNED = 'returned'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_SENT, 'Sent'), (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'), (STATUS_RETURNED, 'Returned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payslip = models.ForeignKey('payroll.EmployeePayslip', on_delete=models.CASCADE, related_name='payment_instructions')
    bank_account = models.ForeignKey(
        'accounts.BankAccount', on_delete=models.PROTECT, null=True, blank=True, related_name='payment_instructions',
        help_text='Null when payment_mode is not bank_transfer.',
    )
    payment_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_BANK_TRANSFER)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    failure_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_payment_instructions_v2'
        ordering = ['payslip', 'created_at']

    def __str__(self):
        return f'{self.payslip_id} -> {self.amount} ({self.payment_mode})'
