from datetime import date, timedelta

from vaccines.engine import VaccinationEngine
from vaccines.models import DependencyRule, Product, Series, SeriesProduct, SeriesRule, Vaccine
from .base import BaseVaccinationTestCase


class TestSeriesDependenciesAndAvailability(BaseVaccinationTestCase):
    def create_pneumo_series(self, prevenar_available=True, primovax_available=True, include_primovax=True):
        prevenar_vaccine = Vaccine.objects.create(name='Prevenar13', live=False)
        prevenar = Product.objects.create(vaccine=prevenar_vaccine, manufacturer='Pfizer', available=prevenar_available)
        primovax = None

        series = Series.objects.create(name='Pneumo', mixing_policy=Series.MIXING_FLEXIBLE, min_valid_interval_days=28)
        SeriesProduct.objects.create(series=series, product=prevenar, priority=0)
        SeriesRule.objects.create(
            series=series,
            slot_number=1,
            prior_valid_doses=0,
            min_age_days=60,
            recommended_age_days=60,
            overdue_age_days=90,
            min_interval_days=0,
            product=prevenar,
        )

        if include_primovax:
            primovax_vaccine = Vaccine.objects.create(name='Primovax', live=False)
            primovax = Product.objects.create(vaccine=primovax_vaccine, manufacturer='Acme', available=primovax_available)
            SeriesProduct.objects.create(series=series, product=primovax, priority=1)
            SeriesRule.objects.create(
                series=series,
                slot_number=1,
                prior_valid_doses=0,
                min_age_days=75,
                recommended_age_days=75,
                overdue_age_days=105,
                min_interval_days=0,
                product=primovax,
            )

        return series, prevenar, primovax

    def evaluate_at_age(self, child):
        return VaccinationEngine(child, evaluation_date=date.today()).evaluate()

    def test_available_candidate_is_selected(self):
        self.create_pneumo_series(prevenar_available=False, primovax_available=True)
        child = self.make_child('Pneumo Candidate', age_days=80)

        result = self.evaluate_at_age(child)

        self.assertIn('Primovax', self.due_names(result))
        self.assertEqual(result['due_but_unavailable'], [])

    def test_due_but_unavailable_is_reported_when_no_candidate_available(self):
        self.create_pneumo_series(prevenar_available=False, primovax_available=False)
        child = self.make_child('Pneumo Unavailable', age_days=80)

        result = self.evaluate_at_age(child)

        self.assertNotIn('Prevenar13', self.due_names(result))
        self.assertNotIn('Primovax', self.due_names(result))
        self.assertEqual([item['vaccine'].name for item in result['due_but_unavailable']], ['Primovax'])

    def test_dependency_blocks_when_anchor_slot_is_missing(self):
        pneumo, prevenar, primovax = self.create_pneumo_series(prevenar_available=True, primovax_available=False, include_primovax=False)
        DependencyRule.objects.create(dependent_series=pneumo, dependent_slot_number=1, anchor_series=self.dtp_series, anchor_slot_number=1, min_offset_days=15, block_if_anchor_missing=True)
        child = self.make_child('Dependency Blocked', age_days=80)

        result = self.evaluate_at_age(child)

        self.assertNotIn('Prevenar13', self.due_names(result))
        self.assertNotIn('Primovax', self.upcoming_names(result))
        self.assertEqual([item['vaccine'].name for item in result['blocked']], ['Prevenar13'])

    def test_dependency_pushes_next_date_after_anchor_offset(self):
        pneumo, prevenar, primovax = self.create_pneumo_series(prevenar_available=True, primovax_available=False, include_primovax=False)
        DependencyRule.objects.create(dependent_series=pneumo, dependent_slot_number=1, anchor_series=self.dtp_series, anchor_slot_number=1, min_offset_days=15, block_if_anchor_missing=True)
        child = self.make_child('Dependency Upcoming', age_days=80)
        self.give_dose(child, self.penta, days_ago=10)

        result = self.evaluate_at_age(child)

        self.assertNotIn('Prevenar13', self.due_names(result))
        self.assertIn('Prevenar13', self.upcoming_names(result))
        upcoming_item = next(item for item in result['upcoming'] if item[0].name == 'Prevenar13')
        self.assertEqual(upcoming_item[1], date.today() + timedelta(days=5))

    def test_dependency_allows_due_once_offset_is_met(self):
        pneumo, prevenar, primovax = self.create_pneumo_series(prevenar_available=True, primovax_available=False, include_primovax=False)
        DependencyRule.objects.create(dependent_series=pneumo, dependent_slot_number=1, anchor_series=self.dtp_series, anchor_slot_number=1, min_offset_days=15, block_if_anchor_missing=True)
        child = self.make_child('Dependency Due', age_days=90)
        self.give_dose(child, self.penta, days_ago=20)

        result = self.evaluate_at_age(child)

        self.assertIn('Prevenar13', self.due_names(result))
