from vaccines.engine import VaccinationEngine
from .base import BaseVaccinationTestCase


class TestSeriesBackedDTP(BaseVaccinationTestCase):
    include_dtp_legacy_group = False

    def test_series_recommends_penta_without_legacy_group(self):
        child = self.make_child("Series Baby", age_days=90)
        result = self.evaluate(child)

        self.assertIn('Penta', self.due_names(result))

    def test_series_recommends_dtc_booster_without_legacy_group(self):
        child = self.make_child("Series Booster", age_days=19 * 30)
        self.give_dose(child, self.penta, days_ago=17 * 30)
        self.give_dose(child, self.penta, days_ago=16 * 30)
        self.give_dose(child, self.penta, days_ago=15 * 30)
        result = self.evaluate(child)

        self.assertIn('DTC', self.due_names(result))

    def test_series_recommends_td_for_older_child_without_legacy_group(self):
        child = self.make_child("Series Td", age_days=8 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365 - 30)
        self.give_dose(child, self.penta, days_ago=7 * 365 - 60)
        result = self.evaluate(child)

        self.assertIn('Td', self.due_names(result))


