"""
Application-layer field encryption for sensitive PII — bank account numbers,
IFSC codes, PAN, UAN, and Aadhaar-registered names (see CLAUDE.md section 3:
"PAN, Aadhaar, bank account numbers must be noted as requiring encryption"),
plus biometric face embeddings (same tier of sensitivity, same treatment).

EncryptedCharField/EncryptedJSONField store ciphertext (Fernet — AES-128-CBC
+ HMAC, random IV per value) in the DB column and transparently decrypt on
read. Fernet is non-deterministic: encrypting the same plaintext twice
produces different ciphertext, so encrypted columns can never be used in an
exact-match `.filter()` — use `blind_index()` below for that instead (see
EmployeeProfile.pan_number_hash; face embeddings have no equivalent need,
since matching is always done by distance in application code, never by
DB-level equality).

A row containing legacy, not-yet-encrypted plaintext (or an already-decrypted
value re-read before a save) fails Fernet decryption and is returned as-is
rather than raising — this is what makes the one-pass migration in
accounts/migrations/0064_encrypt_sensitive_pii.py (and the equivalent one for
face_embedding) safe to run (and re-run).
"""
import hmac
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    return Fernet(key.encode() if isinstance(key, str) else key)


def blind_index(value: str) -> str:
    """
    Deterministic HMAC-SHA256 of a plaintext value, for exact-match lookups
    against an EncryptedCharField's value without ever storing or querying
    the plaintext itself. Uses a key separate from FIELD_ENCRYPTION_KEY.
    """
    key = settings.FIELD_INDEX_HMAC_KEY
    key_bytes = key.encode() if isinstance(key, str) else key
    return hmac.new(key_bytes, value.encode(), hashlib.sha256).hexdigest()


class EncryptedCharField(models.CharField):
    """Transparent Fernet-encrypted CharField. Blank values pass through unencrypted."""

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value:
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return value


class EncryptedJSONField(models.TextField):
    """
    Transparent Fernet-encrypted field for a JSON-serializable Python value
    (a list of floats, here — a face embedding vector) rather than a plain
    string. Same encrypt-on-write/decrypt-on-read contract as
    EncryptedCharField, with a json.dumps/json.loads step wrapped around the
    same encrypt/decrypt call so any JSON-serializable value round-trips.

    Backed by TextField, not the JSONField this replaced — Fernet ciphertext
    is an opaque base64 string, not valid JSON, so it can't live in a jsonb
    column. Blank/None values pass through unencrypted, same convention as
    EncryptedCharField.
    """

    def get_prep_value(self, value):
        if not value:
            return value
        serialized = json.dumps(value)
        return _fernet().encrypt(serialized.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            decrypted = _fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Legacy plaintext JSON (or the raw text left behind by the
            # jsonb->text column-type migration before its own data pass
            # re-saves and encrypts it) — same "return usably as-is"
            # convention as EncryptedCharField, except here "as-is" means
            # parsed back into the list it represents, not the raw string.
            decrypted = value
        try:
            return json.loads(decrypted)
        except (TypeError, ValueError):
            return None
