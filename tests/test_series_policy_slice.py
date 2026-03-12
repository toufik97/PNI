from vaccines.engine import VaccinationEngine
from vaccines.models import ScheduleRule
from .base import BaseVaccinationTestCase


class TestSeriesBackedDTP(BaseVaccinationTestCase):
    def test_series_recommends_penta_without_legacy_group(self):
        self.dtp_group.delete()

        child = self.make_child("Series Baby", age_days=90)
        result = self.evaluate(child)

        self.assertIn('Penta', self.due_names(result))

    def test_series_recommends_dtc_booster_without_legacy_group(self):
        self.dtp_group.delete()

        child = self.make_child("Series Booster", age_days=19 * 30)
        self.give_dose(child, self.penta, days_ago=17 * 30)
        self.give_dose(child, self.penta, days_ago=16 * 30)
        self.give_dose(child, self.penta, days_ago=15 * 30)
        result = self.evaluate(child)

        self.assertIn('DTC', self.due_names(result))

    def test_series_recommends_td_for_older_child_without_legacy_group(self):
        self.dtp_group.delete()

        child = self.make_child("Series Td", age_days=8 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365 - 30)
        self.give_dose(child, self.penta, days_ago=7 * 365 - 60)
        result = self.evaluate(child)

        self.assertIn('Td', self.due_names(result))

    def test_series_owned_group_is_not_double_evaluated_when_bridge_is_removed(self):
        self.dtp_series.legacy_group = None
        self.dtp_series.save(update_fields=['legacy_group'])

        child = self.make_child("Series Owned Group", age_days=90)
        result = self.evaluate(child)

        penta_due_items = [item for item in result['due_today'] if item['vaccine'].name == 'Penta']
        self.assertEqual(len(penta_due_items), 1)
        self.assertEqual(penta_due_items[0]['decision_source'], VaccinationEngine.SOURCE_SERIES_RULE)

    def test_series_recommendations_do_not_depend_on_dtp_schedule_rules(self):
        self.dtp_group.delete()
        ScheduleRule.objects.filter(vaccine__name__in=['Penta', 'DTC', 'Td']).delete()

        child = self.make_child("Series Without Legacy Schedules", age_days=90)
        result = self.evaluate(child)

        self.assertIn('Penta', self.due_names(result))
