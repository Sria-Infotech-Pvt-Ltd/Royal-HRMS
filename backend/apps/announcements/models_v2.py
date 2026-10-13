"""
Phase 8B Task D — announcement audience rules (replacing single
target_org_unit/target_branch with a rule an admin can edit) and
acknowledgement tracking. `Announcement`/`AnnouncementReaction` are
untouched; `visibility`/`target_org_unit`/`target_branch` stay populated
and are migrated verbatim into an equivalent AnnouncementAudienceRule —
see services_announcements_v2.migrate_visibility_to_rule(), which resolves
the SAME recipient set both ways (proven by test).

Scoped down: no scheduling/expiry/draft/approval-workflow (Task D.2), no
translations (Task D.6) — audience-rule migration and acknowledgement
tracking are the two pieces this pass builds and verifies.
"""
import uuid

from django.db import models


class AnnouncementAudienceRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.OneToOneField('announcements.Announcement', on_delete=models.CASCADE, related_name='audience_rule')
    # {"legal_entity_ids": [...], "branch_ids": [...], "org_unit_ids": [...], "grade_codes": [...]}
    # empty list for a key = no filter on that dimension. {} entirely = everyone (matches visibility='all').
    rule = models.JSONField(default=dict, blank=True)
    requires_acknowledgement = models.BooleanField(default=False)
    acknowledgement_due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'announcements_audience_rules_v2'

    def __str__(self):
        return f'Audience for {self.announcement_id}'


class AnnouncementSchedule(models.Model):
    """Phase 8B gap-closure — publish_at/expire_at/pinned_until, drafts.
    An Announcement with a schedule row and publish_at in the future is a
    DRAFT until that time; services_announcements_gaps.visible_announcements()
    is what actually filters by this, not Announcement's own queryset."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.OneToOneField('announcements.Announcement', on_delete=models.CASCADE, related_name='schedule')
    publish_at = models.DateTimeField(null=True, blank=True)
    expire_at = models.DateTimeField(null=True, blank=True)
    pinned_until = models.DateTimeField(null=True, blank=True)
    is_draft = models.BooleanField(default=False)

    class Meta:
        db_table = 'announcements_schedules_v2'

    def __str__(self):
        return f'Schedule for {self.announcement_id}'


class AnnouncementTranslation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey('announcements.Announcement', on_delete=models.CASCADE, related_name='translations')
    language_code = models.CharField(max_length=10)
    title = models.CharField(max_length=300)
    body = models.TextField()

    class Meta:
        db_table = 'announcements_translations_v2'
        unique_together = [('announcement', 'language_code')]

    def __str__(self):
        return f'{self.announcement_id} [{self.language_code}]'


class AnnouncementAcknowledgement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    announcement = models.ForeignKey('announcements.Announcement', on_delete=models.CASCADE, related_name='acknowledgements')
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='announcement_acknowledgements')
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'announcements_acknowledgements_v2'
        unique_together = [('announcement', 'employee')]

    def __str__(self):
        return f'{self.employee_id} ack {self.announcement_id}'
