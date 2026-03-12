from vaccines.engine import VaccinationEngine
from vaccines.models import Product, Series, SeriesProduct, SeriesRule, SeriesTransitionRule, Vaccine
from .base import BaseVaccinationTestCase


class TestSeriesTransitions(BaseVaccinationTestCase):
    def create_transition_series(self, *, mixing_policy):
        prevenar_vaccine = Vaccine.objects.create(name='Prevenar13', live=False)
        prevenar = Product.objects.create(vaccine=prevenar_vaccine, manufacturer='Pfizer', available=True)
        primovax_vaccine = Vaccine.objects.create(name='Primovax', live=False)
        primovax = Product.objects.create(vaccine=primovax_vaccine, manufacturer='Acme', available=True)

        series = Series.objects.create(name=f'Transition {mixing_policy} {Series.objects.count()}', mixing_policy=mixing_policy, min_valid_interval_days=28)
        SeriesProduct.objects.create(series=series, product=prevenar, priority=0)
        SeriesProduct.objects.create(series=series, product=primovax, priority=1)
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
        SeriesRule.objects.create(
            series=series,
            slot_number=2,
            prior_valid_doses=1,
            min_age_days=90,
            recommended_age_days=90,
            overdue_age_days=120,
            min_interval_days=28,
            product=primovax,
        )
        return series, prevenar, primovax

    def evaluate(self, child):
        return VaccinationEngine(child).evaluate()

    def test_flexible_series_preserves_switching_without_transition_rules(self):
        series, prevenar, primovax = self.create_transition_series(mixing_policy=Series.MIXING_FLEXIBLE)
        child = self.make_child('Flexible Transition', age_days=120)
        self.give_dose(child, prevenar.vaccine, days_ago=30)

        result = self.evaluate(child)

        self.assertIn('Primovax', self.due_names(result))

    def test_strict_series_blocks_switching_without_transition_rules(self):
        series, prevenar, primovax = self.create_transition_series(mixing_policy=Series.MIXING_STRICT)
        child = self.make_child('Strict Transition', age_days=120)
        self.give_dose(child, prevenar.vaccine, days_ago=30)

        result = self.evaluate(child)

        self.assertNotIn('Primovax', self.due_names(result))
        self.assertNotIn('Primovax', [item['vaccine'].name for item in result['due_but_unavailable']])
        self.assertNotIn('Primovax', self.upcoming_names(result))

    def test_transition_rule_allows_switching_in_strict_series(self):
        series, prevenar, primovax = self.create_transition_series(mixing_policy=Series.MIXING_STRICT)
        SeriesTransitionRule.objects.create(
            series=series,
            from_product=prevenar,
            to_product=primovax,
            start_slot_number=2,
        )
        child = self.make_child('Strict Transition Allowed', age_days=120)
        self.give_dose(child, prevenar.vaccine, days_ago=30)

        result = self.evaluate(child)

        self.assertIn('Primovax', self.due_names(result))

    def test_unavailable_only_transition_waits_until_source_product_is_unavailable(self):
        series, prevenar, primovax = self.create_transition_series(mixing_policy=Series.MIXING_STRICT)
        SeriesTransitionRule.objects.create(
            series=series,
            from_product=prevenar,
            to_product=primovax,
            start_slot_number=2,
            allow_if_unavailable=True,
        )
        child = self.make_child('Unavailable Transition', age_days=120)
        self.give_dose(child, prevenar.vaccine, days_ago=30)

        result = self.evaluate(child)
        self.assertNotIn('Primovax', self.due_names(result))

        prevenar.available = False
        prevenar.save(update_fields=['available'])

        result = self.evaluate(child)
        self.assertIn('Primovax', self.due_names(result))
