from django.db import migrations


def backfill_active_reference(apps, schema_editor):
    """
    is_active defaults to False for every pre-existing row (0033), which
    would leave every employee who already has an approved registration
    looking like they have none. Backfill it to whichever row the OLD
    _resolve_active_registration logic would have picked — the approved
    row with the latest approved_at per employee — so behaviour doesn't
    regress for anyone already enrolled.
    """
    FaceRegistrationRequest = apps.get_model('attendance', 'FaceRegistrationRequest')

    employee_ids = (
        FaceRegistrationRequest.objects
        .filter(status='approved')
        .values_list('employee_id', flat=True)
        .distinct()
    )
    for employee_id in employee_ids:
        current = (
            FaceRegistrationRequest.objects
            .filter(employee_id=employee_id, status='approved')
            .order_by('-approved_at')
            .first()
        )
        if current is not None:
            FaceRegistrationRequest.objects.filter(pk=current.pk).update(is_active=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0033_face_registration_active_reference'),
    ]

    operations = [
        migrations.RunPython(backfill_active_reference, noop_reverse),
    ]
