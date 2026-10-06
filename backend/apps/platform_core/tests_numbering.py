"""Phase 1 Task G — number-series allocation tests, including the
required concurrency test (no duplicates under concurrent callers)."""
from __future__ import annotations

import threading

from django.db import connection
from django.test import TransactionTestCase

from apps.platform_core import services_numbering as numbering
from apps.platform_core.models import NumberSeries


class NumberSeriesAllocationTests(TransactionTestCase):
    def setUp(self):
        self.series = NumberSeries.objects.create(
            code='test_series', entity='test_entity', pattern='{PREFIX}{SEQ:5}',
            prefix='TST', padding=5, next_value=1,
        )

    def test_allocate_renders_pattern(self):
        self.assertEqual(numbering.allocate('test_series'), 'TST00001')
        self.assertEqual(numbering.allocate('test_series'), 'TST00002')

    def test_preview_does_not_consume(self):
        self.assertEqual(numbering.preview('test_series'), 'TST00001')
        self.assertEqual(numbering.preview('test_series'), 'TST00001')  # unchanged
        self.assertEqual(numbering.allocate('test_series'), 'TST00001')  # still the first real one

    def test_concurrent_allocation_never_duplicates(self):
        """The required concurrency test: N threads, each its own DB
        connection, all allocating from the SAME series simultaneously —
        every resulting code must be unique."""
        results = []
        lock = threading.Lock()
        errors = []

        def worker():
            try:
                code = numbering.allocate('test_series')
                with lock:
                    results.append(code)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)
            finally:
                connection.close()  # each thread gets its own connection

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 20)
        self.assertEqual(len(set(results)), 20, f'Duplicate codes allocated: {results}')

    def test_yearly_reset(self):
        import datetime
        self.series.reset_period = NumberSeries.RESET_YEARLY
        self.series.pattern = '{PREFIX}{YYYY}{SEQ:3}'
        self.series.save()
        code1 = numbering.allocate('test_series', on_date=datetime.date(2026, 3, 1))
        self.assertEqual(code1, 'TST2026001')
        code2 = numbering.allocate('test_series', on_date=datetime.date(2027, 3, 1))
        self.assertEqual(code2, 'TST2027001')  # reset to 1 in the new year
