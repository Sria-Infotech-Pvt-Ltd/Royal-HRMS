"""
Read-only report on how hard face clock-in/out currently is, and which
employees' registered face references are marginal.

Two data sources, because neither alone answers "why 4-5 tries":
  * FaceCaptureTelemetry   — client-side sessions: tries, time, which gate failed, device/FPS.
  * FaceVerificationAttempt — server-side match attempts: distance distribution per employee.

Employees are listed by employee_id only (no names/emails) — the output is
meant to be pasted into tickets and chats.

Usage:
    python manage.py face_clockin_report --schema tenant_demo2026
    python manage.py face_clockin_report --company-code DEMO2026 --days 14
    python manage.py face_clockin_report --all --days 30 --weak-median 0.50
"""
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import median

from django.utils import timezone

from core.tenant_command import TenantCommand

# Targets agreed for the retry-reduction work (see project notes).
TARGET_FIRST_TRY_RATE = 0.90
TARGET_MEDIAN_SECONDS = 10


def _pct(part: int, whole: int) -> str:
    return f'{(100.0 * part / whole):.1f}%' if whole else 'n/a'


class Command(TenantCommand):
    help = 'Read-only report: face clock-in effort (tries/time/gates) and weak face registrations.'

    def add_tenant_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Look-back window in days (default 30).')
        parser.add_argument(
            '--weak-median', type=float, default=0.50,
            help='Flag an employee when their median genuine-match distance is at or above this (default 0.50; the hard threshold is 0.60).',
        )
        parser.add_argument('--min-attempts', type=int, default=3, help='Minimum matched attempts before judging an employee (default 3).')

    def handle_tenant(self, client, *args, **options):
        from apps.attendance.models import FaceCaptureTelemetry, FaceVerificationAttempt

        since = timezone.now() - timedelta(days=options['days'])
        self.stdout.write(f'  Window: last {options["days"]} day(s)')

        self._telemetry_section(FaceCaptureTelemetry, since)
        self._attempts_section(FaceVerificationAttempt, since, options['weak_median'], options['min_attempts'])

    # ── client-side sessions ────────────────────────────────────────────────
    def _telemetry_section(self, model, since):
        rows = list(model.objects.filter(purpose='verify', created_at__gte=since))
        self.stdout.write('\n  [Client telemetry: punch verification sessions]')
        if not rows:
            self.stdout.write('    No telemetry yet — it fills in once the new frontend is deployed and used.')
            return

        # A "punch attempt" for an employee = a run of sessions ending in a capture.
        # Simplest honest measure available per session: how many tries (manual
        # retries + auto resumes) it needed before it captured.
        captured = [r for r in rows if r.outcome == 'captured']
        first_try = [r for r in captured if r.manual_retries == 0 and r.auto_resumes == 0]
        durations = [r.duration_ms / 1000 for r in captured]
        fps = [r.avg_fps for r in rows if r.avg_fps]

        self.stdout.write(f'    Sessions:                {len(rows)}')
        self.stdout.write(f'    Ended in a capture:      {len(captured)} ({_pct(len(captured), len(rows))})')
        rate = len(first_try) / len(captured) if captured else 0
        self.stdout.write(
            f'    First-try success:       {_pct(len(first_try), len(captured))} of captures '
            f'(target >= {TARGET_FIRST_TRY_RATE:.0%}) {"OK" if rate >= TARGET_FIRST_TRY_RATE else "BELOW TARGET"}'
        )
        three_plus = [r for r in captured if (r.manual_retries + r.auto_resumes) >= 2]
        self.stdout.write(f'    Needed 3+ tries:         {_pct(len(three_plus), len(captured))} (target < 2%)')
        if durations:
            med = median(durations)
            self.stdout.write(
                f'    Median time to capture:  {med:.1f}s (target <= {TARGET_MEDIAN_SECONDS}s) '
                f'{"OK" if med <= TARGET_MEDIAN_SECONDS else "ABOVE TARGET"}'
            )
        if fps:
            self.stdout.write(f'    Detection FPS:           median {median(fps):.1f}, {_pct(sum(1 for f in fps if f < 8), len(fps))} of sessions under 8 fps')

        backends = Counter(r.tf_backend or 'unknown' for r in rows)
        self.stdout.write('    TF backend:              ' + ', '.join(f'{k}={v}' for k, v in backends.most_common()))

        reasons: Counter = Counter()
        signals: Counter = Counter()
        for r in rows:
            d = r.details or {}
            for key, count in (d.get('failure_reasons') or {}).items():
                if isinstance(count, int):
                    reasons[key] += count
            for key in ('liveness_timeouts', 'blink_seen', 'turn_seen'):
                if isinstance(d.get(key), int):
                    signals[key] += d[key]
        if reasons:
            self.stdout.write('    What blocked captures (count of rejected frames/attempts):')
            for key, count in reasons.most_common(10):
                self.stdout.write(f'      - {key}: {count}')
        if signals:
            self.stdout.write(
                f'    Liveness: timeouts={signals["liveness_timeouts"]}, '
                f'sessions where a blink was seen={signals["blink_seen"]}, head turn seen={signals["turn_seen"]}'
            )

        by_device: defaultdict = defaultdict(lambda: [0, 0])
        for r in captured:
            ua = r.user_agent or ''
            family = ('Android' if 'Android' in ua else 'iPhone/iPad' if ('iPhone' in ua or 'iPad' in ua)
                      else 'Windows' if 'Windows' in ua else 'Mac' if 'Macintosh' in ua else 'Other')
            by_device[family][0] += 1
            if r.manual_retries == 0 and r.auto_resumes == 0:
                by_device[family][1] += 1
        if by_device:
            self.stdout.write('    First-try success by platform:')
            for family, (total, ok) in sorted(by_device.items(), key=lambda kv: -kv[1][0]):
                self.stdout.write(f'      - {family}: {_pct(ok, total)} of {total}')

    # ── server-side matches ─────────────────────────────────────────────────
    def _attempts_section(self, model, since, weak_median, min_attempts):
        from django.db.models import Count, Q

        attempts = model.objects.filter(created_at__gte=since)
        self.stdout.write('\n  [Server-side match attempts]')
        total = attempts.count()
        if not total:
            self.stdout.write('    No attempts in this window.')
            return

        matched = attempts.filter(is_match=True).count()
        self.stdout.write(f'    Attempts: {total}, matched: {matched} ({_pct(matched, total)})')
        reasons = (
            attempts.filter(is_match=False).values('rejection_reason')
            .annotate(n=Count('id')).order_by('-n')
        )
        for row in reasons:
            self.stdout.write(f'      - rejected "{row["rejection_reason"] or "mismatch"}": {row["n"]}')

        per_employee: defaultdict = defaultdict(list)
        low_conf: Counter = Counter()
        failed: Counter = Counter()
        for emp_id, ok, dist, reason in attempts.values_list(
            'employee__employee_id', 'is_match', 'distance', 'rejection_reason',
        ):
            key = emp_id or 'unknown'
            if ok and dist is not None:
                per_employee[key].append(dist)
            if not ok:
                failed[key] += 1
            if reason == 'low_confidence_pending':
                low_conf[key] += 1

        weak = []
        for emp, dists in per_employee.items():
            if len(dists) < min_attempts:
                continue
            med = median(dists)
            if med >= weak_median or low_conf[emp] > 0:
                weak.append((emp, med, max(dists), len(dists), low_conf[emp], failed[emp]))
        weak.sort(key=lambda r: (-r[4], -r[1]))

        self.stdout.write(
            f'\n  [Weak face references] employees with median matched distance >= {weak_median} '
            f'(hard limit 0.60) or any 0.55-0.60 rejection: {len(weak)}'
        )
        self.stdout.write('    These are the only employees who should be asked to re-register.')
        for emp, med, worst, n, lc, fails in weak[:100]:
            self.stdout.write(
                f'      - {emp}: median={med:.3f} worst={worst:.3f} matched={n} low_conf_rejects={lc} failed_total={fails}'
            )
        if len(weak) > 100:
            self.stdout.write(f'      … and {len(weak) - 100} more')

        capped = attempts.filter(rejection_reason='attempt_cap_exceeded').values('employee').distinct().count()
        self.stdout.write(f'\n  Employees who hit the failed-attempt lockout in this window: {capped}')
