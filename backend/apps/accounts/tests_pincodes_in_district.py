"""The PIN codes of one district, for the address form's PIN code drop-down (uses the offline PIN table; no database)."""
from django.test import SimpleTestCase

from apps.accounts.views_pincode import _closest, _normalise, pincodes_for_district


class NameMatchingTests(SimpleTestCase):
    def test_names_are_compared_ignoring_case_punctuation_and_spacing(self):
        self.assertEqual(_normalise('Medchal–Malkajgiri'), _normalise('MEDCHAL MALKAJGIRI'))
        self.assertEqual(_normalise('  Tamil   Nadu '), 'tamil nadu')

    def test_a_close_spelling_finds_the_dataset_name(self):
        pool = ['JANGOAN', 'JAGITIAL', 'KUMURAM BHEEM ASIFABAD', 'HYDERABAD']
        self.assertEqual(_closest('Jangaon', pool), 'JANGOAN')
        self.assertEqual(_closest('Jagtial', pool), 'JAGITIAL')
        self.assertEqual(_closest('Komaram Bheem Asifabad', pool), 'KUMURAM BHEEM ASIFABAD')
        self.assertEqual(_closest('hyderabad', pool), 'HYDERABAD')

    def test_a_different_name_is_not_forced_into_a_match(self):
        self.assertIsNone(_closest('Narnia', ['HYDERABAD', 'WARANGAL']))
        self.assertIsNone(_closest('', ['HYDERABAD']))


class PincodesForDistrictTests(SimpleTestCase):
    def test_lists_the_districts_pin_codes_lowest_first_each_with_an_area(self):
        rows = pincodes_for_district('Telangana', 'Hyderabad')
        self.assertGreater(len(rows), 20)
        codes = [row['pincode'] for row in rows]
        self.assertEqual(codes, sorted(codes))
        self.assertIn('500081', codes)
        self.assertTrue(all(row['area'] for row in rows[:5]))
        self.assertTrue(all(len(code) == 6 and code.isdigit() for code in codes))

    def test_state_and_district_can_be_written_any_way(self):
        self.assertEqual(pincodes_for_district('TELANGANA', 'hyderabad'), pincodes_for_district('Telangana', 'Hyderabad'))

    def test_a_district_the_dataset_spells_differently_still_works(self):
        self.assertTrue(pincodes_for_district('Telangana', 'Jangaon'))
        self.assertTrue(pincodes_for_district('Telangana', 'Medchal–Malkajgiri'))

    def test_only_this_states_pin_codes_when_two_states_share_a_district_name(self):
        maharashtra = {row['pincode'] for row in pincodes_for_district('Maharashtra', 'Aurangabad')}
        bihar = {row['pincode'] for row in pincodes_for_district('Bihar', 'Aurangabad')}
        self.assertTrue(maharashtra and bihar)
        self.assertFalse(maharashtra & bihar)

    def test_unknown_or_missing_names_give_an_empty_list(self):
        self.assertEqual(pincodes_for_district('Telangana', 'Narnia'), [])
        self.assertEqual(pincodes_for_district('Atlantis', 'Hyderabad'), [])
        self.assertEqual(pincodes_for_district('', ''), [])

    def test_every_pin_code_belongs_to_the_district_it_was_asked_for(self):
        from apps.accounts.views_pincode import lookup_pincode
        for row in pincodes_for_district('Telangana', 'Warangal')[:15]:
            found = lookup_pincode(row['pincode'])
            self.assertEqual(found['state'], 'Telangana')
