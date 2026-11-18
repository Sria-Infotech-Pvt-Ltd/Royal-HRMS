"""
Hire document upload: idempotent retry, bounded storage timeout, last-upload-wins under overlap, cleanup of replaced files.

Background. A document upload used to hold one request open for as long as the storage connection stalled (the ImageKit SDK default was
60 s x 3 attempts), keep a database transaction open around the network call, leave replaced files in storage forever, and let two
overlapping uploads for one slot delete each other's row. Daphne logged "took too long to shut down and was killed" for the first.

The overlap is tested deterministically (a second upload completes in the middle of the first one's storage write) rather than with real
threads: a TransactionTestCase would truncate the seeded document-type rows of the shared test database.
"""
from __future__ import annotations

import os
from unittest.mock import patch

from django.db import transaction
from django.urls import reverse

from apps.accounts import services_hire_documents
from apps.accounts.models import HireActionDocument
from apps.accounts.tests_hire_wizard import HireWizardTestCase, _VALID_PNG, _in_memory_save, _png_file
from core.storage import ImageKitStorage, StorageUnavailable


def _image(label: str, size: int = 0) -> bytes:
    """A valid PNG that is unique per label (the view rejects the same bytes under two document types)."""
    return _VALID_PNG + label.encode() + os.urandom(size)


class HireDocumentUploadTests(HireWizardTestCase):
    def setUp(self):
        super().setUp()
        self.action = self._create_draft()
        self.saves: list[str] = []

    def _upload(self, doc_type='pan_card', content=None, entry_ref='', name='scan.png'):
        data = {'document_type': doc_type, 'file': _png_file(name, content if content is not None else _image(doc_type))}
        if entry_ref:
            data['entry_ref'] = entry_ref
        return self.client.post(reverse('hire-action-document-list', args=[self.action.id]), data, format='multipart')

    def _count_saves(self, hook=None):
        def save(storage, name, content):
            self.saves.append(name)
            if hook:
                hook()
            return _in_memory_save(storage, name, content)
        return patch.object(ImageKitStorage, '_save', save)

    def _rows(self, doc_type='pan_card'):
        return HireActionDocument.objects.filter(hire_action=self.action, document_type=doc_type)

    # ── idempotent retry ───────────────────────────────────────────────────────────────────────────────────────
    def test_the_same_file_uploaded_again_writes_nothing_to_storage_and_creates_no_second_row(self):
        content = _image('pan')
        with self._count_saves():
            first = self._upload(content=content)
            retry = self._upload(content=content)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(retry.data['data']['id'], first.data['data']['id'])
        self.assertEqual(len(self.saves), 1)
        self.assertEqual(self._rows().count(), 1)

    # ── bounded storage wait ───────────────────────────────────────────────────────────────────────────────────
    def test_a_stalled_storage_answers_with_a_clear_retryable_error_and_stores_nothing(self):
        def stalled(storage, name, content):
            raise StorageUnavailable('The file storage did not respond in time.')
        with patch.object(ImageKitStorage, '_save', stalled):
            response = self._upload()
        self.assertEqual(response.status_code, 503)
        self.assertIn('upload the file again', response.data['message'].lower())
        # Django marks the TEST's own wrapping transaction for rollback when the exception passes through Model.save();
        # requests are not wrapped in a transaction in production (no ATOMIC_REQUESTS), so only the test needs this reset.
        transaction.set_rollback(False)
        self.assertEqual(self._rows().count(), 0)

    def test_the_storage_client_gives_up_on_a_stalled_connection_in_seconds_not_minutes(self):
        from core import storage
        budget = storage.STORAGE_TIMEOUT
        self.assertLessEqual(budget.write + storage.STORAGE_MAX_RETRIES * budget.write, 65)
        self.assertLessEqual(budget.connect, 5)
        self.assertLessEqual(storage.STORAGE_MAX_RETRIES, 1)

    # ── overlapping uploads for one slot ───────────────────────────────────────────────────────────────────────
    def test_two_overlapping_uploads_for_one_slot_leave_exactly_one_row_and_remove_the_other_file(self):
        cleaned: list[list[str]] = []
        second_done = []

        def second_upload_lands_meanwhile():
            if second_done:
                return
            second_done.append(True)
            self.assertEqual(self._upload(content=_image('second')).status_code, 201)

        with patch.object(services_hire_documents, '_start_cleanup', lambda names: cleaned.append(list(names))), \
                self.captureOnCommitCallbacks(execute=True), self._count_saves(second_upload_lands_meanwhile):
            first = self._upload(content=_image('first'))
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self._rows().count(), 1)
        self.assertEqual(str(self._rows().get().id), first.data['data']['id'])   # the answer is the row that survived
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(len(cleaned[0]), 1)   # the losing file is removed from storage, not left behind

    def test_overlapping_uploads_for_different_slots_both_survive(self):
        done = []

        def other_slot_lands_meanwhile():
            if done:
                return
            done.append(True)
            self.assertEqual(self._upload('aadhaar_card', _image('aadhaar')).status_code, 201)

        with self._count_saves(other_slot_lands_meanwhile):
            self.assertEqual(self._upload('pan_card', _image('pan')).status_code, 201)
        self.assertEqual(HireActionDocument.objects.filter(hire_action=self.action).count(), 2)

    # ── draft closed while uploading ───────────────────────────────────────────────────────────────────────────
    def test_a_hire_completed_while_the_file_uploads_is_refused_and_the_stored_file_is_dropped(self):
        cleaned: list[list[str]] = []

        def hire_gets_discarded_meanwhile():
            type(self.action).objects.filter(pk=self.action.pk).update(status='completed')

        with patch.object(services_hire_documents, '_start_cleanup', lambda names: cleaned.append(list(names))), \
                self._count_saves(hire_gets_discarded_meanwhile):
            response = self._upload()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(HireActionDocument.objects.filter(hire_action=self.action).count(), 0)
        self.assertEqual(len(cleaned), 1)

    # ── realistic sizes and unchanged rules ────────────────────────────────────────────────────────────────────
    def test_realistic_file_sizes_upload_and_keep_their_size(self):
        for doc_type, size in (('pan_card', 70 * 1024), ('aadhaar_card', 1200 * 1024), ('tenth_certificate', 4500 * 1024)):
            with self.subTest(doc_type=doc_type):
                response = self._upload(doc_type, _image(doc_type, size))
                self.assertEqual(response.status_code, 201, response.data)
                self.assertGreaterEqual(self._rows(doc_type).get().file_size, size)

    def test_a_file_over_the_size_limit_is_still_refused(self):
        self.assertEqual(self._upload(content=_image('big', 5200 * 1024)).status_code, 400)

    def test_one_file_under_two_document_types_is_still_refused(self):
        content = _image('shared')
        self.assertEqual(self._upload('pan_card', content).status_code, 201)
        self.assertEqual(self._upload('aadhaar_card', content).status_code, 400)

    def test_a_per_entry_attachment_replaces_only_that_entrys_file(self):
        self.assertEqual(self._upload('degree_certificate', _image('a1'), entry_ref='temp-1').status_code, 201)
        self.assertEqual(self._upload('degree_certificate', _image('b1'), entry_ref='temp-2').status_code, 201)
        self.assertEqual(self._upload('degree_certificate', _image('a2'), entry_ref='temp-1').status_code, 201)
        rows = self._rows('degree_certificate')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.filter(entry_ref='temp-1').count(), 1)
