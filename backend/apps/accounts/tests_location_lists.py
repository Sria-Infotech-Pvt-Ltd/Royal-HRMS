"""The State and District drop-down lists must match the PIN code lookup exactly, so a Suggest / auto-fill can never write a name
that is missing from the list. No database needed."""
import indiapins
from django.test import SimpleTestCase

from apps.accounts.views_location import list_districts, list_states
from apps.accounts.views_pincode import lookup_pincode


class LocationListsTests(SimpleTestCase):
    def test_states_are_the_36_canonical_names_a_to_z(self):
        states = list_states()
        self.assertEqual(len(states), 36)
        self.assertEqual(states, sorted(states, key=str.casefold))
        self.assertIn('Telangana', states)

    def test_districts_are_a_to_z_and_unknown_state_is_empty(self):
        districts = list_districts('Telangana')
        self.assertEqual(districts, sorted(districts, key=str.casefold))
        self.assertIn('Hyderabad', districts)
        self.assertEqual(list_districts('Atlantis'), [])

    def test_every_pin_code_answer_is_in_the_lists_exactly(self):
        lists = {state: set(list_districts(state)) for state in list_states()}
        codes = set()
        for state in indiapins.states():
            codes.update(indiapins.pincodes_in_state(state))
        for code in sorted(codes):
            found = lookup_pincode(code)
            self.assertIsNotNone(found, code)
            if not found['district']:  # a few PIN codes carry no district in the dataset
                continue
            self.assertIn(found['district'], lists.get(found['state'], set()), code)
