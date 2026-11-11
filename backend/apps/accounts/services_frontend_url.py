"""
The public web address of the frontend, used to build links that are emailed to people (account activation).

Why this exists: the activation link used to be `Company.portal_url + '/activate/<token>/'` with no check on the stored value. When
the value was blank (no Company row, or the field empty) the email carried the bare path `/activate/<token>/`, and a value such as
`http://` produced `http:/activate/<token>/`; mail clients and browsers turn both into `http://activate/<token>/`, a host called
"activate". Nothing in the system noticed, because the email was still "sent".

Now the address is checked every time a link is built. If it is missing or not a usable web address, building the link fails with
PortalUrlNotConfigured BEFORE anything is changed or sent, so no broken email can leave the system.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from django.conf import settings

LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


class PortalUrlNotConfigured(RuntimeError):
    """The company's portal URL is missing or not a usable web address. The message is safe to show to an administrator."""


def check_portal_url(value: str) -> str:
    """The cleaned address (no trailing slash) or ValueError saying what is wrong. Blank is an error here; callers that allow an
    administrator to clear the setting handle blank themselves."""
    raw = (value or '').strip()
    if not raw:
        raise ValueError('The portal URL is empty.')
    if any(character.isspace() for character in raw):
        raise ValueError('The portal URL must not contain spaces.')
    parts = urlsplit(raw)
    if parts.scheme not in ('http', 'https'):
        raise ValueError('The portal URL must start with https://, for example https://aira.nxsys.in.')
    host = (parts.hostname or '').lower()
    if not host:
        raise ValueError('The portal URL must include the website name, for example https://aira.nxsys.in.')
    if host not in LOCAL_HOSTS and '.' not in host:
        raise ValueError('The portal URL must be a full website name such as aira.nxsys.in, not a single word.')
    if parts.query or parts.fragment:
        raise ValueError('The portal URL must not contain ? or # parts.')
    # Plain http is for local development only: localhost, and only while DEBUG is on. Anything else must be https.
    if parts.scheme == 'http' and not (host in LOCAL_HOSTS and settings.DEBUG):
        raise ValueError('The portal URL must use https://. Plain http:// is only allowed for localhost during development.')
    return f'{parts.scheme}://{parts.netloc}{parts.path.rstrip("/")}'


def frontend_origin() -> str:
    """The checked portal address from the company settings. Raises PortalUrlNotConfigured when it cannot be used."""
    from apps.accounts.models import Company

    company = Company.objects.first()
    value = company.portal_url if company else ''
    if not (value or '').strip():
        raise PortalUrlNotConfigured('The company portal URL is not set. An administrator must set it in Company settings before invitation links can be sent.')
    try:
        return check_portal_url(value)
    except ValueError as exc:
        raise PortalUrlNotConfigured(f'The company portal URL cannot be used: {exc}') from exc


def frontend_url(path: str) -> str:
    """Absolute link to `path` (which must start with "/") on the frontend."""
    if not path.startswith('/'):
        raise ValueError('path must start with "/"')
    return f'{frontend_origin()}{path}'
