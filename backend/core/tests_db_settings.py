"""The local-development database tuning in core/db_settings.py must change NOTHING unless DEBUG is on."""
from django.test import SimpleTestCase

from core.db_settings import (
    DEFAULT_CONN_MAX_AGE_SECONDS, LOCAL_DEBUG_CONNECT_TIMEOUT_SECONDS, LOCAL_DEBUG_KEEPALIVE_OPTIONS,
    apply_local_debug_options, default_conn_max_age, health_checks_enabled,
)

# What production and UAT run with today: only the sslmode setting.
PRODUCTION_OPTIONS = {'sslmode': 'require'}


class ProductionIsUntouchedTests(SimpleTestCase):
    def test_options_are_left_exactly_as_they_were_when_debug_is_off(self):
        options = dict(PRODUCTION_OPTIONS)
        self.assertEqual(apply_local_debug_options(options, debug=False), PRODUCTION_OPTIONS)
        self.assertEqual(options, PRODUCTION_OPTIONS)            # and not just the return value: the dict itself

    def test_the_default_connection_lifetime_is_still_sixty_seconds_when_debug_is_off(self):
        self.assertEqual(default_conn_max_age(False), 60)
        self.assertEqual(DEFAULT_CONN_MAX_AGE_SECONDS, 60)

    def test_health_checks_stay_off_when_debug_is_off_whatever_the_lifetime(self):
        self.assertFalse(health_checks_enabled(False, 60))
        self.assertFalse(health_checks_enabled(False, 0))


class LocalDebugTests(SimpleTestCase):
    def test_a_connect_timeout_and_keepalives_are_added(self):
        options = apply_local_debug_options(dict(PRODUCTION_OPTIONS), debug=True)
        self.assertEqual(options['connect_timeout'], LOCAL_DEBUG_CONNECT_TIMEOUT_SECONDS)
        for name, value in LOCAL_DEBUG_KEEPALIVE_OPTIONS.items():
            self.assertEqual(options[name], value)
        self.assertEqual(options['sslmode'], 'require')           # existing options are kept

    def test_the_connect_timeout_fits_inside_the_browsers_fifteen_second_request_window(self):
        self.assertLess(LOCAL_DEBUG_CONNECT_TIMEOUT_SECONDS, 15)

    def test_a_dead_peer_is_detected_within_about_a_minute(self):
        keepalives = LOCAL_DEBUG_KEEPALIVE_OPTIONS
        detection = keepalives['keepalives_idle'] + keepalives['keepalives_interval'] * keepalives['keepalives_count']
        self.assertEqual(detection, 60)

    def test_values_already_set_for_example_by_the_database_url_win(self):
        options = apply_local_debug_options({'sslmode': 'require', 'connect_timeout': 3, 'keepalives_idle': 5}, debug=True)
        self.assertEqual((options['connect_timeout'], options['keepalives_idle']), (3, 5))

    def test_connections_are_closed_after_every_request_by_default(self):
        self.assertEqual(default_conn_max_age(True), 0)

    def test_health_checks_are_enabled_only_when_connections_are_actually_kept_open(self):
        self.assertTrue(health_checks_enabled(True, 60))
        self.assertFalse(health_checks_enabled(True, 0))
