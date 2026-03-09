from django.test import TestCase
from django.core.exceptions import ValidationError
from vaccines.models import Vaccine, VaccineGroup, GroupRule, ScheduleRule

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
            recommended_age_days=50  # Invalid: min > rec
        )
        with self.assertRaises(ValidationError) as cm:
            rule.full_clean()
        self.assertIn("cannot be greater than recommended age", str(cm.exception))

    def test_group_rule_overlap_prevention(self):
        # 1. Create a valid rule: 0-100 days
        GroupRule.objects.create(
            group=self.group,
            prior_doses=0,
            min_age_days=0,
            max_age_days=100,
            vaccine_to_give=self.vax,
            min_interval_days=0
        )

        # 2. Try to create an overlapping rule: 50-150 days
        overlapping_rule = GroupRule(
            group=self.group,
            prior_doses=0,
            min_age_days=50,
            max_age_days=150,
            vaccine_to_give=self.vax,
            min_interval_days=0
        )
        
        with self.assertRaises(ValidationError) as cm:
            overlapping_rule.full_clean()
        self.assertIn("overlaps with an existing rule", str(cm.exception))

    def test_group_rule_min_greater_than_max_fails(self):
        rule = GroupRule(
            group=self.group,
            prior_doses=0,
            min_age_days=200,
            max_age_days=100,  # Invalid: min > max
            vaccine_to_give=self.vax,
            min_interval_days=0
        )
        with self.assertRaises(ValidationError) as cm:
            rule.full_clean()
        self.assertIn("is greater than Max age", str(cm.exception))
