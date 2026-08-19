"""
Tenant-qualified Channels group name for per-user WebSocket notifications.

apps.notifications.consumers.NotificationConsumer joins one group per user
id — but that id (an auto-increment PK) is only unique within a company's
own schema, not globally. Without the schema name folded into the group
name, two companies' user #5 join the exact same Channels group, and a
notification/attendance/leave push meant for one company's employee is
broadcast straight into the other company's same-numbered employee's open
browser tab too. Every group_send/group_add site for this group must use
this same helper so sender and consumer always agree on the name.
"""
from django.db import connection


def notification_group_name(user_id, schema_name: str | None = None) -> str:
    """
    `schema_name` should be passed explicitly by callers on the async side of
    a sync/async boundary (e.g. a Channels consumer reading it back from
    `scope`, set once by the WS auth middleware) rather than trusting
    `connection.schema_name` to have propagated correctly across that
    boundary. Plain synchronous Django request/task/signal contexts can omit
    it and rely on the `connection` fallback below, same as
    core.cache_keys.tenant_aware_key_func.
    """
    if not schema_name:
        schema_name = getattr(connection, 'schema_name', None) or '__no_tenant__'
    return f'notifications_{schema_name}_{user_id}'
