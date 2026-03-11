from datetime import date

from vaccines.engine import VaccinationEngine
from vaccines.models import DependencyRule, Product, Series, SeriesProduct, SeriesRule, Vaccine
from .base import BaseVaccinationTestCase


class TestEngineProvenance(BaseVaccinationTestCase):
    def test_series_due_item_includes_provenance(self):
        child = self.make_child('Series Due', age_days=60)

        result = self.evaluate(child)

        penta_item = next(item for item in result['due_today'] if item['vaccine'].name == 'Penta')
        self.assertEqual(result['policy_version'], 'series-policy-v1')
        self.assertEqual(penta_item['decision_source'], VaccinationEngine.SOURCE_SERIES_RULE)
        self.assertEqual(penta_item['decision_type'], VaccinationEngine.DECISION_DUE)
        self.assertEqual(penta_item['series_code'], self.dtp_series.code)
        self.assertEqual(penta_item['product_code'], self.product_map['Penta'].code)
        self.assertTrue(penta_item['rule_key'].startswith(f'series:{self.dtp_series.code}:slot:1'))
        self.assertEqual(penta_item['slot_number'], 1)
        self.assertIn('due today', penta_item['message'])

    def test_upcoming_details_keep_schedule_rule_provenance(self):
        child = self.make_child('RR Upcoming', age_days=200)

        result = self.evaluate(child)

        rr_detail = next(item for item in result['upcoming_details'] if item['vaccine'].name == 'RR')
        self.assertEqual(rr_detail['decision_source'], VaccinationEngine.SOURCE_SCHEDULE_RULE)
        self.assertEqual(rr_detail['decision_type'], VaccinationEngine.DECISION_UPCOMING)
        self.assertEqual(rr_detail['product_code'], self.product_map['RR'].code)
        self.assertTrue(rr_detail['rule_key'].startswith(f'schedule:{self.rr.id}:'))
        self.assertEqual((rr_detail['vaccine'], rr_detail['target_date'], rr_detail['dose_number']), next(item for item in result['upcoming'] if item[0].name == 'RR'))

    def test_invalid_history_records_reason_and_rule_source(self):
        child = self.make_child('Early Penta', age_days=7)
        self.give_dose(child, self.penta, days_ago=0)

        result = self.evaluate(child)

        invalid_item = next(item for item in result['invalid_history'] if item['vaccine'].name == 'Penta')
        self.assertEqual(invalid_item['decision_source'], VaccinationEngine.SOURCE_SERIES_RULE)
        self.assertEqual(invalid_item['reason_code'], 'too_early')
        self.assertTrue(invalid_item['rule_key'].startswith(f'series:{self.dtp_series.code}:slot:1'))
        self.assertIn('Too early', invalid_item['message'])

    def test_blocked_items_include_dependency_provenance(self):
        prevenar_vaccine = Vaccine.objects.create(name='Prevenar13', live=False)
        prevenar = Product.objects.create(vaccine=prevenar_vaccine, manufacturer='Pfizer', available=True)
        pneumo = Series.objects.create(name='Pneumo', mixing_policy=Series.MIXING_FLEXIBLE, min_valid_interval_days=28)
        SeriesProduct.objects.create(series=pneumo, product=prevenar, priority=0)
        SeriesRule.objects.create(
            series=pneumo,
            slot_number=1,
            prior_valid_doses=0,
            min_age_days=60,
            recommended_age_days=60,
            overdue_age_days=90,
            min_interval_days=0,
            product=prevenar,
        )
        DependencyRule.objects.create(
            dependent_series=pneumo,
            dependent_slot_number=1,
            anchor_series=self.dtp_series,
            anchor_slot_number=1,
            min_offset_days=15,
            block_if_anchor_missing=True,
        )
        child = self.make_child('Blocked Pneumo', age_days=80)

        result = self.evaluate(child)

        blocked_item = next(item for item in result['blocked'] if item['vaccine'].name == 'Prevenar13')
        self.assertEqual(blocked_item['decision_source'], VaccinationEngine.SOURCE_SERIES_RULE)
        self.assertEqual(blocked_item['decision_type'], VaccinationEngine.DECISION_BLOCKED)
        self.assertEqual(blocked_item['series_code'], pneumo.code)
        self.assertTrue(blocked_item['rule_key'].startswith(f'series:{pneumo.code}:slot:1'))
        self.assertTrue(blocked_item['blocking_constraints'])
        self.assertTrue(blocked_item['blocking_constraints'][0]['rule_key'].startswith(f'dependency:{pneumo.code}:1:'))
        self.assertTrue(blocked_item['reasons'])
