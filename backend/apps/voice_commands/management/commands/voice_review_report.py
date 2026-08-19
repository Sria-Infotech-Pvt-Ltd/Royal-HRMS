"""
Read-only report over apps.accounts.models.AuditLog's voice_commands rows —
the same table (and the same models.Index(fields=['module', 'created_at']),
auditlog_module_created_idx) every other voice audit event already writes to
via apps/voice_commands/audit.py. No new storage and no new endpoint: a
management command is the plainest fit for something that "doesn't need a
UI" and only needs running occasionally by a human reviewing recent traffic.

Two sections:

1. No-match transcripts, clustered by fuzzy similarity. Exact-match grouping
   would badly undercount — real speech varies word-for-word every time
   ("clock in from home" vs "clock in from home please"). Clustering uses
   rapidfuzz.fuzz.token_set_ratio over normalize_transcript()'d text — the
   same fuzzy-matching library apps/voice_commands/matcher.py already uses
   for intent matching, just a looser scorer: token_set_ratio tolerates one
   phrase being a subset/superset of another, which suits grouping loosely-
   related freeform phrasing better than matcher.py's token_sort_ratio
   (scored against a fixed, curated phrase list instead of other freeform
   text). This only catches near-duplicate phrasing (word order, filler
   words, minor variation) — it does NOT catch synonym-level semantic
   similarity ("clock me in" vs "punch me in"), which would need embeddings,
   a new external dependency this command deliberately doesn't add for a v1.

2. Clarification outcomes — confirmed / declined / re-asked / abandoned —
   per flavor (rule_engine / llm / stt), reconstructed entirely from the
   start and outcome audit rows each flow already writes (ACTION_NO_MATCH
   with a candidate_intent, ACTION_LLM_FALLBACK_USED below the LLM tier's
   own clarification threshold, ACTION_STT_CONFIRMATION_STARTED, and
   ACTION_CLARIFICATION_OUTCOME) — no new tracking beyond those rows.
   apps.voice_commands.clarification stores at most one pending
   clarification per user at a time (one Redis key), so a user's start/
   outcome rows can be reconciled in plain chronological order: a start
   with no confirmed/declined outcome before either the next start for that
   same user or the end of the report window is counted as abandoned —
   there's no eviction callback on the Redis TTL to hook a direct
   "abandoned" event off of, so this is inferred rather than logged.

The no-match cluster section below prints VERBATIM transcript text — real
employee speech/typed input, which has been observed in practice to include
a spoken name or other personal detail (not hypothetical — see this
feature's own real-data threshold-calibration comments elsewhere in this
app). This output is for internal engineering review only; the command
prints a reminder of that above the cluster section, and it should not be
pasted into an external ticket, chat, or doc without redacting names/
personal details first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from rapidfuzz import fuzz

from apps.accounts.models import AuditLog
from apps.voice_commands.audit import (
    ACTION_CLARIFICATION_OUTCOME,
    ACTION_LLM_FALLBACK_USED,
    ACTION_NO_MATCH,
    ACTION_STT_CONFIRMATION_STARTED,
    MODULE,
)
from apps.voice_commands.llm_fallback import _LLM_CLARIFICATION_THRESHOLD
from apps.voice_commands.normalizer import normalize_transcript

# Below this rapidfuzz score (0-100) a no-match transcript starts its own new
# cluster instead of joining the closest existing one. NOT calibrated against
# real transcript volume yet — a starting point only, same discipline as
# every other threshold in this feature (see conversation.py's
# STT_CONFIRM_THRESHOLD / llm_fallback.py's _LLM_CLARIFICATION_THRESHOLD).
CLUSTER_SIMILARITY_THRESHOLD = 80

_SENSITIVE_DATA_NOTICE = (
    'NOTE: the no-match cluster section below prints verbatim employee '
    'transcripts — real speech/typed input that has been observed to include '
    'spoken names or other personal details. Internal engineering review '
    'only; redact before sharing outside the team.'
)

_CLARIFICATION_TYPES = ('rule_engine', 'llm', 'stt')
_TERMINAL_OUTCOMES = frozenset({'confirmed', 'declined'})
_OUTCOME_DISPLAY_ORDER = ('confirmed', 'declined', 're_asked', 'abandoned')


class Command(BaseCommand):
    help = (
        'Voice-commands review report: clusters recent no-match transcripts by '
        'similarity, and summarizes clarification outcomes (confirmed/declined/'
        're-asked/abandoned) per flavor (rule_engine/llm/stt).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Report window in days (default: 7).')

    def handle(self, *args, **options):
        days = options['days']
        window_start = timezone.now() - timedelta(days=days)

        self.stdout.write(self.style.MIGRATE_HEADING(f'Voice review report — last {days} day(s)'))
        self.stdout.write(self.style.WARNING(_SENSITIVE_DATA_NOTICE))
        self._report_no_match_clusters(window_start)
        self._report_clarification_outcomes(window_start)

    def _report_no_match_clusters(self, window_start):
        changes_list = AuditLog.objects.filter(
            module=MODULE, action=ACTION_NO_MATCH, created_at__gte=window_start,
        ).values_list('changes', flat=True)
        transcripts = [changes.get('transcript') for changes in changes_list if changes.get('transcript')]

        clusters = _cluster_transcripts(transcripts)
        clusters.sort(key=lambda cluster: len(cluster['variants']), reverse=True)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nNo-match clusters — {len(transcripts)} transcript(s), {len(clusters)} cluster(s)',
        ))
        for cluster in clusters:
            self.stdout.write(f"  [{len(cluster['variants'])}x] {cluster['representative']!r}")
            for variant in cluster['variants']:
                if variant != cluster['representative']:
                    self.stdout.write(f'        - {variant!r}')

    def _report_clarification_outcomes(self, window_start):
        rows = AuditLog.objects.filter(
            module=MODULE,
            action__in=(
                ACTION_NO_MATCH, ACTION_LLM_FALLBACK_USED,
                ACTION_STT_CONFIRMATION_STARTED, ACTION_CLARIFICATION_OUTCOME,
            ),
            created_at__gte=window_start,
        ).order_by('created_at').values('user_id', 'action', 'changes')

        events_by_user = defaultdict(list)
        for row in rows:
            event = _classify_event(row)
            if event is not None:
                events_by_user[row['user_id']].append(event)

        stats = {clarification_type: defaultdict(int) for clarification_type in _CLARIFICATION_TYPES}
        confidence_pairs = {'llm': [], 'stt': []}
        for user_events in events_by_user.values():
            _reconcile_user_events(user_events, stats, confidence_pairs)

        self.stdout.write(self.style.MIGRATE_HEADING('\nClarification outcomes by type'))
        for clarification_type in _CLARIFICATION_TYPES:
            counts = stats[clarification_type]
            self.stdout.write(f"  {clarification_type}: {counts['started']} started")
            for outcome in _OUTCOME_DISPLAY_ORDER:
                self.stdout.write(f'    {outcome}: {counts[outcome]}')

        for clarification_type in ('llm', 'stt'):
            pairs = confidence_pairs[clarification_type]
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'\n{clarification_type} confidence/outcome pairs — {len(pairs)}, for threshold tuning',
            ))
            for confidence, outcome in pairs:
                self.stdout.write(f'  confidence={confidence} -> {outcome}')


def _cluster_transcripts(transcripts: list[str]) -> list[dict]:
    """
    Greedy single-pass clustering: each transcript joins the closest existing
    cluster if it scores above CLUSTER_SIMILARITY_THRESHOLD against that
    cluster's representative (the first transcript that started it),
    otherwise it starts a new cluster. O(n * clusters), fine at review-report
    scale — this is not a hot path.
    """
    clusters: list[dict] = []
    for transcript in transcripts:
        normalized = normalize_transcript(transcript)
        if not normalized:
            continue

        best_cluster, best_score = None, 0
        for cluster in clusters:
            score = fuzz.token_set_ratio(normalized, cluster['normalized'])
            if score > best_score:
                best_cluster, best_score = cluster, score

        if best_cluster is not None and best_score >= CLUSTER_SIMILARITY_THRESHOLD:
            best_cluster['variants'].append(transcript)
        else:
            clusters.append({'normalized': normalized, 'representative': transcript, 'variants': [transcript]})

    return clusters


def _classify_event(row: dict) -> dict | None:
    """
    Reduce one AuditLog row to {'kind': 'start'|'outcome', 'type': ..., ...}
    for _reconcile_user_events, or None if this row isn't a clarification
    event at all (e.g. a flat no-match with no candidate_intent, or an
    LLM-fallback row that dispatched directly instead of asking).
    """
    action = row['action']
    changes = row['changes'] or {}

    if action == ACTION_NO_MATCH:
        if not changes.get('candidate_intent'):
            return None
        return {'kind': 'start', 'type': 'rule_engine', 'confidence': changes.get('confidence')}

    if action == ACTION_LLM_FALLBACK_USED:
        confidence = changes.get('confidence')
        # Only a low-confidence classification actually goes through
        # start_clarification (see llm_fallback.try_llm_fallback) — every
        # other LLM_FALLBACK_USED row (rejected, or a confident direct
        # dispatch) is not a clarification start at all.
        if not changes.get('resolved_intent') or confidence is None or confidence >= _LLM_CLARIFICATION_THRESHOLD:
            return None
        return {'kind': 'start', 'type': 'llm', 'confidence': confidence}

    if action == ACTION_STT_CONFIRMATION_STARTED:
        return {'kind': 'start', 'type': 'stt', 'confidence': changes.get('language_probability')}

    if action == ACTION_CLARIFICATION_OUTCOME:
        return {'kind': 'outcome', 'type': changes.get('clarification_type'), 'outcome': changes.get('outcome')}

    return None


def _reconcile_user_events(events: list[dict], stats: dict, confidence_pairs: dict) -> None:
    """
    Walk one user's events in chronological order, one open clarification
    slot per type (mirrors the real Redis pending-state invariant: at most
    one pending clarification per user at a time). A new start while one is
    already open means the previous one was abandoned (superseded, e.g. by a
    confident new command — see conversation.py's own abandon branch).
    Anything still open once this user's events run out is also abandoned —
    it neither resolved nor got superseded before the report window ended.
    """
    open_start: dict[str, dict] = {}

    for event in events:
        clarification_type = event['type']
        if clarification_type not in stats:
            continue

        if event['kind'] == 'start':
            if clarification_type in open_start:
                stats[clarification_type]['abandoned'] += 1
            stats[clarification_type]['started'] += 1
            open_start[clarification_type] = event
            continue

        outcome = event['outcome']
        if outcome not in ('confirmed', 'declined', 're_asked'):
            continue
        stats[clarification_type][outcome] += 1
        if outcome in _TERMINAL_OUTCOMES:
            start = open_start.pop(clarification_type, None)
            if start is not None and clarification_type in confidence_pairs:
                confidence_pairs[clarification_type].append((start['confidence'], outcome))

    for clarification_type, start in open_start.items():
        stats[clarification_type]['abandoned'] += 1
