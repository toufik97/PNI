from datetime import date, timedelta

from .base import BaseVaccinationTestCase


class TestSeriesDependenciesAndAvailability(BaseVaccinationTestCase):
    optional_series_names = ('Pneumo',)

    def setUp(self):
        super().setUp()
        self.prevenar_product = self.product_map['Prevenar13']
        self.primovax_product = self.product_map['Primovax']

    def test_available_candidate_is_selected(self):
        self.prevenar_product.available = False
        self.prevenar_product.save(update_fields=['available'])
        child = self.make_child('Pneumo Candidate', age_days=80)
        self.give_dose(child, self.penta, days_ago=20)

        result = self.evaluate(child)

        self.assertIn('Primovax', self.due_names(result))
        self.assertEqual(result['due_but_unavailable'], [])

    def test_due_but_unavailable_is_reported_when_no_candidate_available(self):
        self.prevenar_product.available = False
        self.primovax_product.available = False
        self.prevenar_product.save(update_fields=['available'])
        self.primovax_product.save(update_fields=['available'])
        child = self.make_child('Pneumo Unavailable', age_days=80)
        self.give_dose(child, self.penta, days_ago=20)

        result = self.evaluate(child)

        self.assertNotIn('Prevenar13', self.due_names(result))
        self.assertNotIn('Primovax', self.due_names(result))
        self.assertEqual([item['vaccine'].name for item in result['due_but_unavailable']], ['Primovax'])

    def test_dependency_blocks_when_anchor_slot_is_missing(self):
        self.primovax_product.available = False
        self.primovax_product.save(update_fields=['available'])
        child = self.make_child('Dependency Blocked', age_days=80)

        result = self.evaluate(child)

        self.assertNotIn('Prevenar13', self.due_names(result))
        self.assertNotIn('Primovax', self.upcoming_names(result))
        self.assertEqual([item['vaccine'].name for item in result['blocked']], ['Prevenar13'])

    def test_dependency_pushes_next_date_after_anchor_offset(self):
        self.primovax_product.available = False
        self.primovax_product.save(update_fields=['available'])
        child = self.make_child('Dependency Upcoming', age_days=80)
        self.give_dose(child, self.penta, days_ago=10)

        result = self.evaluate(child)

        self.assertNotIn('Prevenar13', self.due_names(result))
        self.assertIn('Prevenar13', self.upcoming_names(result))
        upcoming_item = next(item for item in result['upcoming'] if item[0].name == 'Prevenar13')
        self.assertEqual(upcoming_item[1], date.today() + timedelta(days=5))

    def test_dependency_allows_due_once_offset_is_met(self):
        self.primovax_product.available = False
        self.primovax_product.save(update_fields=['available'])
        child = self.make_child('Dependency Due', age_days=90)
        self.give_dose(child, self.penta, days_ago=20)

        result = self.evaluate(child)

        self.assertIn('Prevenar13', self.due_names(result))

    def test_started_product_path_stays_on_same_product_when_available(self):
        child = self.make_child('Pneumo Continuity', age_days=140)
        self.give_dose(child, self.prevenar13, days_ago=60)

        result = self.evaluate(child)

        self.assertIn('Prevenar13', self.due_names(result))
        self.assertNotIn('Primovax', self.due_names(result))

    def test_transition_allows_switch_when_started_product_is_unavailable(self):
        self.prevenar_product.available = False
        self.prevenar_product.save(update_fields=['available'])
        child = self.make_child('Pneumo Switch', age_days=140)
        self.give_dose(child, self.prevenar13, days_ago=60)

        result = self.evaluate(child)

        self.assertNotIn('Prevenar13', self.due_names(result))
        self.assertIn('Primovax', self.due_names(result))
