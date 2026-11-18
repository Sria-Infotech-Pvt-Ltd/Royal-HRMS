"""Company assets issued to employees (CompanyAsset, the table the Assets screens use today).

A person sees the assets issued to them. HR with onboarding.edit also sees the assets of the employees they may see, which is the
rule the HR asset endpoints already apply. The newer inventory tables (Asset, AssetAllocation) hold no live data and are not
searched until they are used.
"""
from apps.accounts.models import CompanyAsset
from apps.global_search import filters as f
from apps.global_search.registry import FieldSpec, SearchModule, register
from apps.global_search.scope import own_or_in_scope

from ._helpers import choices_of, label_of, short_date


def _queryset(user):
    return CompanyAsset.objects.filter(own_or_in_scope(user, 'employee', permission='onboarding.edit')).select_related('employee')


def _describe(asset: CompanyAsset) -> dict:
    return {
        'id': str(asset.pk), 'title': ' · '.join(part for part in (label_of(asset, 'asset_type'), asset.tag_number) if part),
        'subtitle': asset.employee.full_name,
        'meta': {'Condition': label_of(asset, 'condition'), 'Issued': short_date(asset.issued_at), 'Returned': short_date(asset.returned_at)},
        'url': '/dashboard/employees',
    }


ASSETS = register(SearchModule(
    key='assets', label='Assets', icon='ti-device-laptop', permission=None, queryset=_queryset,
    fields=(
        FieldSpec('asset_type', 'Asset type', f.CHOICE, 'asset_type', choices=choices_of(CompanyAsset, 'asset_type')),
        FieldSpec('tag_number', 'Tag number', f.TEXT, 'tag_number', searchable=True),
        FieldSpec('condition', 'Condition', f.CHOICE, 'condition', choices=choices_of(CompanyAsset, 'condition')),
        FieldSpec('employee_name', 'Issued to', f.TEXT, 'employee__full_name', searchable=True),
        FieldSpec('employee_id', 'Employee ID', f.TEXT, 'employee__employee_id', searchable=True),
        FieldSpec('issued_at', 'Issued on', f.DATE, 'issued_at'),
        FieldSpec('returned_at', 'Returned on', f.DATE, 'returned_at'),
    ),
    describe=_describe, order_by=('-created_at', '-pk'), default_url='/dashboard/employees',
))
