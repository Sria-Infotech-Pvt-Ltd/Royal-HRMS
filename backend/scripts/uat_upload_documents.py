"""Upload and verify required synthetic documents for the 100-person UAT set.

This uses the normal HR employee-document and onboarding-review endpoints.
Files contain a valid tiny PNG plus a synthetic per-employee/type marker.
The script is resumable: document types already present are left untouched.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()
logging.getLogger('apps.accounts.views.onboarding_documents').setLevel(logging.WARNING)

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.db.utils import OperationalError
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.demo_workforce_data import EMAIL_SUFFIX
from apps.accounts.models import DocumentTypeConfig, EmployeeDocument, User


_PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108020000009077'
    '53de0000000c4944415478da6360000002000155a5d4a80000000049454e44ae426082'
) + b'\x00' * 3000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Only process the first N employees (0 = all).')
    args = parser.parse_args()

    def query_with_retry(query_factory):
        for attempt in range(5):
            try:
                connection.close()
                return query_factory()
            except OperationalError:
                connection.close()
                if attempt == 4:
                    raise
                time.sleep(2 * (attempt + 1))

    actor = query_with_retry(lambda: User.objects.filter(is_active=True, is_superuser=True).first())
    if actor is None:
        raise SystemExit('No active UAT HR administrator is available.')
    employees = query_with_retry(lambda: list(
        User.objects.filter(email__iendswith=EMAIL_SUFFIX).order_by('employee_id')
    ))
    if args.limit:
        employees = employees[:args.limit]
    required = query_with_retry(lambda: list(DocumentTypeConfig.objects.filter(required=True).order_by('type_key')))
    if not employees or not required:
        raise SystemExit('UAT employees or required document types are missing.')

    client = APIClient(SERVER_NAME='localhost')
    uploaded = verified = skipped = 0

    def post_with_retry(request_factory):
        response = None
        for attempt in range(5):
            close_old_connections()
            response = request_factory()
            if response.status_code != 503 or attempt == 4:
                return response
            time.sleep(2 * (attempt + 1))
        return response

    with override_settings(ALLOWED_HOSTS=['*'], SECURE_SSL_REDIRECT=False):
        for index, employee in enumerate(employees, start=1):
            documents = query_with_retry(lambda: list(EmployeeDocument.objects.filter(user=employee)))
            documents_by_type = {doc.document_type: doc for doc in documents}
            for config in required:
                doc = documents_by_type.get(config.type_key)
                if doc is not None:
                    if doc and doc.verification_status == EmployeeDocument.VERIFICATION_VERIFIED:
                        skipped += 1
                        continue
                else:
                    marker = f'{employee.employee_id}:{config.type_key}'.encode()
                    client.force_authenticate(user=actor)
                    response = post_with_retry(lambda: client.post(
                        reverse('employee-documents', kwargs={'employee_id': employee.employee_id}),
                        {
                            'document_type': config.type_key,
                            'file': SimpleUploadedFile(
                                f'uat-{employee.employee_id}-{config.type_key}.png',
                                _PNG + marker + b'\x00' * 16,
                                content_type='image/png',
                            ),
                        },
                        format='multipart',
                    ))
                    if response.status_code != 201:
                        raise RuntimeError(
                            f'Upload failed at employee {index}, type {config.type_key}: '
                            f'HTTP {response.status_code} {getattr(response, "data", "")}'
                        )
                    doc = query_with_retry(lambda: EmployeeDocument.objects.get(pk=response.data['data']['id']))
                    uploaded += 1

                if doc.verification_status != EmployeeDocument.VERIFICATION_VERIFIED:
                    client.force_authenticate(user=actor)
                    response = post_with_retry(lambda: client.post(
                        reverse('onboarding-document-verify', kwargs={'doc_id': doc.pk}),
                        {'verification_status': EmployeeDocument.VERIFICATION_VERIFIED},
                        format='json',
                    ))
                    if response.status_code != 200:
                        raise RuntimeError(
                            f'Verification failed at employee {index}, type {config.type_key}: '
                            f'HTTP {response.status_code} {getattr(response, "data", "")}'
                        )
                    verified += 1
            if index % 10 == 0 or index == len(employees):
                print(f'Processed {index}/{len(employees)} synthetic employees; uploaded={uploaded}, verified={verified}, skipped={skipped}', flush=True)
    print(f'Done: employees={len(employees)}, required_types={len(required)}, uploaded={uploaded}, verified={verified}, skipped={skipped}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
