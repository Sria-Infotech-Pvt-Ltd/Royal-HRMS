"""
Payment gateway integration point for website registrations.

The rest of the registration workflow depends only on this interface:

  get_gateway()                 configured gateway, or None (settings.PAYMENT_GATEWAY empty)
  gateway.create_order(reg)     server-side order for the registration's server-calculated total
  gateway.parse_webhook(...)    verify the gateway's signature → VerifiedPayment, or None if invalid

A registration becomes "paid" ONLY through
apps.tenants.registrations.record_payment_event(), fed by a verified
webhook. Browser redirects / client callbacks are never proof of payment.
Until a real gateway (Priority 5) is registered and configured, no
registration can be marked paid — so none can be approved.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class VerifiedPayment:
    """A payment event whose gateway signature has been verified."""
    event_id: str
    order_id: str
    payment_id: str
    amount_minor: int          # smallest currency unit (paise)
    currency: str
    status: str                # 'paid' | 'failed'
    failure_reason: str = ''


class PaymentGateway:
    """Interface a gateway adapter implements (see register_gateway)."""
    name = ''

    def create_order(self, registration) -> dict:
        """Create an order for registration.total. Returns
        {'order_id': str, 'amount_minor': int, 'currency': str, 'checkout': {...}}
        where 'checkout' holds only public values the browser needs."""
        raise NotImplementedError

    def parse_webhook(self, body: bytes, headers) -> VerifiedPayment | None:
        """Verify the webhook signature over the RAW body. None when invalid."""
        raise NotImplementedError


_GATEWAYS: dict[str, type[PaymentGateway]] = {}


def register_gateway(cls: type[PaymentGateway]) -> type[PaymentGateway]:
    _GATEWAYS[cls.name] = cls
    return cls


def get_gateway() -> PaymentGateway | None:
    name = (getattr(settings, 'PAYMENT_GATEWAY', '') or '').strip()
    if not name:
        return None
    cls = _GATEWAYS.get(name)
    if cls is None:
        raise ImproperlyConfigured(f'PAYMENT_GATEWAY "{name}" is not a registered payment gateway.')
    return cls()


def to_minor(amount: Decimal) -> int:
    """Rupees → paise (2-decimal currencies)."""
    return int((Decimal(amount) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
