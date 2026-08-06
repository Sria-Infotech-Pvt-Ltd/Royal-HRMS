from django.conf import settings
from django.db import models

from apps.branch.models import Branch


class Candidate(models.Model):
    MODE_IN_PERSON  = 'in_person'
    MODE_VIDEO_CALL = 'video_call'
    MODE_PHONE      = 'phone'
    MODE_CHOICES = [
        (MODE_IN_PERSON,  'In-Person'),
        (MODE_VIDEO_CALL, 'Video Call'),
        (MODE_PHONE,      'Phone'),
    ]

    STATUS_PENDING             = 'pending'
    STATUS_SCREENING           = 'screening'
    STATUS_INTERVIEW_SCHEDULED = 'interview_scheduled'
    STATUS_INTERVIEW_DONE      = 'interview_done'
    STATUS_SELECTED            = 'selected'
    STATUS_OFFER_SENT          = 'offer_sent'
    STATUS_CONVERTED           = 'converted'
    STATUS_REJECTED            = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING,             'Pending'),
        (STATUS_SCREENING,           'Screening'),
        (STATUS_INTERVIEW_SCHEDULED, 'Interview Scheduled'),
        (STATUS_INTERVIEW_DONE,      'Interview Done'),
        (STATUS_SELECTED,            'Selected'),
        (STATUS_OFFER_SENT,          'Offer Sent'),
        (STATUS_CONVERTED,           'Converted to Employee'),
        (STATUS_REJECTED,            'Rejected'),
    ]

    name             = models.CharField(max_length=200)
    email            = models.EmailField()
    phone            = models.CharField(max_length=20, blank=True)
    position_applied = models.CharField(max_length=200)
    branch           = models.ForeignKey(
                           Branch,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='candidates',
                       )
    interview_date   = models.DateField(null=True, blank=True)
    interview_time   = models.TimeField(null=True, blank=True)
    interviewer      = models.ForeignKey(
                           settings.AUTH_USER_MODEL,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='interviews_as_interviewer',
                       )
    interview_mode   = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_IN_PERSON)
    meeting_link     = models.URLField(max_length=500, blank=True, help_text='Video call link — shown to the candidate when interview_mode is Video Call.')
    notes            = models.TextField(blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    referral_by      = models.ForeignKey(
                           settings.AUTH_USER_MODEL,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='referrals_made',
                       )
    details_filled          = models.BooleanField(default=False)
    hr_approved             = models.BooleanField(default=False)
    portal_credentials_sent = models.BooleanField(default=False)
    portal_user             = models.ForeignKey(
                                  settings.AUTH_USER_MODEL,
                                  on_delete=models.SET_NULL,
                                  null=True, blank=True,
                                  related_name='candidate_portal',
                              )
    added_by         = models.ForeignKey(
                           settings.AUTH_USER_MODEL,
                           on_delete=models.SET_NULL,
                           null=True, blank=True,
                           related_name='candidates_added',
                       )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_candidates'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} — {self.position_applied}'


class CandidateLog(models.Model):
    TYPE_SUCCESS = 'success'
    TYPE_ERROR   = 'error'
    TYPE_INFO    = 'info'
    TYPE_WARN    = 'warn'
    TYPE_CHOICES = [
        (TYPE_SUCCESS, 'Success'),
        (TYPE_ERROR,   'Error'),
        (TYPE_INFO,    'Info'),
        (TYPE_WARN,    'Warning'),
    ]

    candidate   = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='logs')
    log_type    = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_INFO)
    title       = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_candidate_logs'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.candidate.name} — {self.title}'


class CandidateEmail(models.Model):
    STATUS_SENT   = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SENT,   'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    candidate     = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='emails')
    template_used = models.CharField(max_length=100, blank=True)
    subject       = models.CharField(max_length=500)
    to_email      = models.EmailField()
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SENT)
    sent_by       = models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name='recruitment_emails_sent',
                    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_candidate_emails'
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.subject} → {self.to_email}'


class ReferralRule(models.Model):
    icon      = models.CharField(max_length=50)
    title     = models.CharField(max_length=150)
    body      = models.TextField()
    order     = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'referral_rule'
        ordering = ['order']

    def __str__(self):
        return self.title


class ReferralBonus(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_PAID     = 'paid'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PAID,     'Paid'),
    ]

    candidate    = models.OneToOneField(
                       Candidate,
                       on_delete=models.CASCADE,
                       related_name='referral_bonus',
                   )
    referrer     = models.ForeignKey(
                       settings.AUTH_USER_MODEL,
                       on_delete=models.PROTECT,
                       related_name='referral_bonuses_earned',
                   )
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    approved_by  = models.ForeignKey(
                       settings.AUTH_USER_MODEL,
                       on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='referral_bonuses_approved',
                   )
    approved_at  = models.DateTimeField(null=True, blank=True)
    paid_by      = models.ForeignKey(
                       settings.AUTH_USER_MODEL,
                       on_delete=models.SET_NULL,
                       null=True, blank=True,
                       related_name='referral_bonuses_paid',
                   )
    paid_at      = models.DateTimeField(null=True, blank=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'referral_bonus'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.referrer.full_name} — {self.bonus_amount} ({self.status})'
