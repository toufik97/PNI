from django.core.exceptions import ValidationError
from django.test import TestCase

from vaccines.models import DependencyRule, GroupRule, ScheduleRule, Series, Vaccine, VaccineGroup


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

    def test_dependency_rule_direct_cycle_prevention(self):
        series_a = Series.objects.create(name="Series A")
        series_b = Series.objects.create(name="Series B")
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
