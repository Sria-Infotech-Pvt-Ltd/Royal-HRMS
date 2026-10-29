import uuid

from django.conf import settings
from django.db import models


class PermissionTemplate(models.Model):
    """A named, reusable permission bundle (e.g. "Manager", "HR Admin") that
    can be applied to any number of Positions in one action — the bulk
    alternative to editing each position's own permissions one at a time
    (PositionPermission / PositionPermissionsView). Applying a template
    doesn't link the position to it afterward: it's a one-time stamp, not a
    live binding — editing the template later does NOT retroactively change
    positions it was already applied to (same reasoning the org-wide "Roles"
    removal settled on: access follows the seat's own stored permissions,
    never a reference that could silently change what someone can do)."""
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.ManyToManyField('accounts.Permission', blank=True, related_name='templates')
    can_manage_team   = models.BooleanField(default=False)
    can_manage_branch = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )

    class Meta:
        db_table = 'hrms_permission_templates'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name
