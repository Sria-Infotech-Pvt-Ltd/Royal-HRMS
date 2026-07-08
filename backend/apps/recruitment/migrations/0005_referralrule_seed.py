from django.db import migrations


_RULES = [
    {'icon': 'ti-users',          'title': 'Eligibility',          'order': 1, 'body': 'All confirmed employees with 6+ months of service are eligible to refer candidates.'},
    {'icon': 'ti-currency-rupee', 'title': 'Referral Bonus',       'order': 2, 'body': 'A bonus of ₹10,000 is paid upon the referred candidate completing 90 days in the role.'},
    {'icon': 'ti-user-cancel',    'title': 'No Self-Referral',     'order': 3, 'body': 'Employees cannot refer themselves, immediate family members, or direct reports.'},
    {'icon': 'ti-calendar-off',   'title': 'Cooling Period',       'order': 4, 'body': 'A candidate referred or applied in the last 12 months is not eligible.'},
    {'icon': 'ti-list-numbers',   'title': 'Active Referral Limit','order': 5, 'body': 'Each employee may hold up to 3 active referrals at any time.'},
    {'icon': 'ti-receipt-tax',    'title': 'Tax & Payroll',        'order': 6, 'body': 'Referral bonuses are subject to income tax and processed in the next payroll cycle after the 90-day milestone.'},
]


def seed_referral_rules(apps, schema_editor):
    ReferralRule = apps.get_model('recruitment', 'ReferralRule')
    for rule in _RULES:
        ReferralRule.objects.get_or_create(title=rule['title'], defaults=rule)


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0004_referralrule'),
    ]

    operations = [
        migrations.RunPython(seed_referral_rules, migrations.RunPython.noop),
    ]
