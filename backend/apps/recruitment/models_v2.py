"""
Phase 8A Task A — recruitment: requisitions, openings, pipelines,
CandidateProfile/Application split, interviews, scorecards, offers, BGV,
a rule-driven referral programme.

Scoped down from the master prompt's full scope, stated plainly:
- No duplicate-detection/merge tool (CandidateProfile has email/phone hash
  columns ready for it, but no merge UI/service is built this pass).
- No public careers-page endpoint, no screening-question Phase-2-layout
  wiring, no skills-on-opening (Skill master exists at
  apps.accounts.models_family_skills.Skill; not linked here).
- No consent/retention/anonymisation job (Task A.12) — flagged as a real,
  separate compliance feature, not attempted as an afterthought here.
- Scorecard "blind until submitted" visibility rule is a query-layer
  concern for whichever view reads Scorecard, not enforced by the model
  itself in this pass.
Everything here is additive — `Candidate`/`ReferralRule`/`ReferralBonus`
and every existing recruitment view/endpoint are completely untouched.
"""
import uuid

from django.db import models


class JobRequisition(models.Model):
    STATUS_DRAFT    = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_FILLED   = 'filled'
    STATUS_CLOSED   = 'closed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_APPROVED, 'Approved'),
        (STATUS_FILLED, 'Filled'), (STATUS_CLOSED, 'Closed'),
    ]
    REASON_NEW_POSITION = 'new_position'
    REASON_REPLACEMENT  = 'replacement'
    REASON_CHOICES = [(REASON_NEW_POSITION, 'New position'), (REASON_REPLACEMENT, 'Replacement')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=60, unique=True, blank=True)
    position = models.ForeignKey('accounts.Position', on_delete=models.PROTECT, related_name='job_requisitions')
    headcount = models.PositiveSmallIntegerField(default=1)
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default=REASON_NEW_POSITION)
    replaced_employee = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='requisitions_replacing',
    )
    target_start_date = models.DateField(null=True, blank=True)
    hiring_manager = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='requisitions_as_hiring_manager')
    justification = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='requisitions_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recruitment_job_requisitions_v2'
        ordering = ['-created_at']

    def __str__(self):
        return self.reference or str(self.id)


