"""
Application-layer field encryption for sensitive PII — bank account numbers,
IFSC codes, PAN, UAN, and Aadhaar-registered names (see CLAUDE.md section 3:
"PAN, Aadhaar, bank account numbers must be noted as requiring encryption").

EncryptedCharField stores ciphertext (Fernet — AES-128-CBC + HMAC, random IV
per value) in the DB column and transparently decrypts on read. Fernet is
non-deterministic: encrypting the same plaintext twice produces different
ciphertext, so encrypted columns can never be used in an exact-match `.filter()`
— use `blind_index()` below for that instead (see EmployeeProfile.pan_number_hash).

A row containing legacy, not-yet-encrypted plaintext (or an already-decrypted
value re-read before a save) fails Fernet decryption and is returned as-is
rather than raising — this is what makes the one-pass migration in
accounts/migrations/0064_encrypt_sensitive_pii.py safe to run (and re-run).
"""
import hmac
import hashlib

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
