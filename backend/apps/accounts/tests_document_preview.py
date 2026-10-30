"""
Document Center preview / download through the signed link (file_url).

The browser fetches file_url with a plain fetch / link — no Authorization
header, and the 15-minute access cookie may already have expired. The link
carries its company ('s' in the signed token), so it still opens the file in
the right company schema instead of failing on public (was an unhandled 500).
"""
from __future__ import annotations

from unittest import mock
from urllib.parse import parse_qs, urlparse

import requests
from django.core import signing
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests_policy_ack_contacts import PDF, PolicyFixture
from config.test_runner import TEST_SCHEMA_NAME


def _upstream(content_type='application/octet-stream', status=200):
    r = mock.Mock(status_code=status, headers={'content-type': content_type, 'content-length': str(len(PDF))})
    r.iter_content.return_value = [PDF]
    if status >= 400:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(response=r)
    return r


class DocumentPreviewTests(PolicyFixture):
    def setUp(self):
        super().setUp()
        p = mock.patch('apps.accounts.views.cloudinary.utils.private_download_url', return_value='https://cdn.example/dl')
        p.start()
        self.addCleanup(p.stop)

    def link(self, user=None, doc=None):
        """file_url exactly as the Document Center list returns it."""
        resp = self.api(user or self.emp).get(reverse('document-list-create'))
        doc = doc or self.policy
        url = next(d['file_url'] for d in resp.data['data']['results'] if d['id'] == doc.pk)
        return url

    def fetch(self, url, client=None, upstream=None):
        parsed = urlparse(url)
        with mock.patch('apps.accounts.views.http_req.get', return_value=upstream or _upstream()) as get:
            resp = (client or APIClient()).get(parsed.path, {'t': parse_qs(parsed.query)['t'][0]})
        return resp, get

    def token(self, payload):
        return f'/api/documents/{self.policy.pk}/?t={signing.dumps(payload, salt="doc-dl")}'

    def test_preview_works_without_access_cookie(self):
        url = self.link()
        resp, get = self.fetch(url)                       # fresh client: no cookie, like an expired session
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertEqual(resp['Content-Disposition'], 'inline; filename="p.pdf"')
        self.assertEqual(b''.join(resp.streaming_content), PDF)
        get.assert_called_once()                          # one upstream fetch per request

    def test_link_is_bound_to_issuing_company(self):
        token = parse_qs(urlparse(self.link()).query)['t'][0]
        self.assertEqual(signing.loads(token, salt='doc-dl'), {'id': self.policy.pk, 's': TEST_SCHEMA_NAME})

    def test_upstream_pdf_type_is_kept(self):
        resp, _ = self.fetch(self.link(), upstream=_upstream('application/pdf'))
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_download_uses_same_link_with_cookie(self):
        resp, _ = self.fetch(self.link(), client=self.api(self.emp))
        self.assertEqual(resp.status_code, 200)

    def test_invalid_or_mismatched_token_rejected(self):
        resp = APIClient().get(f'/api/documents/{self.policy.pk}/', {'t': 'tampered'})
        self.assertEqual(resp.status_code, 401)
        other = self.make_doc('Other')
        bad = signing.dumps({'id': other.pk, 's': TEST_SCHEMA_NAME}, salt='doc-dl')
        resp = APIClient().get(f'/api/documents/{self.policy.pk}/', {'t': bad})
        self.assertEqual(resp.status_code, 401)

    def test_unknown_company_in_token_is_not_found(self):
        resp, get = self.fetch(self.token({'id': self.policy.pk, 's': 'tenant_does_not_exist'}))
        self.assertEqual(resp.status_code, 404)
        get.assert_not_called()

    def test_legacy_token_without_company(self):
        legacy = self.token({'id': self.policy.pk})
        resp, _ = self.fetch(legacy)                      # no cookie: clear 401, not a 500
        self.assertEqual(resp.status_code, 401)
        resp, _ = self.fetch(legacy, client=self.api(self.emp))
        self.assertEqual(resp.status_code, 200)

    def test_missing_or_archived_document(self):
        url = self.link()
        self.policy.is_active = False
        self.policy.save(update_fields=['is_active'])
        resp, get = self.fetch(url)
        self.assertEqual(resp.status_code, 404)
        get.assert_not_called()

    def test_storage_failure_is_reported_not_500(self):
        resp, _ = self.fetch(self.link(), upstream=_upstream(status=404))
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.data['message'], 'File temporarily unavailable.')

    def test_metadata_still_needs_permission(self):
        detail = reverse('document-detail', kwargs={'pk': self.policy.pk})
        self.assertEqual(self.api(self.no_perm).get(detail).status_code, 403)
        self.assertIn(APIClient().get(detail).status_code, (401, 403))
