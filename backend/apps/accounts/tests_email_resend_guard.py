"""Email Logs must never replay an email whose point is a one-time link (no database needed)."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.accounts import utils
from apps.accounts.models import EmailLog, PasswordResetToken
from apps.accounts.serializers_email_log import EmailLogSerializer
from apps.accounts.services_email_resend import resend_blocked_reason
from apps.accounts.views_email_log import EmailLogResendView

LINK = 'https://hrms.example.com/activate/11111111-1111-1111-1111-111111111111/'


class PolicyTests(SimpleTestCase):
    def test_an_invitation_may_not_be_replayed_and_the_advice_names_the_right_button_and_the_validity(self):
        reason = resend_blocked_reason('onboarding_invite', False)
        self.assertIn('Resend invitation', reason)
        self.assertIn(f'{utils.INVITE_VALIDITY_HOURS} hours', reason)

    def test_an_admin_password_reset_may_not_be_replayed(self):
        self.assertIn('Reset password', resend_blocked_reason('password_reset_by_admin', False))

    def test_any_email_flagged_as_holding_a_credential_may_not_be_replayed(self):
        self.assertIn('one-time credential', resend_blocked_reason('anything_else', True))

    def test_an_ordinary_email_may_be_replayed(self):
        self.assertIsNone(resend_blocked_reason('leave_approved', False))

    def test_the_serializer_exposes_the_reason_to_the_page(self):
        serializer = EmailLogSerializer()
        self.assertIn('Resend invitation', serializer.get_resend_blocked_reason(SimpleNamespace(template_name='onboarding_invite', has_sensitive_context=True)))
        self.assertIsNone(serializer.get_resend_blocked_reason(SimpleNamespace(template_name='leave_approved', has_sensitive_context=False)))


class LinkStorageTests(SimpleTestCase):
    def test_the_reset_link_is_redacted_and_flags_the_log_as_sensitive(self):
        context = {'employee_name': 'A', 'reset_link': LINK, 'company_name': 'Acme'}
        redacted = utils._redact_context(context)
        self.assertEqual(redacted['reset_link'], '[REDACTED]')
        self.assertNotEqual(redacted, context)             # this is exactly what marks has_sensitive_context
        self.assertEqual(redacted['employee_name'], 'A')

    def test_the_stored_copy_hides_every_occurrence_of_the_link_but_the_original_is_untouched(self):
        html = f'<a href="{LINK}">Set password</a> or paste {LINK}'
        stored = utils.hide_link_in_log(html, LINK)
        self.assertNotIn(LINK, stored)
        self.assertEqual(stored.count('[one-time link not stored]'), 2)
        self.assertEqual(html.count(LINK), 2)


class ActivationInviteLoggingTests(SimpleTestCase):
    """What send_activation_invite sends versus what it stores."""

    def run_invite(self, send_error=None):
        message = mock.MagicMock()
        if send_error:
            message.send.side_effect = send_error
        with mock.patch.object(utils, '_get_smtp_connection', return_value=(object(), 'hr@example.com', None)), \
                mock.patch.object(utils, '_get_company_branding', return_value=('Acme', '', '', '', '')), \
                mock.patch.object(utils, '_company_email_wrapper', side_effect=lambda html, *_rest: html), \
                mock.patch.object(utils, '_activation_link', return_value=LINK), \
                mock.patch.object(utils, '_build_message', return_value=message) as build, \
                mock.patch('apps.accounts.services_frontend_url.frontend_origin', return_value='https://hrms.example.com'), \
                mock.patch.object(PasswordResetToken, 'create_for_user', return_value=SimpleNamespace(id='tok')), \
                mock.patch.object(EmailLog, 'record') as record:
            user = SimpleNamespace(email='new.hire@example.com', full_name='New Hire', employee_id='EMP1')
            try:
                utils.send_activation_invite(user)
                raised = None
            except Exception as exc:        # noqa: BLE001 - the failure path re-raises whatever the mail server raised
                raised = exc
        return build.call_args.kwargs['html_body'], record.call_args.kwargs, raised

    def test_the_mail_that_is_sent_keeps_the_link_but_the_log_does_not_and_is_flagged(self):
        sent_html, logged, raised = self.run_invite()
        self.assertIsNone(raised)
        self.assertIn(LINK, sent_html)
        self.assertNotIn(LINK, logged['body_html'])
        self.assertIn('[one-time link not stored]', logged['body_html'])
        self.assertTrue(logged['has_sensitive_context'])
        self.assertEqual((logged['status'], logged['template_name']), (EmailLog.STATUS_SENT, 'onboarding_invite'))

    def test_a_failed_send_is_logged_the_same_way_and_the_error_still_propagates(self):
        _sent, logged, raised = self.run_invite(send_error=ConnectionError('smtp down'))
        self.assertIsInstance(raised, ConnectionError)
        self.assertNotIn(LINK, logged['body_html'])
        self.assertTrue(logged['has_sensitive_context'])
        self.assertEqual(logged['status'], EmailLog.STATUS_FAILED)


class ResendEndpointTests(SimpleTestCase):
    @staticmethod
    def post(template_name, has_sensitive_context=False):
        log = SimpleNamespace(status=EmailLog.STATUS_FAILED, template_name=template_name, has_sensitive_context=has_sensitive_context, had_attachments=False)
        request = SimpleNamespace(user=SimpleNamespace(pk=1))
        with mock.patch('apps.accounts.views_email_log.has_perm', return_value=True), \
                mock.patch('apps.accounts.views_email_log.EmailLog') as email_log, \
                mock.patch('apps.accounts.views_email_log.resend_logged_email', return_value=SimpleNamespace()) as replay, \
                mock.patch('apps.accounts.views_email_log.EmailLogSerializer') as serializer:
            email_log.STATUS_FAILED = EmailLog.STATUS_FAILED
            email_log.objects.get.return_value = log
            email_log.objects.filter.return_value.exists.return_value = False
            serializer.return_value.data = {}
            response = EmailLogResendView().post(request, 'log-id')
        return response, replay

    def test_resending_an_invitation_is_refused_with_advice_and_nothing_is_sent(self):
        response, replay = self.post('onboarding_invite')
        self.assertEqual(response.status_code, 409)
        self.assertIn('Resend invitation', response.data['message'])
        replay.assert_not_called()

    def test_resending_an_admin_password_reset_is_refused(self):
        response, replay = self.post('password_reset_by_admin')
        self.assertEqual(response.status_code, 409)
        replay.assert_not_called()

    def test_a_credential_email_is_still_refused(self):
        response, replay = self.post('something', has_sensitive_context=True)
        self.assertEqual(response.status_code, 409)
        replay.assert_not_called()

    def test_an_ordinary_failed_email_can_still_be_resent(self):
        response, replay = self.post('leave_approved')
        self.assertEqual(response.status_code, 200)
        replay.assert_called_once()
