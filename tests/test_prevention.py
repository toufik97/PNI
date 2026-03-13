from django.core.exceptions import ValidationError
from django.test import TestCase

from vaccines.models import DependencyRule, Product, Series, SeriesProduct, SeriesRule, SeriesTransitionRule, Vaccine


class TestModelValidationPrevention(TestCase):
    def setUp(self):
        self.vax = Vaccine.objects.create(name="Test Vax")
        self.group = VaccineGroup.objects.create(name="Test Group")
        self.group.vaccines.add(self.vax)

    def test_schedule_rule_min_greater_than_rec_fails(self):
        rule = ScheduleRule(
            vaccine=self.vax,
            dose_number=1,
            min_age_days=100,
            recommended_age_days=50,
        )
        with self.assertRaises(ValidationError) as cm:
            rule.full_clean()
        self.assertIn("cannot be greater than recommended age", str(cm.exception))

    def test_group_rule_overlap_prevention(self):
        GroupRule.objects.create(
            group=self.group,
            prior_doses=0,
            min_age_days=0,
            max_age_days=100,
            vaccine_to_give=self.vax,
            min_interval_days=0,
        )

        overlapping_rule = GroupRule(
            group=self.group,
            prior_doses=0,
            min_age_days=50,
            max_age_days=150,
            vaccine_to_give=self.vax,
            min_interval_days=0,
        )

        with self.assertRaises(ValidationError) as cm:
            overlapping_rule.full_clean()
        self.assertIn("overlaps with an existing rule", str(cm.exception))

    def test_group_rule_min_greater_than_max_fails(self):
        rule = GroupRule(
            group=self.group,
            prior_doses=0,
            min_age_days=200,
            max_age_days=100,
            vaccine_to_give=self.vax,
            min_interval_days=0,
        )
        with self.assertRaises(ValidationError) as cm:
            rule.full_clean()
        self.assertIn("is greater than Max age", str(cm.exception))

    def test_dependency_rule_requires_existing_slots(self):
        vaccine_a = Vaccine.objects.create(name="Series Slot A")
        vaccine_b = Vaccine.objects.create(name="Series Slot B")
        product_a = Product.objects.create(vaccine=vaccine_a)
        product_b = Product.objects.create(vaccine=vaccine_b)
        series_a = Series.objects.create(name="Series Slot A")
        series_b = Series.objects.create(name="Series Slot B")
        SeriesProduct.objects.create(series=series_a, product=product_a, priority=0)
        SeriesProduct.objects.create(series=series_b, product=product_b, priority=0)
        SeriesRule.objects.create(
            series=series_a,
            slot_number=1,
            prior_valid_doses=0,
            product=product_a,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )
        SeriesRule.objects.create(
            series=series_b,
            slot_number=1,
            prior_valid_doses=0,
            product=product_b,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )

        invalid_rule = DependencyRule(
            dependent_series=series_a,
            dependent_slot_number=2,
            anchor_series=series_b,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        with self.assertRaises(ValidationError) as cm:
            invalid_rule.full_clean()
        self.assertIn("dependent slots that exist", str(cm.exception))

    def test_dependency_rule_requires_existing_anchor_slots(self):
        vaccine_a = Vaccine.objects.create(name="Anchor Slot A")
        vaccine_b = Vaccine.objects.create(name="Anchor Slot B")
        product_a = Product.objects.create(vaccine=vaccine_a)
        product_b = Product.objects.create(vaccine=vaccine_b)
        series_a = Series.objects.create(name="Anchor Slot A")
        series_b = Series.objects.create(name="Anchor Slot B")
        SeriesProduct.objects.create(series=series_a, product=product_a, priority=0)
        SeriesProduct.objects.create(series=series_b, product=product_b, priority=0)
        SeriesRule.objects.create(
            series=series_a,
            slot_number=1,
            prior_valid_doses=0,
            product=product_a,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )
        SeriesRule.objects.create(
            series=series_b,
            slot_number=1,
            prior_valid_doses=0,
            product=product_b,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )

        invalid_rule = DependencyRule(
            dependent_series=series_a,
            dependent_slot_number=1,
            anchor_series=series_b,
            anchor_slot_number=2,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        with self.assertRaises(ValidationError) as cm:
            invalid_rule.full_clean()
        self.assertIn("anchor slots that exist", str(cm.exception))

    def test_transition_rule_requires_destination_slot_coverage(self):
        vaccine_a = Vaccine.objects.create(name="Transition Slot A")
        vaccine_b = Vaccine.objects.create(name="Transition Slot B")
        product_a = Product.objects.create(vaccine=vaccine_a)
        product_b = Product.objects.create(vaccine=vaccine_b)
        series = Series.objects.create(name="Transition Slot Coverage")
        SeriesProduct.objects.create(series=series, product=product_a, priority=0)
        SeriesProduct.objects.create(series=series, product=product_b, priority=1)
        SeriesRule.objects.create(
            series=series,
            slot_number=1,
            prior_valid_doses=0,
            product=product_a,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )

        invalid_transition = SeriesTransitionRule(
            series=series,
            from_product=product_a,
            to_product=product_b,
            start_slot_number=2,
            end_slot_number=3,
            active=True,
        )

        with self.assertRaises(ValidationError) as cm:
            invalid_transition.full_clean()
        self.assertIn("destination product", str(cm.exception))

    def test_dependency_rule_direct_cycle_prevention(self):
        vaccine_a = Vaccine.objects.create(name="Cycle Series A")
        vaccine_b = Vaccine.objects.create(name="Cycle Series B")
        product_a = Product.objects.create(vaccine=vaccine_a)
        product_b = Product.objects.create(vaccine=vaccine_b)
        series_a = Series.objects.create(name="Series A")
        series_b = Series.objects.create(name="Series B")
        SeriesProduct.objects.create(series=series_a, product=product_a, priority=0)
        SeriesProduct.objects.create(series=series_b, product=product_b, priority=0)
        SeriesRule.objects.create(
            series=series_a,
            slot_number=1,
            prior_valid_doses=0,
            product=product_a,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )
        SeriesRule.objects.create(
            series=series_b,
            slot_number=1,
            prior_valid_doses=0,
            product=product_b,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )
        DependencyRule.objects.create(
            dependent_series=series_a,
            dependent_slot_number=1,
            anchor_series=series_b,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        cyclical_rule = DependencyRule(
            dependent_series=series_b,
            dependent_slot_number=1,
            anchor_series=series_a,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        with self.assertRaises(ValidationError) as cm:
            cyclical_rule.full_clean()
        self.assertIn("direct blocking cycle", str(cm.exception))

    def test_dependency_rule_transitive_cycle_prevention(self):
        vaccine_a = Vaccine.objects.create(name="Transitive Series A")
        vaccine_b = Vaccine.objects.create(name="Transitive Series B")
        vaccine_c = Vaccine.objects.create(name="Transitive Series C")
        product_a = Product.objects.create(vaccine=vaccine_a)
        product_b = Product.objects.create(vaccine=vaccine_b)
        product_c = Product.objects.create(vaccine=vaccine_c)
        series_a = Series.objects.create(name="Transitive A")
        series_b = Series.objects.create(name="Transitive B")
        series_c = Series.objects.create(name="Transitive C")
        SeriesProduct.objects.create(series=series_a, product=product_a, priority=0)
        SeriesProduct.objects.create(series=series_b, product=product_b, priority=0)
        SeriesProduct.objects.create(series=series_c, product=product_c, priority=0)
        SeriesRule.objects.create(
            series=series_a,
            slot_number=1,
            prior_valid_doses=0,
            product=product_a,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )
        SeriesRule.objects.create(
            series=series_b,
            slot_number=1,
            prior_valid_doses=0,
            product=product_b,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )
        SeriesRule.objects.create(
            series=series_c,
            slot_number=1,
            prior_valid_doses=0,
            product=product_c,
            min_age_days=10,
            recommended_age_days=10,
            overdue_age_days=20,
            min_interval_days=0,
        )
        DependencyRule.objects.create(
            dependent_series=series_a,
            dependent_slot_number=1,
            anchor_series=series_b,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )
        DependencyRule.objects.create(
            dependent_series=series_b,
            dependent_slot_number=1,
            anchor_series=series_c,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        cyclical_rule = DependencyRule(
            dependent_series=series_c,
            dependent_slot_number=1,
            anchor_series=series_a,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        with self.assertRaises(ValidationError) as cm:
            cyclical_rule.full_clean()
        self.assertIn("blocking cycle across multiple series slots", str(cm.exception))
