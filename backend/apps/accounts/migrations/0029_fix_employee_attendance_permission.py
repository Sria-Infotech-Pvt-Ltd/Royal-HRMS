"""
Fix: remove attendance.view from the employee role.

Employees should use /dashboard/my-attendance (permission: null, always visible).
The main /dashboard/attendance page is admin/HR/manager only and is gated by
attendance.view. Giving employees attendance.view caused the admin attendance
page (OT Entry, Invalid Punches, Un-punches) to appear in their sidebar.

attendance.create is kept so employees can submit regularization requests
from the My Attendance page.
"""
from django.db import migrations


def remove_attendance_view_from_employee(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        employee_role = Role.objects.get(name='employee')
        attendance_view = Permission.objects.get(codename='attendance.view')
        RolePermission.objects.filter(
            role=employee_role,
            permission=attendance_view,
        ).delete()
    except (Role.DoesNotExist, Permission.DoesNotExist):
        pass  # already removed or roles not seeded yet


def restore_attendance_view_to_employee(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        employee_role = Role.objects.get(name='employee')
        attendance_view = Permission.objects.get(codename='attendance.view')
        RolePermission.objects.get_or_create(
            role=employee_role,
            permission=attendance_view,
        )
    except (Role.DoesNotExist, Permission.DoesNotExist):
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0028_add_onboarding_draft_status'),
    ]

    operations = [
        migrations.RunPython(
            remove_attendance_view_from_employee,
            restore_attendance_view_to_employee,
        ),
    ]
