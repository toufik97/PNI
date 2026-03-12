from datetime import date, timedelta

from vaccines.availability import AvailabilityResolver
from vaccines.dependencies import DependencyEvaluator
from vaccines.engine import VaccinationEngine
from vaccines.global_constraints import LiveVaccineConstraintService
from vaccines.history_normalizer import HistoryNormalizer
from vaccines.models import DependencyRule, Product, Series, SeriesProduct, SeriesRule, Vaccine
from vaccines.policy_loader import PolicyLoader
from vaccines.recommender import SeriesRecommender
from vaccines.series_validator import SeriesHistoryValidator
from .base import BaseVaccinationTestCase


class TestModuleBoundaries(BaseVaccinationTestCase):
    def test_history_normalizer_sorts_and_groups_records(self):
        child = self.make_child('Normalizer Child', age_days=200)
        rr_record = self.give_dose(child, self.rr, days_ago=5)
        penta_record = self.give_dose(child, self.penta, days_ago=30)

        history = HistoryNormalizer(child, [rr_record, penta_record])

        self.assertEqual([record.vaccine.name for record in history.records], ['Penta', 'RR'])
        self.assertEqual([record.vaccine.name for record in history.history_by_vaccine[self.penta.id]], ['Penta'])
        self.assertEqual(history.age_at_dose(penta_record), 170)

    def test_series_validator_handles_series_local_validation(self):
        child = self.make_child('Series Validator Child', age_days=60)
        dtc_record = self.give_dose(child, self.dtc, days_ago=0)
        engine = VaccinationEngine(child)
        validator = SeriesHistoryValidator(engine, engine._group_history())

        valid_records = validator.validate(self.dtp_series)

        self.assertEqual(valid_records, [])
        dtc_record.refresh_from_db()
        self.assertTrue(dtc_record.invalid_flag)
        self.assertEqual(dtc_record.invalid_reason, dtc_record.REASON_WRONG_VACCINE)
        self.assertEqual(len(engine.invalid_history), 1)

    def test_policy_loader_returns_active_policy_objects(self):
        loader = PolicyLoader()

        self.assertIn(self.dtp_series, loader.get_active_series())
        self.assertIn(self.dtp_group, loader.get_vaccine_groups())
        self.assertEqual(loader.get_active_policy_version(), self.dtp_series.policy_version)

    def test_availability_resolver_uses_product_availability_and_priority(self):
        resolver = AvailabilityResolver()
        penta_product = self.product_map['Penta']
        dtc_product = self.product_map['DTC']
        dtc_product.available = False
        dtc_product.save(update_fields=['available'])

        self.assertTrue(resolver.is_product_available(penta_product))
        self.assertFalse(resolver.is_product_available(dtc_product))
        self.assertEqual(resolver.series_product_priority(self.dtp_series, penta_product.id), 0)

    def test_dependency_evaluator_blocks_when_anchor_history_missing(self):
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

        evaluator = DependencyEvaluator(
            series_history_cache={},
            dependency_rule_key_builder=lambda dependency, slot_number: f'dependency:{dependency.id}:{slot_number}',
        )
        target_date = date.today()

        adjusted_target, blocking = evaluator.apply(pneumo, 1, target_date)

        self.assertEqual(adjusted_target, target_date)
        self.assertEqual(blocking[0]['reason_code'], 'dependency_anchor_missing')

    def test_live_vaccine_constraint_service_defers_incompatible_due_item(self):
        child = self.make_child('Live Constraint Child', age_days=300)
        self.give_dose(child, self.bcg, days_ago=10)
        due_item = {'vaccine': self.rr}

        service = LiveVaccineConstraintService(
            global_live_rule_key='global:live-live-28d',
            product_lookup=lambda vaccine: None,
            flag_invalid=lambda *args, **kwargs: None,
            build_live_deferral_item=lambda item, safe_date, recent_live_doses: {
                'vaccine': item['vaccine'],
                'target_date': safe_date,
                'recent_count': len(recent_live_doses),
            },
        )

        remaining_due, deferred = service.defer_recommendations(
            list(child.vaccination_records.all()),
            [due_item],
            date.today(),
        )

        self.assertEqual(remaining_due, [])
        self.assertEqual(deferred[0]['vaccine'], self.rr)
        self.assertEqual(deferred[0]['target_date'], date.today() + timedelta(days=18))
        self.assertEqual(deferred[0]['recent_count'], 1)
    def test_series_recommender_returns_due_item_for_due_series(self):
        child = self.make_child('Recommender Child', age_days=90)
        engine = VaccinationEngine(child)
        engine.series_history_cache[self.dtp_series.id] = []

        recommender = SeriesRecommender(
            child=engine.child,
            evaluation_date=engine.evaluation_date,
            age_days=engine.age_days,
            availability=engine.availability,
            dependencies=engine.dependencies,
            series_history_cache=engine.series_history_cache,
            state_to_due_item=engine._state_to_due_item,
            state_to_missing_item=engine._state_to_missing_item,
            state_to_upcoming_item=engine._state_to_upcoming_item,
            state_to_blocked_item=engine._state_to_blocked_item,
        )

        result = recommender.recommend(self.dtp_series)

        self.assertEqual([item['vaccine'].name for item in result['due_today']], ['Penta'])
        self.assertEqual(result['due_but_unavailable'], [])

