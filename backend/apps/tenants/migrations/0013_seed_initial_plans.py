"""
Initial plans from "HRMS - Business plans.docx": Starter, Growth, Business.
Seeded ACTIVE (assignable by Platform Admin) but NOT public. Only features
that exist are included — TDS, performance, appraisal, training, advanced
reports / analytics, roster, legal entities, API integrations and custom
workflows are "Coming soon" in the catalogue. Features not in the document
(announcements, WFH, assessments, Face ID, voice) are placed as a default
for Platform Admin to review. Existing plans with the same code are left
untouched.
"""
from decimal import Decimal

from django.db import migrations

STARTER = ['attendance', 'leave', 'documents', 'wfh', 'announcements', 'mobile_access', 'basic_reports']
GROWTH = STARTER + ['payroll', 'expenses', 'recruitment', 'assessments', 'separation', 'advanced_dashboards']
BUSINESS = GROWTH + ['assets', 'face_attendance', 'voice_commands', 'multi_branch', 'advanced_rbac',
                     'priority_support']

PLANS = [
    {'code': 'starter', 'name': 'Starter', 'price': '49', 'order': 1, 'features': STARTER,
     'description': 'For startups and small businesses.'},
    {'code': 'growth', 'name': 'Growth', 'price': '99', 'order': 2, 'features': GROWTH,
     'description': 'For growing SMEs and mid-sized companies. Most popular.'},
    {'code': 'business', 'name': 'Business / Premium', 'price': '149', 'order': 3, 'features': BUSINESS,
     'description': 'For enterprises and multi-location businesses. Suggested 100–1,000+ employees. '
                    'GST treatment to be confirmed.'},
]


def seed(apps, schema_editor):
    Plan = apps.get_model('tenants', 'SubscriptionPlan')
    for p in PLANS:
        if Plan.objects.filter(code=p['code']).exists():
            continue
        Plan.objects.create(
            code=p['code'], name=p['name'], description=p['description'],
            price_per_employee=Decimal(p['price']), currency='INR', billing_periods=['monthly'],
            gst_rate=Decimal('18'), gst_inclusive=False, features=sorted(set(p['features'])),
            status='active', is_public=False, display_order=p['order'],
        )


def unseed(apps, schema_editor):
    Plan = apps.get_model('tenants', 'SubscriptionPlan')
    Plan.objects.filter(code__in=[p['code'] for p in PLANS], subscriptions__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [('tenants', '0012_saas_subscriptions')]
    operations = [migrations.RunPython(seed, unseed)]
