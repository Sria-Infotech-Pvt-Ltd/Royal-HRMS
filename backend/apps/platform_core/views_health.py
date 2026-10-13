"""
Phase 9B Task G — observability: a real liveness/readiness check hitting
the actual DB connection (not just "process is up"), unauthenticated by
design (this is what a load balancer / uptime monitor polls, same
convention as every standard health-check endpoint — no PII, no business
data, just a boolean + latency).

Scoped down, stated plainly: this is one check (DB connectivity) rather
than a full dependency graph (Celery broker, SMTP, external APIs) — those
are flagged here as the natural next additions, not silently omitted.
"""
import time

from django.db import connections
from django.db.utils import OperationalError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.responses import error, success


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        checks = {}
        overall_ok = True

        start = time.monotonic()
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            checks['database'] = {'ok': True, 'latency_ms': round((time.monotonic() - start) * 1000, 2)}
        except OperationalError as exc:
            checks['database'] = {'ok': False, 'error': str(exc)}
            overall_ok = False

        data = {'status': 'ok' if overall_ok else 'degraded', 'checks': checks}
        if overall_ok:
            return success('Service healthy.', data)
        return error('Service degraded.', data, http_status=503)
