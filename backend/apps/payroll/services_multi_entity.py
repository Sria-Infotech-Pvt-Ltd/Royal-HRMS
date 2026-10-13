"""
Phase 7B Task M — multi-entity/multi-currency guard. Scoped down to the
one real, enforceable rule the master prompt states explicitly ("no
implicit conversion"): an EmployeeCompensation's currency must match its
PayGroup's currency, full stop — raising rather than silently converting.
Cross-entity transfer (Task M.2) and consolidated multi-currency reporting
(Task M.3) are NOT built in this pass — both need real exchange-rate-at-a-
date plumbing this phase hasn't touched; documented here as deferred
rather than approximated.
"""


class CurrencyMismatchError(Exception):
    pass


def validate_compensation_currency(compensation, pay_group) -> None:
    comp_currency = compensation.currency_id
    group_currency = pay_group.currency_id
    if comp_currency and group_currency and comp_currency != group_currency:
        raise CurrencyMismatchError(
            f'Employee compensation is in a different currency than pay group '
            f'{pay_group.code} — no implicit conversion. Resolve explicitly before running payroll.'
        )
