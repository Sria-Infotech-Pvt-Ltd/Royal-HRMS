import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0224_seed_timesheet_approval_rule'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalworkflowrule',
            name='l1_approver_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='approvalworkflowrule',
            name='l2_approver_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='approvalworkflowrule',
            name='l1_approver_kind',
            field=models.CharField(blank=True, choices=[('reporting_manager', 'Reporting manager'), ('hr', 'HR partner'), ('person', 'A specific person')], default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='approvalworkflowrule',
            name='l2_approver_kind',
            field=models.CharField(blank=True, choices=[('reporting_manager', 'Reporting manager'), ('hr', 'HR partner'), ('person', 'A specific person')], default='', max_length=20),
        ),
    ]
