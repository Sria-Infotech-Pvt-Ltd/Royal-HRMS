"""
Database connection tuning for LOCAL DEBUG development only.

Why this exists: the local dev server (Daphne/ASGI) talks to a remote Neon database over the public internet. Measured with
the project's own Django (5.1): every ASGI request runs in its own thread, so a "persistent" connection is never reused and
each request pays a fresh TLS connect (~0.8-1.0 s), and nothing bounds how long a connect may hang when the link stalls.

Everything here is a no-op unless `debug` is true, so production and UAT keep exactly the settings they have today. It is
kept as pure functions (no Django import) so the "DEBUG-only" guarantee is unit-tested (core/tests_db_settings.py).
"""
from __future__ import annotations

# Production/UAT value, unchanged from before this module existed.
DEFAULT_CONN_MAX_AGE_SECONDS = 60

# libpq connection parameters applied in DEBUG only.
#  connect_timeout  — give up on one address after this long instead of the OS default (~20 s+ on Windows), so a stalled
#                     link fails inside the browser's 15 s request window and libpq can try the next address (IPv4/IPv6).
#  keepalives*      — the OS sends TCP probes on an idle connection and drops it as dead after
#                     idle + interval * count = 30 + 10 * 3 = 60 s, instead of waiting forever on a half-open socket.
LOCAL_DEBUG_CONNECT_TIMEOUT_SECONDS = 10
LOCAL_DEBUG_KEEPALIVE_OPTIONS = {
    'keepalives': 1,
    'keepalives_idle': 30,
    'keepalives_interval': 10,
    'keepalives_count': 3,
}


def default_conn_max_age(debug: bool) -> int:
    """How long a connection may be kept open when DB_CONN_MAX_AGE is not set.

    DEBUG: 0 = close at the end of every request. Under ASGI a connection is tied to the request's thread and is not reused
    by the next request anyway, so keeping it open for 60 s only leaves an idle socket for the server to cut. An explicit
    DB_CONN_MAX_AGE in the environment always wins over this default."""
    return 0 if debug else DEFAULT_CONN_MAX_AGE_SECONDS


def apply_local_debug_options(options: dict, *, debug: bool) -> dict:
    """Add the DEBUG-only libpq options to a DATABASES[...]['OPTIONS'] dict (in place) and return it.

    Uses setdefault, so anything already set (for example by the DATABASE_URL query string) is left alone."""
    if not debug:
        return options
    options.setdefault('connect_timeout', LOCAL_DEBUG_CONNECT_TIMEOUT_SECONDS)
    for name, value in LOCAL_DEBUG_KEEPALIVE_OPTIONS.items():
        options.setdefault(name, value)
    return options


def health_checks_enabled(debug: bool, conn_max_age: int) -> bool:
    """CONN_HEALTH_CHECKS pings a kept-open connection before reusing it. It only matters when connections are kept open
    (conn_max_age > 0, i.e. someone set DB_CONN_MAX_AGE locally), so it is switched on then, and only in DEBUG."""
    return bool(debug and conn_max_age > 0)
