"""Shared exception types for the rule engine — kept in their own tiny
module so rule_functions.py and services_rules.py can both import them
without one importing the other."""
from __future__ import annotations


class RuleError(Exception):
    """Raised for any malformed/malicious/out-of-budget expression — the
    evaluator NEVER lets a bad rule hang or raise an unhandled Python
    exception; everything funnels through this one clean error type."""
    def __init__(self, message: str, node_path: str = ''):
        self.message = message
        self.node_path = node_path
        super().__init__(f'{node_path}: {message}' if node_path else message)


class RuleLimitExceeded(RuleError):
    pass
