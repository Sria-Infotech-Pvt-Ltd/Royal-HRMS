"""SQLite backend for local development only (settings.py selects it for sqlite:/// DATABASE_URLs).

Why it exists: SQLite has no real ALTER TABLE, so Django's SQLite schema editor removes a column by rebuilding the whole
table, copying every column that the *model* still lists. A RunPython migration that removes several fields from the
same historical model one after another (e.g. accounts.0196_remove_roles) hands the schema editor a model that still
lists the columns it already dropped. SQLite then treats the missing double-quoted column name as a string literal and
copies that text into the rebuilt table, which fails the foreign-key check. PostgreSQL drops columns in place and is
unaffected.

Rather than edit committed migrations, this editor hides such already-dropped fields from the model while it rebuilds
the table, then puts them back.

It also translates the PostgreSQL-only column statements used by idempotent RunSQL migrations
(`ALTER TABLE t ADD COLUMN IF NOT EXISTS ...` / `ALTER TABLE t DROP COLUMN IF EXISTS a, DROP COLUMN IF EXISTS b`) into
their SQLite equivalents: check the table's columns first, then run the plain ADD/DROP COLUMN only where needed.
"""
import logging
import re

from django.db.backends.sqlite3 import base, schema

logger = logging.getLogger(__name__)

_ADD_COLUMN_IF_NOT_EXISTS = re.compile(
    r'^\s*ALTER\s+TABLE\s+"?(?P<table>\w+)"?\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"?(?P<column>\w+)"?\s+(?P<definition>.+?)\s*;?\s*$',
    re.IGNORECASE | re.DOTALL,
)
_DROP_COLUMNS_IF_EXISTS = re.compile(
    r'^\s*ALTER\s+TABLE\s+"?(?P<table>\w+)"?\s+(?P<drops>DROP\s+COLUMN\s+IF\s+EXISTS\s+.+?)\s*;?\s*$',
    re.IGNORECASE | re.DOTALL,
)
_DROP_COLUMN_ITEM = re.compile(r'^\s*DROP\s+COLUMN\s+IF\s+EXISTS\s+"?(?P<column>\w+)"?\s*$', re.IGNORECASE)


class DatabaseSchemaEditor(schema.DatabaseSchemaEditor):

    def execute(self, sql, params=()):
        statements = self._translate_postgres_column_sql(sql) if isinstance(sql, str) else None
        if statements is None:
            return super().execute(sql, params)
        for statement in statements:
            super().execute(statement, None)

    def _translate_postgres_column_sql(self, sql):
        """SQLite statements equivalent to a Postgres `... COLUMN IF [NOT] EXISTS` statement, or None if `sql` isn't one."""
        added = _ADD_COLUMN_IF_NOT_EXISTS.match(sql)
        if added:
            table, column = added['table'], added['column']
            if column in self._table_columns(table):
                return []
            return [f'ALTER TABLE {self.quote_name(table)} ADD COLUMN {self.quote_name(column)} {added["definition"]}']
        dropped = _DROP_COLUMNS_IF_EXISTS.match(sql)
        if dropped:
            items = [_DROP_COLUMN_ITEM.match(part) for part in dropped['drops'].split(',')]
            if not all(items):
                return None
            table = dropped['table']
            existing = self._table_columns(table)
            return [
                f'ALTER TABLE {self.quote_name(table)} DROP COLUMN {self.quote_name(item["column"])}'
                for item in items if item['column'] in existing
            ]
        return None

    def _table_columns(self, table_name):
        with self.connection.cursor() as cursor:
            return {info.name for info in self.connection.introspection.get_table_description(cursor, table_name)}

    def remove_field(self, model, field):
        stale_fields = self._fields_missing_from_table(model, keep=field)
        if not stale_fields:
            return super().remove_field(model, field)
        logger.debug('Ignoring already-dropped columns %s of %s while removing %s',
                     [stale.column for stale in stale_fields], model._meta.db_table, field.column)
        local_fields = model._meta.local_fields
        original_fields = list(local_fields)
        for stale in stale_fields:
            local_fields.remove(stale)
        model._meta._expire_cache()
        try:
            return super().remove_field(model, field)
        finally:
            local_fields[:] = original_fields
            model._meta._expire_cache()

    def _fields_missing_from_table(self, model, keep):
        """Concrete local fields of `model` whose column no longer exists in its table (excluding `keep`)."""
        table_name = model._meta.db_table
        with self.connection.cursor() as cursor:
            if table_name not in self.connection.introspection.table_names(cursor):
                return []
            columns = {info.name for info in self.connection.introspection.get_table_description(cursor, table_name)}
        return [
            candidate for candidate in model._meta.local_concrete_fields
            if candidate is not keep and candidate.column not in columns
        ]


class DatabaseWrapper(base.DatabaseWrapper):
    SchemaEditorClass = DatabaseSchemaEditor
