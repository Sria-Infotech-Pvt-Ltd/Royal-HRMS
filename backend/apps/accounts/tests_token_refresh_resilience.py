"""
A transient database failure during a silent token refresh must not cost the user their session.

The server answers a database failure with 503 (never 401), and because the old refresh token is only blacklisted when the
write succeeds, a failed attempt leaves it valid so the retry works. Only a refresh token that is actually invalid,
expired or missing is answered with 401, which is what ends the session on the frontend.
"""
from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.factories import make_role, make_user


class TokenRefreshResilienceTests(TestCase):
    def setUp(self):
        self.user = make_user('refresh-resilience@test.com', role=make_role('refresh_role'), employee_id='EMP00120')
        self.refresh = str(RefreshToken.for_user(self.user))
        self.client = APIClient(raise_request_exception=False)
        self.url = reverse('token-refresh')

    def post(self, refresh: str | None = None):
        client = APIClient(raise_request_exception=False)
        if refresh is not None:
            client.cookies['royal_refresh_token'] = refresh
        return client.post(self.url, {}, format='json')

    def test_a_good_refresh_token_is_accepted_and_rotated(self):
        response = self.post(self.refresh)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('royal_access_token', response.cookies)
        self.assertIn('royal_refresh_token', response.cookies)
        self.assertEqual(BlacklistedToken.objects.count(), 1)

    def test_a_database_failure_is_a_503_not_a_401(self):
        with patch.object(RefreshToken, 'blacklist', side_effect=OperationalError('SSL error: unexpected eof while reading')):
            response = self.post(self.refresh)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'error')
        self.assertNotIn('royal_access_token', response.cookies)         # nothing half-issued

    def test_the_same_refresh_token_works_once_the_database_is_back(self):
        with patch.object(RefreshToken, 'blacklist', side_effect=OperationalError('server closed the connection unexpectedly')):
            self.assertEqual(self.post(self.refresh).status_code, 503)
        self.assertEqual(BlacklistedToken.objects.count(), 0)            # the failed attempt consumed nothing
        recovered = self.post(self.refresh)                              # the frontend's next attempt
        self.assertEqual(recovered.status_code, 200, recovered.content)
        self.assertIn('royal_access_token', recovered.cookies)

    def test_several_failures_in_a_row_still_leave_the_session_recoverable(self):
        with patch.object(RefreshToken, 'blacklist', side_effect=OperationalError('could not translate host name')):
            statuses = [self.post(self.refresh).status_code for _ in range(3)]
        self.assertEqual(statuses, [503, 503, 503])
        self.assertEqual(self.post(self.refresh).status_code, 200)

    def test_an_invalid_refresh_token_is_a_401(self):
        response = self.post('this.is.not-a-token')
        self.assertEqual(response.status_code, 401)

    def test_a_missing_refresh_cookie_is_a_401(self):
        self.assertEqual(self.post(None).status_code, 401)

    def test_a_refresh_token_that_was_already_rotated_out_is_a_401(self):
        self.assertEqual(self.post(self.refresh).status_code, 200)       # first use rotates and blacklists it
        self.assertEqual(self.post(self.refresh).status_code, 401)       # the old one is now genuinely dead


class ConnectionRecoveryTests(SimpleTestCase):
    """What the 503 path relies on: once a connection is lost, the next query simply opens a fresh one.

    SimpleTestCase (no wrapping transaction) because closing a connection inside one is an error in Django."""
    databases = {'default'}

    def test_a_closed_connection_is_reopened_by_the_next_query(self):
        from django.db import connection
        connection.close()
        self.assertIsNone(connection.connection)
        with connection.cursor() as cursor:
            cursor.execute('select 1')
            self.assertEqual(cursor.fetchone(), (1,))
        self.assertIsNotNone(connection.connection)

    def _connection_flagged_after_an_error(self):
        """A live connection that Django has flagged because a query on it raised a database error.

        close_at is cleared so that only the health check (not the connection's age, which depends on CONN_MAX_AGE and
        so on the environment) can decide whether it is discarded."""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('select 1')
        connection.close_at = None
        connection.errors_occurred = True           # what Django sets when a query on it raised a database error
        return connection

    def test_a_connection_that_died_mid_request_is_discarded_not_reused(self):
        from django.db import connections
        connection = self._connection_flagged_after_an_error()
        # `connection` is a lazy proxy; the health check lives on the real connection wrapper behind it.
        with patch.object(connections[connection.alias], 'is_usable', return_value=False):   # the server really dropped it
            connection.close_if_unusable_or_obsolete()                                        # runs at the start and end of every request
        self.assertIsNone(connection.connection)
        with connection.cursor() as cursor:
            cursor.execute('select 1')               # the next request gets a working connection
            self.assertEqual(cursor.fetchone(), (1,))

    def test_a_flagged_connection_that_still_works_is_kept(self):
        """Django's own rule: an error flag alone does not throw a healthy connection away, it is checked first."""
        connection = self._connection_flagged_after_an_error()
        connection.close_if_unusable_or_obsolete()
        self.assertIsNotNone(connection.connection)
        self.assertFalse(connection.errors_occurred)
