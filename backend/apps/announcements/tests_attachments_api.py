"""Announcement images, PDFs and links through the real API: upload, validation, limits, editing, access control, downloads."""
from __future__ import annotations

import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import OrgUnit, Placement, Position
from apps.announcements.attachment_test_support import (
    LIST_URL, SIGNED_PREFIX, FakeStorageMixin, image_bytes, make_employee, make_poster, pdf_bytes, unique, upload_image, upload_pdf,
)
from apps.announcements.models import Announcement, AnnouncementAttachment
from apps.announcements.services_attachments import make_download_token
from apps.branch.models import Branch, City, State

BASE = {'title': 'Office move', 'body': 'We are moving.', 'category': 'general', 'visibility': 'all'}


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _branch() -> Branch:
    state = State.objects.create(name=unique('State'), code=unique('S')[:10])
    city = City.objects.create(name=unique('City'), state=state)
    return Branch.objects.create(branch_code=unique('BR'), branch_name=unique('Branch'), address='x', state=state, city=city)


class AttachmentApiTestCase(FakeStorageMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.poster = make_poster()
        self.client_ = _client(self.poster)

    def post(self, **fields):
        return self.client_.post(LIST_URL, {**BASE, **fields}, format='multipart')

    def create_with(self, **fields) -> dict:
        response = self.post(**fields)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['data']

    def detail(self, announcement_id: int) -> str:
        return f'{LIST_URL}{announcement_id}/'


class UploadTests(AttachmentApiTestCase):
    def test_valid_images_in_all_three_formats_are_stored(self):
        data = self.create_with(images=[
            upload_image('a.png'), upload_image('b.jpg', 'JPEG', 'image/jpeg'), upload_image('c.webp', 'WEBP', 'image/webp'),
        ])
        kinds = {(row['original_filename'], row['content_type']) for row in data['attachments']}
        self.assertEqual(kinds, {('a.png', 'image/png'), ('b.jpg', 'image/jpeg'), ('c.webp', 'image/webp')})
        self.assertTrue(all(row['attachment_type'] == 'image' and row['url'].startswith(SIGNED_PREFIX) for row in data['attachments']))
        self.assertEqual(len(self.stored), 3)
        self.assertEqual(AnnouncementAttachment.objects.count(), 3)

    def test_a_valid_pdf_is_stored_with_its_name_size_and_download_path(self):
        data = self.create_with(documents=[upload_pdf('Leave policy.pdf')])
        (row,) = data['attachments']
        self.assertEqual((row['attachment_type'], row['original_filename'], row['content_type']), ('document', 'Leave policy.pdf', 'application/pdf'))
        self.assertEqual(row['file_size'], len(pdf_bytes()))
        self.assertEqual(row['url'], '')                                     # documents are never shown from a direct address
        self.assertEqual(row['download_path'], f'/announcements/{data["id"]}/attachments/{row["id"]}/download/')

    def test_the_stored_name_is_generated_and_a_hostile_filename_is_neutralised(self):
        data = self.create_with(images=[SimpleUploadedFile('../../etc/passwd.png', image_bytes(), content_type='image/png')])
        (row,) = data['attachments']
        self.assertEqual(row['original_filename'], 'passwd.png')            # directories dropped from the name that is shown
        (stored_name,) = self.stored
        self.assertTrue(stored_name.startswith('announcements/'))
        self.assertNotIn('..', stored_name)
        self.assertNotIn('passwd', stored_name)                             # the uploaded name never reaches storage

    def test_an_announcement_without_attachments_still_works_as_before(self):
        response = self.client_.post(LIST_URL, BASE, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()['data']
        self.assertEqual((body['attachments'], body['links']), ([], []))


class RejectedUploadTests(AttachmentApiTestCase):
    def assert_rejected(self, response, *words):
        self.assertEqual(response.status_code, 400, response.content)
        message = json.dumps(response.json()).lower()
        for word in words:
            self.assertIn(word.lower(), message)
        self.assertFalse(Announcement.objects.exists())                      # nothing was created
        self.assertEqual(self.stored, {})                                    # and nothing was left in storage

    def test_unsupported_image_types_are_refused(self):
        for name, content_type in (('x.gif', 'image/gif'), ('x.svg', 'image/svg+xml'), ('x.bmp', 'image/bmp'), ('x.exe', 'application/octet-stream')):
            self.assert_rejected(self.post(images=[SimpleUploadedFile(name, image_bytes(), content_type=content_type)]), 'not accepted')

    def test_other_document_types_are_refused(self):
        for name, content_type in (('x.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'), ('x.txt', 'text/plain'), ('x.exe', 'application/pdf')):
            self.assert_rejected(self.post(documents=[SimpleUploadedFile(name, pdf_bytes(), content_type=content_type)]), 'not accepted')

    def test_a_declared_type_that_does_not_match_the_extension_is_refused(self):
        self.assert_rejected(self.post(images=[SimpleUploadedFile('photo.png', image_bytes('JPEG'), content_type='image/jpeg')]), 'not accepted')

    def test_a_file_whose_bytes_are_not_what_it_claims_is_refused(self):
        self.assert_rejected(self.post(images=[SimpleUploadedFile('photo.png', b'MZ' + b'\x00' * 200, content_type='image/png')]), "doesn't match")
        self.assert_rejected(self.post(documents=[SimpleUploadedFile('policy.pdf', b'just some text, not a pdf', content_type='application/pdf')]), "doesn't match")
        self.assert_rejected(self.post(images=[SimpleUploadedFile('photo.jpg', image_bytes('PNG'), content_type='image/jpeg')]), "doesn't match")

    def test_a_damaged_image_or_cut_off_pdf_is_refused(self):
        self.assert_rejected(self.post(images=[SimpleUploadedFile('photo.png', image_bytes()[:60], content_type='image/png')]), 'readable image')
        self.assert_rejected(self.post(documents=[SimpleUploadedFile('policy.pdf', b'%PDF-1.4\n1 0 obj\n' + b'x' * 3000, content_type='application/pdf')]), 'complete pdf')

    def test_files_over_5_mb_are_refused_and_an_empty_file_too(self):
        self.assert_rejected(self.post(documents=[SimpleUploadedFile('big.pdf', pdf_bytes(extra=700_000), content_type='application/pdf')]), '5 mb')
        self.assert_rejected(self.post(images=[SimpleUploadedFile('empty.png', b'', content_type='image/png')]), 'empty')

    def test_a_good_file_next_to_a_bad_one_stores_nothing(self):
        self.assert_rejected(self.post(images=[upload_image('ok.png'), SimpleUploadedFile('bad.png', b'nope', content_type='image/png')]), "doesn't match")


class LimitTests(AttachmentApiTestCase):
    def test_at_most_five_images_and_five_pdfs(self):
        self.create_with(images=[upload_image(f'{n}.png') for n in range(5)], documents=[upload_pdf(f'{n}.pdf') for n in range(5)])
        response = self.post(images=[upload_image(f'{n}.png') for n in range(6)])
        self.assertEqual(response.status_code, 400)
        self.assertIn('at most 5 images', json.dumps(response.json()))
        response = self.post(documents=[upload_pdf(f'{n}.pdf') for n in range(6)])
        self.assertIn('at most 5 pdf', json.dumps(response.json()).lower())
        self.assertEqual(Announcement.objects.count(), 1)

    def test_the_limit_counts_what_the_announcement_already_has(self):
        data = self.create_with(images=[upload_image(f'{n}.png') for n in range(4)])
        response = self.client_.patch(self.detail(data['id']), {'images': [upload_image('a.png'), upload_image('b.png')]}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AnnouncementAttachment.objects.count(), 4)
        ok = self.client_.patch(self.detail(data['id']), {'images': [upload_image('a.png')]}, format='multipart')
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(AnnouncementAttachment.objects.count(), 5)

    def test_removing_makes_room_in_the_same_edit(self):
        data = self.create_with(images=[upload_image(f'{n}.png') for n in range(5)])
        gone = [row['id'] for row in data['attachments'][:2]]
        response = self.client_.patch(
            self.detail(data['id']), {'images': [upload_image('new1.png'), upload_image('new2.png')], 'remove_attachment_ids': gone}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(AnnouncementAttachment.objects.count(), 5)


class EditingTests(AttachmentApiTestCase):
    def test_editing_without_mentioning_attachments_or_links_keeps_them(self):
        data = self.create_with(
            images=[upload_image()], documents=[upload_pdf()], links=json.dumps([{'title': 'Map', 'url': 'https://maps.example.com/office'}]))
        for method, payload in (('patch', {'title': 'New title'}), ('put', {**BASE, 'title': 'Newer title'})):
            response = getattr(self.client_, method)(self.detail(data['id']), payload, format='json')
            self.assertEqual(response.status_code, 200, response.content)
            body = response.json()['data']
            self.assertEqual(len(body['attachments']), 2)
            self.assertEqual(body['links'], [{'title': 'Map', 'url': 'https://maps.example.com/office'}])
        self.assertEqual(AnnouncementAttachment.objects.count(), 2)

    def test_an_attachment_can_be_removed_and_its_file_is_deleted_after_commit(self):
        data = self.create_with(images=[upload_image('keep.png'), upload_image('drop.png')])
        drop = next(row for row in data['attachments'] if row['original_filename'] == 'drop.png')
        dropped_name = AnnouncementAttachment.objects.get(pk=drop['id']).file.name
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client_.patch(self.detail(data['id']), {'remove_attachment_ids': [drop['id']]}, format='multipart')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row['original_filename'] for row in response.json()['data']['attachments']], ['keep.png'])
        self.assertIn(dropped_name, self.deleted)
        self.assertEqual(len(self.stored), 1)

    def test_one_cannot_remove_another_announcements_attachment(self):
        mine = self.create_with(images=[upload_image()])
        other = self.create_with(images=[upload_image('other.png')])
        stolen = other['attachments'][0]['id']
        response = self.client_.patch(self.detail(mine['id']), {'remove_attachment_ids': [stolen]}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(AnnouncementAttachment.objects.filter(pk=stolen).exists())

    def test_deleting_the_announcement_deletes_its_files(self):
        data = self.create_with(images=[upload_image()], documents=[upload_pdf()])
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client_.delete(self.detail(data['id'])).status_code, 200)
        self.assertEqual(AnnouncementAttachment.objects.count(), 0)
        self.assertEqual(self.stored, {})

    def test_an_edit_that_fails_changes_nothing(self):
        data = self.create_with(images=[upload_image('keep.png')])
        response = self.client_.patch(
            self.detail(data['id']), {'title': 'Renamed', 'images': [SimpleUploadedFile('bad.png', b'nope', content_type='image/png')]}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Announcement.objects.get(pk=data['id']).title, BASE['title'])
        self.assertEqual(AnnouncementAttachment.objects.count(), 1)

    def test_a_storage_failure_midway_leaves_no_stray_files(self):
        from apps.announcements.services_attachments import store_new_files
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        saves = []

        def flaky_save(storage, name, content):
            if saves:
                raise RuntimeError('storage went away')
            saves.append(name)
            self.stored[name] = b'x'
            return name

        with mock.patch('core.storage.ImageKitStorage._save', flaky_save), self.assertRaises(RuntimeError):
            store_new_files(announcement, [upload_image('a.png'), upload_image('b.png')], [])
        self.assertEqual(self.stored, {})                                    # the first upload was taken back
        self.assertEqual(AnnouncementAttachment.objects.count(), 1)          # (its row is rolled back by the caller's transaction)


class LinkTests(AttachmentApiTestCase):
    def links(self, value) -> object:
        return self.post(links=json.dumps(value))

    def test_valid_links_are_stored_in_order(self):
        value = [{'title': 'Handbook', 'url': 'https://example.com/handbook'}, {'title': 'Form', 'url': 'http://intranet.local/form?id=1#top'}]
        response = self.links(value)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['data']['links'], value)

    def test_only_web_addresses_are_accepted(self):
        for url in ('javascript:alert(1)', 'data:text/html,<b>x</b>', 'ftp://example.com/f', 'file:///etc/passwd', 'example.com', 'https://', 'https://user:pw@example.com/', 'https://exa mple.com', ''):
            response = self.links([{'title': 'Bad', 'url': url}])
            self.assertEqual(response.status_code, 400, url)
        self.assertFalse(Announcement.objects.exists())

    def test_a_link_needs_a_title_and_titles_and_counts_are_bounded(self):
        self.assertEqual(self.links([{'title': '  ', 'url': 'https://example.com'}]).status_code, 400)
        self.assertEqual(self.links([{'title': 'x' * 101, 'url': 'https://example.com'}]).status_code, 400)
        self.assertEqual(self.links([{'title': f'L{n}', 'url': 'https://example.com'} for n in range(6)]).status_code, 400)
        self.assertEqual(self.post(links='not json').status_code, 400)
        self.assertEqual(self.links({'title': 'x'}).status_code, 400)

    def test_links_can_be_sent_as_json_edited_and_cleared(self):
        response = self.client_.post(LIST_URL, {**BASE, 'links': [{'title': 'A', 'url': 'https://a.example.com'}]}, format='json')
        announcement_id = response.json()['data']['id']
        self.assertEqual(response.json()['data']['links'][0]['title'], 'A')
        edited = self.client_.patch(self.detail(announcement_id), {'links': [{'title': 'B', 'url': 'https://b.example.com'}]}, format='json')
        self.assertEqual(edited.json()['data']['links'], [{'title': 'B', 'url': 'https://b.example.com'}])
        cleared = self.client_.patch(self.detail(announcement_id), {'links': []}, format='json')
        self.assertEqual(cleared.json()['data']['links'], [])


