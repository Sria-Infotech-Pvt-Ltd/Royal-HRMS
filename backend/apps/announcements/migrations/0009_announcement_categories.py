from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0008_announcement_attachments_and_links'),
    ]

    operations = [
        migrations.AlterField(
            model_name='announcement',
            name='category',
            field=models.CharField(choices=[('general', 'Company News'), ('policy', 'Policy'), ('event', 'Events'), ('celebration', 'Celebration'), ('holiday', 'Holiday & Closures'), ('payroll', 'Payroll & Benefits'), ('urgent', 'Urgent')], max_length=20),
        ),
    ]
