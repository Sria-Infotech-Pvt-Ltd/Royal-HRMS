"""
Add an optional 'provider' label to SMTPSettings — Gmail / Amazon SES /
Zoho Mail / Brevo / Resend / Outlook365 / Custom SMTP / Dedicated Mail
Server. Purely a UI convenience on top of the existing generic host/port/
username/password/use_tls fields; nothing in the send path reads it.
Blank by default and NOT backfilled — every pre-existing row keeps
provider='' ("unspecified/custom"), so this is a no-op for current
production configs.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0098_seed_password_reset_email_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='smtpsettings',
            name='provider',
            field=models.CharField(
                blank=True,
                choices=[
                    ('gmail', 'Gmail'),
                    ('amazon_ses', 'Amazon SES'),
                    ('zoho_mail', 'Zoho Mail'),
                    ('brevo', 'Brevo (Sendinblue)'),
                    ('resend', 'Resend'),
                    ('outlook365', 'Outlook / Office 365'),
                    ('custom_smtp', 'Custom SMTP'),
                    ('dedicated_server', 'Dedicated Mail Server'),
                ],
                default='',
                max_length=20,
            ),
        ),
    ]