class AccessTests(AttachmentApiTestCase):
    def setUp(self):
        super().setUp()
        self.branch_a, self.branch_b = _branch(), _branch()
        self.in_a = make_employee(branch=self.branch_a.branch_name)
        self.in_b = make_employee(branch=self.branch_b.branch_name)

    def branch_announcement(self) -> tuple[dict, dict]:
        data = self.create_with(visibility='branch', target_branch=self.branch_a.id, documents=[upload_pdf()], images=[upload_image()])
        return data, next(row for row in data['attachments'] if row['attachment_type'] == 'document')

    def download(self, user, announcement_id, attachment_id, **query):
        client = _client(user) if user else APIClient()
        return client.get(f'{LIST_URL}{announcement_id}/attachments/{attachment_id}/download/', query)

    def test_the_audience_sees_the_attachments_and_others_see_nothing_of_the_announcement(self):
        data, document = self.branch_announcement()
        seen = _client(self.in_a).get(self.detail(data['id']))
        self.assertEqual(seen.status_code, 200)
        self.assertEqual(len(seen.json()['data']['attachments']), 2)
        self.assertEqual(_client(self.in_b).get(self.detail(data['id'])).status_code, 404)
        listed = _client(self.in_b).get(LIST_URL).json()['data']['results']
        self.assertEqual(listed, [])

    def test_a_member_of_the_audience_is_sent_to_a_short_lived_signed_address(self):
        data, document = self.branch_announcement()
        response = self.download(self.in_a, data['id'], document['id'])
        self.assertEqual(response.status_code, 302)
        name = AnnouncementAttachment.objects.get(pk=document['id']).file.name
        self.assertEqual(response['Location'], f'{SIGNED_PREFIX}{name}?sig=300')       # five minutes, not the two-hour image address
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_someone_outside_the_audience_cannot_download_and_is_not_told_the_file_exists(self):
        data, document = self.branch_announcement()
        response = self.download(self.in_b, data['id'], document['id'])
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('Location', response)

    def test_a_signed_out_visitor_needs_to_sign_in(self):
        data, document = self.branch_announcement()
        self.assertEqual(self.download(None, data['id'], document['id']).status_code, 401)

    def test_the_link_from_the_e_mail_works_for_exactly_that_attachment_until_it_expires(self):
        data, document = self.branch_announcement()
        token = make_download_token(data['id'], document['id'])
        self.assertEqual(self.download(None, data['id'], document['id'], token=token).status_code, 302)
        other = next(row for row in data['attachments'] if row['attachment_type'] == 'image')
        self.assertEqual(self.download(None, data['id'], other['id'], token=token).status_code, 403)      # a different attachment
        self.assertEqual(self.download(None, data['id'], document['id'], token=token + 'x').status_code, 403)   # tampered
        with mock.patch('apps.announcements.services_attachments.EMAIL_LINK_MAX_AGE_SECONDS', -1):
            self.assertEqual(self.download(None, data['id'], document['id'], token=token).status_code, 403)    # expired

    def test_an_attachment_must_belong_to_the_announcement_in_the_address(self):
        data, document = self.branch_announcement()
        elsewhere = self.create_with()
        self.assertEqual(self.download(self.in_a, elsewhere['id'], document['id']).status_code, 404)

    def test_department_announcements_follow_the_org_unit(self):
        unit = OrgUnit.objects.create(name=unique('Dept'))
        member, outsider = make_employee(), make_employee()
        position = Position.objects.create(org_unit=unit, title=unique('Seat'), grade='L1')
        Placement.objects.create(position=position, employee=member, effective_from='2020-01-01')
        data = self.create_with(visibility='department', target_org_unit=unit.id, documents=[upload_pdf()])
        document = data['attachments'][0]
        self.assertEqual(self.download(member, data['id'], document['id']).status_code, 302)
        self.assertEqual(self.download(outsider, data['id'], document['id']).status_code, 404)

    def test_company_wide_announcements_reach_everyone(self):
        data = self.create_with(documents=[upload_pdf()])
        self.assertEqual(self.download(self.in_b, data['id'], data['attachments'][0]['id']).status_code, 302)


class DashboardTests(AttachmentApiTestCase):
    def test_the_dashboard_card_gets_a_picture_and_the_attachment_count(self):
        self.create_with(images=[upload_image()], documents=[upload_pdf()], links=json.dumps([{'title': 'A', 'url': 'https://a.example.com'}]))
        card = _client(make_employee()).get('/api/dashboard/announcement/').json()['data']
        self.assertTrue(card['image_url'].startswith(SIGNED_PREFIX))
        self.assertEqual(card['attachment_count'], 3)

    def test_the_dashboard_card_without_attachments_has_no_picture(self):
        self.create_with()
        card = _client(make_employee()).get('/api/dashboard/announcement/').json()['data']
        self.assertEqual((card['image_url'], card['attachment_count']), ('', 0))
