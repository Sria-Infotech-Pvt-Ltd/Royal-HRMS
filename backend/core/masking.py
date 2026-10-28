"""Masking for values shown on screen: enough to recognise the person, never the full address."""


def mask_email(address: str) -> str:
    """'rahul.sharma@example.com' -> 'r***@example.com'; blank stays blank."""
    local, separator, domain = (address or '').partition('@')
    if not separator or not local:
        return ''
    return f'{local[0]}***@{domain}'
