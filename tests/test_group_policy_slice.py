from vaccines.models import GroupRule, Vaccine, VaccineGroup
from .base import BaseVaccinationTestCase


class TestGroupRulesWithoutScheduleFallback(BaseVaccinationTestCase):
    def test_group_recommendation_does_not_require_schedule_rules(self):
        custom_vaccine = Vaccine.objects.create(name='Custom Group Vax', live=False)
        custom_group = VaccineGroup.objects.create(name='Custom Group', min_valid_interval_days=21)
        custom_group.vaccines.add(custom_vaccine)
        GroupRule.objects.create(
            group=custom_group,
            prior_doses=0,
            min_age_days=45,
            max_age_days=120,
            vaccine_to_give=custom_vaccine,
            min_interval_days=0,
            dose_amount='0.25ml',
        )

        child = self.make_child('Custom Group Child', age_days=60)
        result = self.evaluate(child)

        matching_items = [item for item in result['due_today'] if item['vaccine'].name == 'Custom Group Vax']
        self.assertEqual(len(matching_items), 1)
        self.assertEqual(matching_items[0]['decision_source'], 'group_rule')
        self.assertEqual(matching_items[0]['dose_amount'], '0.25ml')
