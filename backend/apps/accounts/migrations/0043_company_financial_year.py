from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0042_clean_employee_role_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='financial_year_start_month',
            field=models.CharField(
                choices=[
                    ('January', 'January'), ('February', 'February'), ('March', 'March'),
                    ('April', 'April'), ('May', 'May'), ('June', 'June'),
                    ('July', 'July'), ('August', 'August'), ('September', 'September'),
                    ('October', 'October'), ('November', 'November'), ('December', 'December'),
                ],
                default='April',
                help_text='First month of the financial year (e.g. "April" for Apr–Mar).',
                max_length=10,
            ),
        ),
    ]
