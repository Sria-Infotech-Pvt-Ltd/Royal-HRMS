from django.db import migrations, models


def seed_categories(apps, schema_editor):
    EmailTemplateCategory = apps.get_model('accounts', 'EmailTemplateCategory')
    defaults = [
        {'name': 'wish',         'display_name': 'Wishes',        'order': 1},
        {'name': 'reminder',     'display_name': 'Reminders',     'order': 2},
        {'name': 'notification', 'display_name': 'Notifications', 'order': 3},
        {'name': 'document',     'display_name': 'Documents',     'order': 4},
        {'name': 'recruitment',  'display_name': 'Recruitment',   'order': 5},
        {'name': 'onboarding',   'display_name': 'Onboarding',    'order': 6},
    ]
    for d in defaults:
        EmailTemplateCategory.objects.get_or_create(
            name=d['name'],
            defaults={**d, 'is_builtin': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0016_add_performance_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailTemplateCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50, unique=True)),
                ("display_name", models.CharField(max_length=100)),
                ("is_builtin", models.BooleanField(default=False)),
                ("order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "db_table": "hrms_email_template_categories",
                "ordering": ["order", "display_name"],
            },
        ),
        migrations.AlterField(
            model_name="emailtemplate",
            name="template_type",
            field=models.CharField(default="notification", max_length=50),
        ),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
