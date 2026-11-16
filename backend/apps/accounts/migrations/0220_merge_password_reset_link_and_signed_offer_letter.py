from django.db import migrations


class Migration(migrations.Migration):
    """Merge migration, no schema changes of its own.

    The 05-nov-2026 branch added 0212_repair_employee_code_series_columns and
    0213_password_reset_by_admin_link_not_password on top of 0211; this branch had
    already grown 0212_employee_id_ranges ... 0219_signed_offer_letter_optional
    on top of the same 0211. Both chains are kept untouched and joined here so
    the graph has a single leaf again (Django refuses to migrate with two)."""

    dependencies = [
        ('accounts', '0213_password_reset_by_admin_link_not_password'),
        ('accounts', '0219_signed_offer_letter_optional'),
    ]

    operations = []
