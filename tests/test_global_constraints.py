from datetime import date, timedelta

from vaccines.engine import VaccinationEngine
from vaccines.models import GlobalConstraintRule, PolicyVersion
from .base import BaseVaccinationTestCase


class TestGlobalConstraintPolicy(BaseVaccinationTestCase):
    def test_custom_live_spacing_rule_shortens_live_deferral_window(self):
        GlobalConstraintRule.objects.create(
            name='Short Live Spacing',
            code='short-live-spacing',
            constraint_type=GlobalConstraintRule.CONSTRAINT_LIVE_LIVE_SPACING,
            min_spacing_days=14,
            policy_version=PolicyVersion.get_active(),
            active=True,
        )
        child = self.make_child('Custom Live Spacing', age_days=300)
        self.give_dose(child, self.bcg, days_ago=10)

        result = VaccinationEngine(child, evaluation_date=date.today()).evaluate()

        self.assertNotIn('RR', self.due_names(result))
        upcoming_item = next(item for item in result['upcoming'] if item[0].name == 'RR')
        self.assertEqual(upcoming_item[1], date.today() + timedelta(days=4))

    def test_default_live_spacing_remains_28_days_without_rule(self):
        child = self.make_child('Default Live Spacing', age_days=300)
        self.give_dose(child, self.bcg, days_ago=10)

        result = VaccinationEngine(child, evaluation_date=date.today()).evaluate()

        upcoming_item = next(item for item in result['upcoming'] if item[0].name == 'RR')
        self.assertEqual(upcoming_item[1], date.today() + timedelta(days=18))
