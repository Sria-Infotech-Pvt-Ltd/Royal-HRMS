from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0003_candidate_portal_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReferralRule',
            fields=[
                ('id',         models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('icon',       models.CharField(max_length=50)),
                ('title',      models.CharField(max_length=150)),
                ('body',       models.TextField()),
                ('order',      models.PositiveIntegerField(default=1)),
                ('is_active',  models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'referral_rule',
                'ordering': ['order'],
            },
        ),
    ]
