"""
Storing one document uploaded in the Hire wizard.

Why this is separate from the view, and what it guarantees:

* Idempotent retry. The same bytes uploaded again for the same slot (a retry after a timeout, a double click, a reload) return the
  row already stored and write nothing to storage, so a retry is instant and can never create a duplicate.
* No database transaction is held open during the network upload. The file is written to storage first; only the short
  "keep exactly one file per slot" step runs inside a transaction.
* Concurrent uploads to the same slot cannot corrupt it. That step locks the draft's row, so two uploads for the same slot run it one
  after the other and exactly one row (the newest) survives. Uploads to different slots do not wait for each other.
* Replaced files are removed from storage (they used to be left behind there forever), after the database change is committed and
  in the background, so the person never waits for the slow storage delete and a failed delete never undoes a successful upload.
"""
from __future__ import annotations

import logging
import threading

from django.db import transaction

from apps.accounts.models import HireAction, HireActionDocument

logger = logging.getLogger(__name__)


class DraftNoLongerOpen(Exception):
    """The hire was completed or discarded while the file was uploading."""


def _discard_stored_files(names: list[str]) -> None:
    storage = HireActionDocument._meta.get_field('file').storage
    for name in names:
        try:
            storage.delete(name)
        except Exception as exc:  # noqa: BLE001 - cleanup of an already-replaced file must never surface to the caller
            logger.warning('Could not remove a replaced hire document from storage (%s); it is orphaned there.', type(exc).__name__)


def _slot(action: HireAction, document_type: str, entry_ref: str, allow_multiple: bool):
    """The rows that compete for one slot, or None when the type allows several files (nothing is replaced)."""
    if entry_ref:
        return HireActionDocument.objects.filter(hire_action=action, document_type=document_type, entry_ref=entry_ref)
    if not allow_multiple:
        return HireActionDocument.objects.filter(hire_action=action, document_type=document_type, entry_ref='')
    return None


def find_identical(action: HireAction, document_type: str, entry_ref: str, content_hash: str) -> HireActionDocument | None:
    return HireActionDocument.objects.filter(
        hire_action=action, document_type=document_type, entry_ref=entry_ref, content_hash=content_hash,
    ).first()


def store_document(action: HireAction, serializer, *, document_type: str, entry_ref: str, allow_multiple: bool,
                   file_name: str, file_size: int, content_hash: str) -> tuple[HireActionDocument, bool]:
    """Returns (the document that now holds the slot, created). created is False when an identical file was already there."""
    already = find_identical(action, document_type, entry_ref, content_hash)
    if already:
        return already, False

    # Storage write first, no transaction open around it. Raises StorageUnavailable (nothing stored) on a stalled connection.
    doc = serializer.save(hire_action=action, file_name=file_name[:255], file_size=file_size, content_hash=content_hash, entry_ref=entry_ref)

    replaced_names: list[str] = []
    still_open = True
    with transaction.atomic():
        still_open = HireAction.objects.select_for_update().filter(pk=action.pk, status=HireAction.STATUS_DRAFT).exists()
        slot = _slot(action, document_type, entry_ref, allow_multiple) if still_open else None
        if slot is not None:
            rows = list(slot.order_by('-uploaded_at', '-id'))
            for loser in rows[1:]:
                replaced_names.append(loser.file.name)
                loser.delete()
            doc = rows[0]   # last upload wins, so the answer is the row that actually survived
        if replaced_names:
            transaction.on_commit(lambda: _start_cleanup(replaced_names))
    if not still_open:
        # The hire was completed or discarded while this file uploaded: drop what was just stored rather than leave it orphaned.
        name = doc.file.name
        doc.delete()
        _start_cleanup([name])
        raise DraftNoLongerOpen()
    return doc, True


def _start_cleanup(names: list[str]) -> None:
    threading.Thread(target=_discard_stored_files, args=(list(names),), name='hire-doc-cleanup', daemon=True).start()
