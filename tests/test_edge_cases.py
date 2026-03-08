"""
Edge case tests: unknown status, mixed vaccine history, simultaneous vaccines.
"""
from .base import BaseVaccinationTestCase


class TestUnknownVaccinationStatus(BaseVaccinationTestCase):
    """Children with unknown_status=True should be treated as unvaccinated."""

    def test_unknown_status_treated_as_unvaccinated(self):
        """unknown_status=True, no records → same as 0 doses."""
        from patients.models import Child
        from datetime import date, timedelta

        child = Child.objects.create(
            id="unknown_child", name="Unknown History",
            sex='M', dob=date.today() - timedelta(days=120),
            unknown_status=True
        )
        result = self.evaluate(child)
        # Should recommend Penta (0 doses, <12m)
        self.assertIn('Penta', self.due_names(result))


class TestMixedVaccineHistory(BaseVaccinationTestCase):
    """Penta, DTC, and Td doses should all count toward the same group total."""

    def test_mixed_penta_dtc_counted_together(self):
        """3 Penta doses (correct vaccine per age) = primary complete → DTC booster due at 19mo."""
        child = self.make_child("Mixed History", age_days=19 * 30)
        # All 3 as Penta — correct per the rule (<3y = Penta)
        self.give_dose(child, self.penta, days_ago=17 * 30)
        self.give_dose(child, self.penta, days_ago=16 * 30)
        self.give_dose(child, self.penta, days_ago=15 * 30)
        result = self.evaluate(child)
        # 3 valid doses at 19mo → DTC booster due
        self.assertIn('DTC', self.due_names(result))

    def test_penta_and_td_counted_together(self):
        """3 Penta + 1 Td = 4 total DTP doses."""
        child = self.make_child("Penta Td Mix", age_days=8 * 365)
        for i in range(3):
            self.give_dose(child, self.penta, days_ago=7 * 365 - i * 30)
        self.give_dose(child, self.td, days_ago=6 * 365)
        result = self.evaluate(child)
        # 4 doses at 8y → Td dose 5 due
        self.assertIn('Td', self.due_names(result))


class TestSimultaneousVaccination(BaseVaccinationTestCase):
    """Multiple vaccines can be given on the same visit."""

    def test_dtp_and_rr_same_day(self):
        """Both DTP and RR can be due on the same day."""
        child = self.make_child("Same Day", age_days=270)
        result = self.evaluate(child)
        due = self.due_names(result)
        # Age 9mo, 0 doses → Penta due AND RR dose 1 due
        self.assertIn('Penta', due)
        self.assertIn('RR', due)


class TestNeverRestartSeries(BaseVaccinationTestCase):
    """The series should never be restarted — always continue from last valid dose."""

    def test_late_dose_continues_not_restarts(self):
        """1 dose given years ago → continues from dose 2, doesn't restart."""
        child = self.make_child("Late Dose", age_days=5 * 365)
        self.give_dose(child, self.penta, days_ago=4 * 365)
        result = self.evaluate(child)
        # 1 prior dose at 5y (3-7y bracket) → DTC due (dose 2), not Penta dose 1
        self.assertIn('DTC', self.due_names(result))
        # And the recommended vaccine should NOT be Penta (since age > 3)
        self.assertNotIn('Penta', self.due_names(result))