class JobOpening(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CLOSED    = 'closed'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published'), (STATUS_CLOSED, 'Closed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requisition = models.ForeignKey(JobRequisition, on_delete=models.CASCADE, related_name='openings')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_internal_only = models.BooleanField(default=False)
    closing_date = models.DateField(null=True, blank=True)
    pipeline_template = models.ForeignKey('recruitment.PipelineTemplate', on_delete=models.PROTECT, related_name='openings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recruitment_job_openings_v2'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class PipelineTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'recruitment_pipeline_templates_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class PipelineStage(models.Model):
    CATEGORY_ACTIVE    = 'active'
    CATEGORY_OFFER     = 'offer'
    CATEGORY_HIRED     = 'hired'
    CATEGORY_REJECTED  = 'rejected'
    CATEGORY_WITHDRAWN = 'withdrawn'
    CATEGORY_CHOICES = [
        (CATEGORY_ACTIVE, 'Active'), (CATEGORY_OFFER, 'Offer'), (CATEGORY_HIRED, 'Hired'),
        (CATEGORY_REJECTED, 'Rejected'), (CATEGORY_WITHDRAWN, 'Withdrawn'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(PipelineTemplate, on_delete=models.CASCADE, related_name='stages')
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=100)
    stage_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_ACTIVE)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'recruitment_pipeline_stages_v2'
        unique_together = [('template', 'code')]
        ordering = ['template', 'order']

    def __str__(self):
        return f'{self.template.code} › {self.code}'


class CandidateProfile(models.Model):
    """The PERSON, separate from an Application (person x opening) — so
    one real human can apply to multiple openings without duplicate
    candidate records. `legacy_candidate` links back to the one
    pre-existing `Candidate` row this profile was migrated from, where
    applicable (see services_recruitment.migrate_candidate_to_application)."""
    SOURCE_REFERRAL    = 'referral'
    SOURCE_CAREER_SITE = 'career_site'
    SOURCE_AGENCY      = 'agency'
    SOURCE_JOB_BOARD   = 'job_board'
    SOURCE_WALK_IN     = 'walk_in'
    SOURCE_OTHER       = 'other'
    SOURCE_CHOICES = [
        (SOURCE_REFERRAL, 'Referral'), (SOURCE_CAREER_SITE, 'Career site'), (SOURCE_AGENCY, 'Agency'),
        (SOURCE_JOB_BOARD, 'Job board'), (SOURCE_WALK_IN, 'Walk-in'), (SOURCE_OTHER, 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField()
    email_hash = models.CharField(max_length=64, db_index=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    phone_hash = models.CharField(max_length=64, db_index=True, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_OTHER)
    legacy_candidate = models.OneToOneField(
        'recruitment.Candidate', on_delete=models.SET_NULL, null=True, blank=True, related_name='profile_v2',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recruitment_candidate_profiles_v2'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        import hashlib
        self.email_hash = hashlib.sha256(self.email.strip().lower().encode()).hexdigest() if self.email else ''
        self.phone_hash = hashlib.sha256(self.phone.strip().encode()).hexdigest() if self.phone else ''
        super().save(*args, **kwargs)


class Application(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_profile = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='applications')
    opening = models.ForeignKey(JobOpening, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    # Legacy candidates with free-text position_applied and no real opening
    # get a per-branch "legacy opening" placeholder row — see
    # services_recruitment's migration function; this stays None for those.
    current_stage = models.ForeignKey(PipelineStage, on_delete=models.PROTECT, related_name='applications')
    legacy_candidate = models.OneToOneField(
        'recruitment.Candidate', on_delete=models.SET_NULL, null=True, blank=True, related_name='application_v2',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recruitment_applications_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.candidate_profile.name} -> {self.opening or "legacy"}'

    @property
    def is_closed(self) -> bool:
        return self.current_stage.stage_category in (
            PipelineStage.CATEGORY_HIRED, PipelineStage.CATEGORY_REJECTED, PipelineStage.CATEGORY_WITHDRAWN,
        )


class InterviewRound(models.Model):
    STATUS_SCHEDULED = 'scheduled'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [(STATUS_SCHEDULED, 'Scheduled'), (STATUS_COMPLETED, 'Completed'), (STATUS_CANCELLED, 'Cancelled')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interview_rounds')
    round_type = models.CharField(max_length=60)
    mode = models.CharField(max_length=20, default='in_person')
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField(null=True, blank=True)
    meeting_link = models.URLField(max_length=500, blank=True)
    panel = models.ManyToManyField('accounts.User', related_name='interview_rounds_on_panel', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recruitment_interview_rounds_v2'
        ordering = ['scheduled_start']

    def __str__(self):
        return f'{self.application_id} — {self.round_type}'


class ScorecardTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    # [{"criterion": "Communication", "weight": 30}, ...] — weights sum to 100, validated in services_recruitment.
    criteria = models.JSONField(default=list)

    class Meta:
        db_table = 'recruitment_scorecard_templates_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class Scorecard(models.Model):
    RECOMMENDATION_STRONG_YES = 'strong_yes'
    RECOMMENDATION_YES        = 'yes'
    RECOMMENDATION_NO         = 'no'
    RECOMMENDATION_STRONG_NO  = 'strong_no'
    RECOMMENDATION_CHOICES = [
        (RECOMMENDATION_STRONG_YES, 'Strong yes'), (RECOMMENDATION_YES, 'Yes'),
        (RECOMMENDATION_NO, 'No'), (RECOMMENDATION_STRONG_NO, 'Strong no'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview_round = models.ForeignKey(InterviewRound, on_delete=models.CASCADE, related_name='scorecards')
    template = models.ForeignKey(ScorecardTemplate, on_delete=models.PROTECT, related_name='scorecards')
    interviewer = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='scorecards_submitted')
    # {"Communication": 8, ...} — per-criterion score 1-10, validated against template.criteria in services_recruitment.
    scores = models.JSONField(default=dict)
    overall_recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, blank=True)
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'recruitment_scorecards_v2'
        unique_together = [('interview_round', 'interviewer')]

    def __str__(self):
        return f'{self.interview_round_id} by {self.interviewer_id}'


class Offer(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_APPROVED  = 'approved'
    STATUS_SENT      = 'sent'
    STATUS_ACCEPTED  = 'accepted'
    STATUS_DECLINED  = 'declined'
    STATUS_EXPIRED   = 'expired'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_APPROVED, 'Approved'), (STATUS_SENT, 'Sent'),
        (STATUS_ACCEPTED, 'Accepted'), (STATUS_DECLINED, 'Declined'), (STATUS_EXPIRED, 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='offers')
    version = models.PositiveSmallIntegerField(default=1)
    pay_structure = models.ForeignKey('payroll.PayStructure', on_delete=models.SET_NULL, null=True, blank=True, related_name='offers')
    annual_ctc = models.DecimalField(max_digits=12, decimal_places=2)
    joining_date = models.DateField()
    position = models.ForeignKey('accounts.Position', on_delete=models.PROTECT, related_name='offers')
    expiry_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='offers_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recruitment_offers_v2'
        unique_together = [('application', 'version')]
        ordering = ['-version']

    def __str__(self):
        return f'{self.application_id} v{self.version} ({self.status})'


class BGVCheck(models.Model):
    CHECK_IDENTITY   = 'identity'
    CHECK_EDUCATION  = 'education'
    CHECK_EMPLOYMENT = 'employment'
    CHECK_ADDRESS    = 'address'
    CHECK_CRIMINAL   = 'criminal'
    CHECK_TYPE_CHOICES = [
        (CHECK_IDENTITY, 'Identity'), (CHECK_EDUCATION, 'Education'), (CHECK_EMPLOYMENT, 'Employment'),
        (CHECK_ADDRESS, 'Address'), (CHECK_CRIMINAL, 'Criminal'),
    ]
    STATUS_PENDING   = 'pending'
    STATUS_CLEAR     = 'clear'
    STATUS_FLAGGED   = 'flagged'
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'), (STATUS_CLEAR, 'Clear'), (STATUS_FLAGGED, 'Flagged')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='bgv_checks')
    check_type = models.CharField(max_length=20, choices=CHECK_TYPE_CHOICES)
    vendor_code = models.CharField(max_length=40, blank=True, help_text='Integration interface only — no real vendor API call is made.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    result_note = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'recruitment_bgv_checks_v2'
        unique_together = [('application', 'check_type')]

    def __str__(self):
        return f'{self.application_id} — {self.check_type} ({self.status})'


class ReferralProgramRule(models.Model):
    """Rule-driven replacement for ReferralBonus's flat bonus_amount — one
    active rule resolves the bonus amount and payout schedule for a new
    referral; ReferralBonus itself is untouched (still the real payout
    record), this is additive configuration consumed by
    services_recruitment.resolve_referral_bonus_amount()."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_days_after_join = models.PositiveSmallIntegerField(default=90)
    # Optional second tranche — [] = single payout. {"days_after_join": 30, "percent": 50} per tranche.
    payout_tranches = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'recruitment_referral_program_rules_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class RecruitmentV2Entitlement(models.Model):
    """Phase 8A Task E — recruitment.v2 flag, default OFF. Same pattern as
    Phase 7A/7B's PayrollV2Entitlement/PayrollOpsV2Entitlement."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'recruitment_v2_entitlement_v2'

    def __str__(self):
        return f'recruitment.v2: {"ON" if self.is_enabled else "off"}'
