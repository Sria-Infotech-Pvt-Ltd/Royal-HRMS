import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('branch', '0008_merge_0007'),
        ('hrms', '0010_leaverequest_lop_days'),
    ]

    operations = [
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id',           models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('name',         models.CharField(max_length=200)),
                ('date',         models.DateField(db_index=True)),
                ('holiday_type', models.CharField(
                    choices=[
                        ('national', 'National Holiday'),
                        ('regional', 'Regional Holiday'),
                        ('optional', 'Optional Holiday'),
                        ('company',  'Company Holiday'),
                    ],
                    default='national',
                    max_length=20,
                )),
                ('description',  models.TextField(blank=True, default='')),
                ('branch',       models.ForeignKey(
                    blank=True,
                    help_text='Leave blank for a company-wide holiday.',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='holidays',
                    to='branch.branch',
                )),
                ('is_active',    models.BooleanField(default=True)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('updated_at',   models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'hrms_holidays', 'ordering': ['date']},
        ),
    ]
