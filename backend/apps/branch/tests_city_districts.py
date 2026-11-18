"""The Company Code City drop-down offers every district of the state, not only the towns seeded at install."""
from __future__ import annotations

from unittest import mock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_user
from apps.branch.models import Branch, City, State
from apps.branch.services_cities import _official_districts, ensure_state_districts

DISTRICTS = ('Adilabad', 'Hyderabad', 'Mahabubnagar', 'Mulugu', 'Nirmal', 'Warangal Urban')


def _telangana() -> State:
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    return state


def _patch_districts(names=DISTRICTS):
    _official_districts.cache_clear()
    return mock.patch('apps.branch.services_cities._official_districts', return_value=tuple(names))


class EnsureStateDistrictsTests(TestCase):
    def setUp(self):
        self.state = _telangana()
        City.objects.filter(state=self.state).delete()

    def test_adds_only_the_missing_districts(self):
        City.objects.create(name='Hyderabad', state=self.state)
        City.objects.create(name='Ramagundam', state=self.state)      # a town, not a district: stays
        with _patch_districts():
            added = ensure_state_districts(self.state)
        names = set(City.objects.filter(state=self.state).values_list('name', flat=True))
        self.assertEqual(added, 5)
        self.assertEqual(names, {'Hyderabad', 'Ramagundam', 'Adilabad', 'Mahabubnagar', 'Mulugu', 'Nirmal', 'Warangal Urban'})

    def test_a_second_run_adds_nothing(self):
        with _patch_districts():
            ensure_state_districts(self.state)
            self.assertEqual(ensure_state_districts(self.state), 0)
        self.assertEqual(City.objects.filter(state=self.state).count(), len(DISTRICTS))

    def test_a_near_copy_of_an_existing_spelling_is_not_added_twice(self):
        City.objects.create(name='Mahbubnagar', state=self.state)
        with _patch_districts():
            ensure_state_districts(self.state)
        self.assertFalse(City.objects.filter(state=self.state, name='Mahabubnagar').exists())
        self.assertEqual(City.objects.filter(state=self.state, name__icontains='ahb').count(), 1)

    def test_existing_cities_keep_their_row_and_a_switched_off_one_stays_off(self):
        kept = City.objects.create(name='Adilabad', state=self.state, is_active=False)
        with _patch_districts():
            ensure_state_districts(self.state)
        kept.refresh_from_db()
        self.assertFalse(kept.is_active)
        self.assertEqual(City.objects.filter(state=self.state, name='Adilabad').count(), 1)

    def test_a_branch_stays_on_its_city(self):
        city = City.objects.create(name='Hyderabad', state=self.state)
        branch = Branch.objects.create(branch_code='K01', branch_name='Kondapur', address='1 Road', state=self.state, city=city)
        with _patch_districts():
            ensure_state_districts(self.state)
        branch.refresh_from_db()
        self.assertEqual(branch.city_id, city.id)

    def test_a_failing_district_source_leaves_the_list_as_it_was(self):
        City.objects.create(name='Hyderabad', state=self.state)
        _official_districts.cache_clear()
        with mock.patch('apps.branch.services_cities._official_districts', side_effect=RuntimeError('dataset missing')):
            self.assertEqual(ensure_state_districts(self.state), 0)
        self.assertEqual(City.objects.filter(state=self.state).count(), 1)

    def test_an_unknown_state_adds_nothing(self):
        other = State.objects.create(name='Nowhere Land', code='NW')
        with _patch_districts(()):
            self.assertEqual(ensure_state_districts(other), 0)


class CityListEndpointTests(TestCase):
    def test_the_city_list_includes_every_district(self):
        state = _telangana()
        City.objects.filter(state=state).delete()
        City.objects.create(name='Hyderabad', state=state)
        client = APIClient()
        client.force_authenticate(make_user(email='cities@example.test'))
        with _patch_districts():
            response = client.get(reverse('city-list', args=[state.id]))
        self.assertEqual(response.status_code, 200)
        names = [city['name'] for city in response.data['data']]
        self.assertEqual(names, sorted(set(DISTRICTS)))
