"""
Phase 2 Task A.2 — syncs code-registered core entities
(platform_core.registry.register_entity calls) into the
EntityDefinition table. Idempotent: matches by `code`, creates missing
rows, updates the auto-generated fields (app_label/model_name/
attributes_column) on existing rows WITHOUT touching admin-editable
fields (label, icon, plural_label) once they've been changed from the
registration default — same "never clobber an admin edit" principle as
Phase 1's seed-pack loader, applied here to a much smaller, code-defined
set.

Also run from a post_migrate signal (see apps.py) so a fresh install
always has these rows without a manual step.
"""
from django.core.management.base import BaseCommand

from apps.platform_core import registry
from apps.platform_core.models import EntityDefinition


class Command(BaseCommand):
    help = 'Sync code-registered core entities into the EntityDefinition table.'

    def handle(self, *args, **options):
        registry.register_builtin_core_entities()
        created, updated, unchanged = 0, 0, 0

        for reg in registry.get_core_registrations():
            obj, was_created = EntityDefinition.objects.get_or_create(
                code=reg['code'],
                defaults={
                    'label': reg['label'], 'plural_label': reg['plural_label'], 'module': reg['module'],
                    'kind': EntityDefinition.KIND_CORE, 'app_label': reg['app_label'], 'model_name': reg['model_name'],
                    'attributes_column': reg['attributes_column'], 'legal_entity_scoped': reg['legal_entity_scoped'],
                    'owner_field': reg['owner_field'], 'status': EntityDefinition.STATUS_PUBLISHED,
                },
            )
            if was_created:
                created += 1
                continue

            # Only the auto-generated, code-owned fields are kept in sync —
            # label/icon/plural_label are admin-editable and never
            # overwritten here once the row exists.
            changed_fields = []
            for field in ('app_label', 'model_name', 'attributes_column', 'legal_entity_scoped'):
                if getattr(obj, field) != reg[field]:
                    setattr(obj, field, reg[field])
                    changed_fields.append(field)
            if changed_fields:
                obj.save(update_fields=changed_fields)
                updated += 1
            else:
                unchanged += 1

        self.stdout.write(self.style.SUCCESS(f'Entity registry synced. Created={created} Updated={updated} Unchanged={unchanged}'))
