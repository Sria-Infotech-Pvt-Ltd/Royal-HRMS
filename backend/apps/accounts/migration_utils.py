"""Shared migration-operation helpers.

PostgresOnlyAddConstraint/PostgresOnlyRemoveConstraint wrap Django's own
AddConstraint/RemoveConstraint so a Postgres-only constraint (ExclusionConstraint,
which generates `EXCLUDE USING gist (...)` SQL) is a no-op on any other
backend. UAT/production run on PostgreSQL; local development may use SQLite
(see config/settings.py), where these guards skip the Postgres-only SQL.
"""
from __future__ import annotations

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, connections, migrations
from django.db.models import Exists, F, Func, Q
from django.db.models.lookups import Exact


class PortableExclusionConstraint(ExclusionConstraint):
    """A real ExclusionConstraint on Postgres; invisible everywhere else.

    SQLite's schema editor implements ANY constraint add/remove/alter on a
    table by fully rebuilding it — regenerating CREATE TABLE SQL for the
    model's CURRENT constraint state, including every other constraint still
    attached to it (see django.db.backends.sqlite3.schema.
    DatabaseSchemaEditor._remake_table). Guarding just the migration
    operations that add/remove this specific constraint (see
    PostgresOnlyAddConstraint/PostgresOnlyRemoveConstraint below) isn't
    enough on its own: the moment ANY unrelated schema change touches the
    same table (e.g. swapping an ordinary CheckConstraint), SQLite rebuilds
    the whole table and tries to emit this constraint's `EXCLUDE USING gist
    (...)` SQL anyway — a syntax SQLite has never heard of.

    Overriding constraint_sql/create_sql/remove_sql to return None on any
    non-Postgres backend uses Django's own documented "falsy SQL means skip
    this constraint" contract (see BaseDatabaseSchemaEditor.add_constraint/
    remove_constraint/create_model, all of which check `if sql:` before
    executing) — the same mechanism Django's own built-in constraint classes
    already use for backend-conditional SQL, not a hack layered on top of it.
    """

    def constraint_sql(self, model, schema_editor):
        if schema_editor.connection.vendor != 'postgresql':
            return None
        return super().constraint_sql(model, schema_editor)

    def create_sql(self, model, schema_editor):
        if schema_editor.connection.vendor != 'postgresql':
            return None
        return super().create_sql(model, schema_editor)

    def remove_sql(self, model, schema_editor):
        if schema_editor.connection.vendor != 'postgresql':
            return None
        return super().remove_sql(model, schema_editor)

    def validate(self, model, instance, exclude=None, using=DEFAULT_DB_ALIAS):
        """Postgres validates with the real `&&` range operator. Other backends (local SQLite) can't run that, so the
        same rule is checked with plain comparisons: every EQUAL expression matches, and the inclusive
        daterange(lower, upper, '[]') windows overlap (a null upper bound means open-ended)."""
        if connections[using].vendor == 'postgresql':
            return super().validate(model, instance, exclude=exclude, using=using)
        replacement_map = instance._get_field_expression_map(meta=model._meta, exclude=exclude)
        replacements = {F(field): value for field, value in replacement_map.items()}
        filters = []
        for expression, operator in self.expressions:
            expression = F(expression) if isinstance(expression, str) else expression
            if exclude and any(isinstance(part, F) and part.name in exclude for part in expression.flatten()):
                return
            if operator == RangeOperators.EQUAL:
                filters.append(Exact(expression, expression.replace_expressions(replacements)))
            elif operator == RangeOperators.OVERLAPS and _is_inclusive_daterange(expression):
                filters.append(_overlap_filter(expression, instance))
            else:
                raise NotImplementedError(f'{self.name}: operator {operator!r} has no non-Postgres validation.')
        queryset = model._default_manager.using(using).filter(*filters)
        model_class_pk = instance._get_pk_val(model._meta)
        if not instance._state.adding and model_class_pk is not None:
            queryset = queryset.exclude(pk=model_class_pk)
        if self.condition:
            is_violated = (self.condition & Exists(queryset.filter(self.condition))).check(replacement_map, using=using)
        else:
            is_violated = queryset.exists()
        if is_violated:
            raise ValidationError(self.get_violation_error_message(), code=self.violation_error_code)


def _is_inclusive_daterange(expression) -> bool:
    if not isinstance(expression, Func):
        return False
    # Func(..., function='daterange') keeps that keyword in `extra`; a Func subclass would set the class attribute instead.
    function_name = expression.extra.get('function') or expression.function
    return (function_name == 'daterange'
            and all(isinstance(part, F) for part in expression.get_source_expressions()[:2]))


def _overlap_filter(expression, instance) -> Q:
    """Rows whose [lower, upper] window (upper null = open-ended) overlaps the instance's own window."""
    lower_field, upper_field = (part.name for part in expression.get_source_expressions()[:2])
    lower, upper = getattr(instance, lower_field), getattr(instance, upper_field)
    overlap = Q(**{f'{upper_field}__isnull': True}) | Q(**{f'{upper_field}__gte': lower})
    if upper is not None:
        overlap &= Q(**{f'{lower_field}__lte': upper})
    return overlap


class PostgresOnlyAddConstraint(migrations.AddConstraint):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)


class PostgresOnlyRemoveConstraint(migrations.RemoveConstraint):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)
