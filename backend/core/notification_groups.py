"""
Channels group name for per-user WebSocket notifications.

Every group_send/group_add site for this group must use this same helper
so sender and consumer always agree on the name.
"""


def notification_group_name(user_id) -> str:
    return f'notifications_{user_id}'
