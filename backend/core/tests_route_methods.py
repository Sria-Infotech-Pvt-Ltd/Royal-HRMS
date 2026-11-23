"""
Wrong verbs and malformed ids must give a clear client error, never "An unexpected error occurred" (HTTP 500).

Found by the full-project crawl: a view that serves both a list URL and a detail URL has methods that fit only one of them, so a
call such as PATCH on the list URL raised TypeError (500 plus a traceback in errors.log); and ids that are not numbers
(/api/documents/abc/) raised ValueError (500). Now: 405 and "not found".
"""
import inspect
import re

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.accounts.models import User
from core.view_mixins import RouteMatchedMethodsMixin

PARAM = re.compile(r'<(?:\w+:)?(\w+)>')


def _api_routes(patterns=None, prefix=''):
    for pattern in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _api_routes(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern) and (prefix + str(pattern.pattern)).startswith('api/'):
            yield prefix + str(pattern.pattern), pattern


class EveryMethodFitsItsRouteTests(SimpleTestCase):
    def test_a_view_method_that_cannot_take_the_urls_parameters_is_guarded_with_the_mixin(self):
        unguarded = []
        for route, pattern in _api_routes():
            view_class = getattr(pattern.callback, 'view_class', None)
            if view_class is None or issubclass(view_class, RouteMatchedMethodsMixin):
                continue
            url_params = PARAM.findall(route)
            for method in ('get', 'post', 'put', 'patch', 'delete'):
                handler = getattr(view_class, method, None)
                if not callable(handler):
                    continue
                parameters = inspect.signature(handler).parameters
                if any(p.kind is p.VAR_KEYWORD for p in parameters.values()):
                    continue
                accepted = {name for name in parameters if name not in ('self', 'request')}
                required = {name for name, p in parameters.items() if name not in ('self', 'request') and p.default is p.empty}
                if not set(url_params) <= accepted or not required <= set(url_params):
                    unguarded.append(f'{method.upper()} /{route} [{view_class.__name__}]')
        self.assertEqual(unguarded, [], 'These views would answer 500 on a wrong verb: add RouteMatchedMethodsMixin (core/view_mixins.py)')


class WrongVerbAndBadIdTests(TestCase):
    def setUp(self):
        cache.clear()
        admin = make_user('route-admin@test.com', employee_id='RTE001')
        User.objects.filter(pk=admin.pk).update(is_superuser=True)
        self.client = APIClient(raise_request_exception=False)
        self.client.force_authenticate(user=User.objects.get(pk=admin.pk))

    def test_the_wrong_verb_on_a_shared_view_is_405_not_500(self):
        cases = [
            ('get', '/api/settings/onboarding-fields/some_key/'), ('patch', '/api/settings/onboarding-fields/'), ('delete', '/api/settings/onboarding-fields/'),
            ('get', '/api/settings/document-types/some_key/'), ('patch', '/api/settings/document-types/'),
            ('get', '/api/leave/policy/casual/'), ('put', '/api/leave/policy/'), ('delete', '/api/leave/policy/'),
            ('get', '/api/onboarding/education-experience-field-config/abc/'), ('patch', '/api/onboarding/education-experience-field-config/'),
            ('post', '/api/onboarding/documents/1/'), ('post', '/api/onboarding/custom-file-fields/1/'),
        ]
        for verb, url in cases:
            response = getattr(self.client, verb)(url)
            self.assertEqual(response.status_code, 405, f'{verb.upper()} {url} -> {response.status_code}')

    def test_a_malformed_id_is_not_found_with_a_readable_message(self):
        for url, expected in [
            ('/api/onboarding/documents/abc/', 'Document not found.'),
            ('/api/onboarding/custom-file-fields/abc/', 'File not found.'),
            ('/api/documents/abc/', 'not found'),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404, f'{url} -> {response.status_code}')
            self.assertIn(expected.lower(), str(response.json().get('message', '')).lower())
