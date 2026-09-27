"""Shared migration-operation helpers.

PostgresOnlyAddConstraint/PostgresOnlyRemoveConstraint wrap Django's own
AddConstraint/RemoveConstraint so a Postgres-only constraint (ExclusionConstraint,
which generates `EXCLUDE USING gist (...)` SQL with no SQLite equivalent) is a
no-op on any other backend, the same way Django's own BtreeGistExtension
operation already no-ops on non-Postgres (see django.contrib.postgres.operations.
CreateExtension.database_forwards) rather than crashing the whole migration
history. Local dev can run against SQLite (see config/settings.py's
DATABASE_URL default) without ever hitting these; production (Neon Postgres)
gets the real constraint exactly as before — nothing changes there.

This intentionally means the "no double-booking" guarantee these two
constraints exist for is NOT enforced at the DB level on SQLite — only
Postgres gets the real guarantee. That trade-off is deliberate: SQLite here
is for local development convenience only, never a production target for
this app (see the settings.py comment on DATABASE_URL's default).
"""
from __future__ import annotations

from django.contrib.postgres.constraints import ExclusionConstraint
from django.db import migrations


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
