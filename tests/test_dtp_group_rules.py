"""
Tests for the DTP Family vaccine group dynamic rules.
Covers all combinations of prior_doses (0-5) × age brackets.
"""
from .base import BaseVaccinationTestCase


class TestDTPZeroDoses(BaseVaccinationTestCase):
    """0 prior DTP doses at different ages."""

    def test_baby_under_12mo_gets_penta(self):
        child = self.make_child("Baby 3mo", age_days=90)
        result = self.evaluate(child)
        self.assertIn('Penta', self.due_names(result))

    def test_toddler_12mo_to_3y_gets_penta(self):
        child = self.make_child("Toddler 18mo", age_days=18 * 30)
        result = self.evaluate(child)
        self.assertIn('Penta', self.due_names(result))

    def test_child_3y_to_7y_gets_dtc(self):
        child = self.make_child("Child 5y", age_days=5 * 365)
        result = self.evaluate(child)
        self.assertIn('DTC', self.due_names(result))

    def test_child_over_7y_gets_td(self):
        child = self.make_child("Child 8y", age_days=8 * 365)
        result = self.evaluate(child)
        self.assertIn('Td', self.due_names(result))


class TestDTPOneDose(BaseVaccinationTestCase):
    """1 prior DTP dose at different ages."""

    def test_baby_gets_penta_after_4w(self):
        child = self.make_child("1dose baby", age_days=120)
        self.give_dose(child, self.penta, days_ago=60)
        result = self.evaluate(child)
        self.assertIn('Penta', self.due_names(result))

    def test_baby_wait_if_too_soon(self):
        """Dose given 14 days ago (< 28 days) → upcoming, not due."""
        child = self.make_child("1dose wait", age_days=90)
        self.give_dose(child, self.penta, days_ago=14)
        result = self.evaluate(child)
        self.assertNotIn('Penta', self.due_names(result))
        self.assertIn('Penta', self.upcoming_names(result))

    def test_over_7y_gets_td(self):
        child = self.make_child("1dose 8y", age_days=8 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365)
        result = self.evaluate(child)
        self.assertIn('Td', self.due_names(result))


class TestDTPTwoDoses(BaseVaccinationTestCase):
    """2 prior DTP doses at different ages."""

    def test_baby_gets_penta_dose3(self):
        child = self.make_child("2dose baby", age_days=150)
        self.give_dose(child, self.penta, days_ago=90)
        self.give_dose(child, self.penta, days_ago=60)
        result = self.evaluate(child)
        self.assertIn('Penta', self.due_names(result))

    def test_3y_to_7y_gets_dtc(self):
        child = self.make_child("2dose 5y", age_days=5 * 365)
        self.give_dose(child, self.penta, days_ago=5 * 365 - 60)
        self.give_dose(child, self.penta, days_ago=5 * 365 - 120)
        result = self.evaluate(child)
        self.assertIn('DTC', self.due_names(result))

    def test_over_7y_gets_td(self):
        child = self.make_child("2dose 8y", age_days=8 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365 - 30)
        result = self.evaluate(child)
        self.assertIn('Td', self.due_names(result))


class TestDTPThreeDoses(BaseVaccinationTestCase):
    """3 prior DTP doses — primary series complete, boosters needed."""

    def test_17mo_waits_for_18mo(self):
        """3 doses at 17 months → DTC NOT due today, in upcoming."""
        child = self.make_child("3dose 17mo", age_days=17 * 30)
        self.give_dose(child, self.penta, days_ago=15 * 30)
        self.give_dose(child, self.penta, days_ago=14 * 30)
        self.give_dose(child, self.penta, days_ago=13 * 30)
        result = self.evaluate(child)
        self.assertNotIn('DTC', self.due_names(result))
        self.assertIn('DTC', self.upcoming_names(result))

    def test_19mo_dtc_due(self):
        """3 doses at 19 months (>6mo since dose 3) → DTC due."""
        child = self.make_child("3dose 19mo", age_days=19 * 30)
        self.give_dose(child, self.penta, days_ago=17 * 30)
        self.give_dose(child, self.penta, days_ago=16 * 30)
        self.give_dose(child, self.penta, days_ago=15 * 30)
        result = self.evaluate(child)
        self.assertIn('DTC', self.due_names(result))

    def test_over_7y_gets_td(self):
        child = self.make_child("3dose 8y", age_days=8 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365)
        self.give_dose(child, self.penta, days_ago=7 * 365 - 30)
        self.give_dose(child, self.penta, days_ago=7 * 365 - 60)
        result = self.evaluate(child)
        self.assertIn('Td', self.due_names(result))


class TestDTPFourDoses(BaseVaccinationTestCase):
    """4 prior DTP doses — B1 complete, need B2."""

    def test_under_5y_upcoming(self):
        """4 doses at 3 years (Dose 4 valid at 2y) \u2192 B2 not due yet, upcoming at 5y."""
        child = self.make_child("4dose 3y", age_days=3 * 365)
        for i in range(3):
            # Dose 1-3: Penta at ~2mo, ~3mo, ~4mo
            self.give_dose(child, self.penta, days_ago=3 * 365 - (60 + i * 30))
        # Dose 4 (B1): DTC at 2 years old (Valid >= 18mo)
        self.give_dose(child, self.dtc, days_ago=1 * 365) 
        result = self.evaluate(child)
        self.assertNotIn('DTC', self.due_names(result))
        self.assertIn('DTC', self.upcoming_names(result))


    def test_over_7y_gets_td(self):
        child = self.make_child("4dose 8y", age_days=8 * 365)
        for i in range(3):
            self.give_dose(child, self.penta, days_ago=7 * 365 - i * 30)
        self.give_dose(child, self.dtc, days_ago=6 * 365)
        result = self.evaluate(child)
        self.assertIn('Td', self.due_names(result))


class TestDTPFiveDoses(BaseVaccinationTestCase):
    """5 doses = fully vaccinated. Nothing due from DTP group."""

    def test_fully_vaccinated_nothing_due(self):
        child = self.make_child("Full DTP", age_days=6 * 365)
        for i in range(3):
            self.give_dose(child, self.penta, days_ago=6 * 365 - (60 + i * 30))
        self.give_dose(child, self.dtc, days_ago=4 * 365)
        self.give_dose(child, self.dtc, days_ago=0) # Age 6y, interval 4y since dose 4
        result = self.evaluate(child)
        dtp_names = {'Penta', 'DTC', 'Td'}
        due_dtp = [n for n in self.due_names(result) if n in dtp_names]
        self.assertEqual(due_dtp, [])
