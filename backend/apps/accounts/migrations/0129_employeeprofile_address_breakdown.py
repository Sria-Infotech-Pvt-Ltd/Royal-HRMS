# Splits current_address/permanent_address (previously one free-text blob
# each) into a proper Indian address: the existing TextField keeps only the
# house/street/area line, and village, district, state and PIN code each get
# their own column — mirrors Company's address/city/state/pin_code split
# (see CompanySerializer / apps/accounts/models.py Company).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0128_alter_smtpsettings_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeprofile",
            name="current_village",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="employeeprofile",
            name="current_district",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="employeeprofile",
            name="current_state",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="employeeprofile",
            name="current_pin_code",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name="employeeprofile",
            name="permanent_village",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="employeeprofile",
            name="permanent_district",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="employeeprofile",
            name="permanent_state",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="employeeprofile",
            name="permanent_pin_code",
            field=models.CharField(blank=True, max_length=6),
        ),
    ]
