"""
Tests that strict validation flags invalid doses correctly.
Ensures validation doesn't contradict scheduling, and checks
all violation types: too_early, too_late, short_interval, wrong_vaccine.
"""
from patients.models import VaccinationRecord as VR
from .base import BaseVaccinationTestCase


class TestIntervalValidation(BaseVaccinationTestCase):
    """Doses given too close together must be flagged with REASON_INTERVAL."""

    def test_group_dose_under_28_days_flagged(self):
        """Two DTP doses < 28 days apart: second is invalid with correct reason code."""
        child = self.make_child("Short Interval", age_days=130)
        self.give_dose(child, self.penta, days_ago=60)
        d2 = self.give_dose(child, self.penta, days_ago=40)  # 20 days after first

        result = self.evaluate(child)

        d2.refresh_from_db()
        self.assertTrue(d2.invalid_flag)
        self.assertEqual(d2.invalid_reason, VR.REASON_INTERVAL)
        self.assertIn("28 days", d2.notes)
        # Engine still recommends Penta (only 1 valid dose)
        self.assertIn('Penta', self.due_names(result))

    def test_valid_interval_not_flagged(self):
        """Two DTP doses >= 28 days apart: neither flagged."""
        child = self.make_child("Good Interval", age_days=120)
        self.give_dose(child, self.penta, days_ago=60)
        self.give_dose(child, self.penta, days_ago=30)

        result = self.evaluate(child)

        self.assertEqual(child.vaccination_records.filter(invalid_flag=True).count(), 0)
        self.assertIn('Penta', self.due_names(result))

    def test_multiple_invalid_doses_counted_correctly(self):
        """Multiple short-interval doses flagged; engine counts only valid ones."""
        child = self.make_child("Multi Invalid", age_days=150)
        self.give_dose(child, self.penta, days_ago=90)
        self.give_dose(child, self.penta, days_ago=80)   # 10 days — invalid
        self.give_dose(child, self.penta, days_ago=70)   # 10 days — invalid

        result = self.evaluate(child)

        self.assertEqual(child.vaccination_records.filter(invalid_flag=True).count(), 2)
        self.assertIn('Penta', self.due_names(result))


class TestMinEligibleAgeValidation(BaseVaccinationTestCase):
    """Doses given before absolute minimum age floors must be flagged REASON_TOO_EARLY."""

    def test_penta_at_one_week_flagged_too_early(self):
        """Penta given at 7 days old (Standard floor is 53 days): flagged too_early."""
        child = self.make_child("Tiny Baby", age_days=7)
        d1 = self.give_dose(child, self.penta, days_ago=0)

        self.evaluate(child)

        d1.refresh_from_db()
        self.assertTrue(d1.invalid_flag)
        self.assertEqual(d1.invalid_reason, VR.REASON_TOO_EARLY)
        # Note should mention the requirement from Layer 1 (Standard Rule)
        # 53 days / 30.44 = 1.74 months
        self.assertIn("1.7 months", d1.notes)

    def test_penta_at_53_days_not_flagged(self):
        """Penta given at 53 days old (exactly the standard floor): valid."""
        child = self.make_child("On Time Baby", age_days=53)
        d1 = self.give_dose(child, self.penta, days_ago=0)

        self.evaluate(child)

        d1.refresh_from_db()
        self.assertFalse(d1.invalid_flag)



class TestMaxAgeValidation(BaseVaccinationTestCase):

    """Doses given after max_age must be strictly flagged with REASON_TOO_LATE."""

    def test_rr_dose_max_age_enforced_via_series_rule(self):
        """Standard vaccine given after max_age is flagged too_late."""
        from vaccines.models import SeriesRule
        rr_rule = SeriesRule.objects.get(product__vaccine__name='RR', slot_number=1)
        rr_rule.max_age_days = 365  # Max age 12 months for dose 1
        rr_rule.save()

        child = self.make_child("Too Old RR", age_days=14 * 30)
        d1 = self.give_dose(child, self.rr, days_ago=0)

        self.evaluate(child)

        d1.refresh_from_db()
        self.assertTrue(d1.invalid_flag)
        self.assertEqual(d1.invalid_reason, VR.REASON_TOO_LATE)
        self.assertIn("Too late", d1.notes)


class TestWrongVaccineValidation(BaseVaccinationTestCase):
    """Doses of the wrong vaccine type for the age group must be flagged REASON_WRONG_VACCINE."""

    def test_penta_given_to_over_7y_flagged_wrong_vaccine(self):
        """Penta given to 8-year-old (who should get Td) is flagged as wrong vaccine."""
        child = self.make_child("Wrong Vaccine 8y", age_days=8 * 365)
        d1 = self.give_dose(child, self.penta, days_ago=0)

        self.evaluate(child)

        d1.refresh_from_db()
        self.assertTrue(d1.invalid_flag)
        self.assertEqual(d1.invalid_reason, VR.REASON_WRONG_VACCINE)
        self.assertIn("Td", d1.notes)

    def test_correct_vaccine_for_age_not_flagged(self):
        """Penta given to 3-month-old (correct) is not flagged."""
        child = self.make_child("Correct Vaccine", age_days=90)
        d1 = self.give_dose(child, self.penta, days_ago=0)

        self.evaluate(child)

        d1.refresh_from_db()
        self.assertFalse(d1.invalid_flag)

    def test_dtc_given_when_td_expected_flagged(self):
        """DTC given at 8 years old (should be Td) is flagged."""
        child = self.make_child("DTC at 8y", age_days=8 * 365)
        d1 = self.give_dose(child, self.dtc, days_ago=0)

        self.evaluate(child)

        d1.refresh_from_db()
        self.assertTrue(d1.invalid_flag)
        self.assertEqual(d1.invalid_reason, VR.REASON_WRONG_VACCINE)


class TestInvalidDoseDoesNotCountForScheduling(BaseVaccinationTestCase):
    """After a dose is invalidated, the schedule must treat it as if it never happened."""

    def test_invalid_dose_not_counted(self):
        """1 valid + 1 invalid = engine sees 1 prior dose, recommends dose 2."""
        child = self.make_child("Invalid Not Counted", age_days=150)
        self.give_dose(child, self.penta, days_ago=60)
        d2 = self.give_dose(child, self.penta, days_ago=45)  # < 28 days

        result = self.evaluate(child)

        d2.refresh_from_db()
        self.assertTrue(d2.invalid_flag)
        self.assertEqual(d2.invalid_reason, VR.REASON_INTERVAL)
        self.assertIn('Penta', self.due_names(result))

    def test_three_valid_doses_no_premature_booster(self):
        """3 valid primary doses at 17mo → DTC not due today, only upcoming."""
        child = self.make_child("No Premature B1", age_days=17 * 30)
        self.give_dose(child, self.penta, days_ago=15 * 30)
        self.give_dose(child, self.penta, days_ago=14 * 30)
        self.give_dose(child, self.penta, days_ago=13 * 30)

        result = self.evaluate(child)

        self.assertNotIn('DTC', self.due_names(result))
        self.assertIn('DTC', self.upcoming_names(result))


class TestMixedVaccineValidation(BaseVaccinationTestCase):
    """Mixing Penta and DTC: intervals validated across the group."""

    def test_penta_then_dtc_under_28_days_invalid(self):
        child = self.make_child("Mixed Invalid", age_days=2 * 365)
        self.give_dose(child, self.penta, days_ago=60)
        d2 = self.give_dose(child, self.dtc, days_ago=45)  # 15 days after Penta

        self.evaluate(child)

        d2.refresh_from_db()
        self.assertTrue(d2.invalid_flag)
        self.assertEqual(d2.invalid_reason, VR.REASON_INTERVAL)

    def test_penta_then_dtc_wrong_vaccine_at_2y(self):
        """DTC given at 2y with 1 prior dose: flagged as wrong_vaccine (should be Penta at 18m-3y)."""
        child = self.make_child("DTC at 2y", age_days=2 * 365)
        self.give_dose(child, self.penta, days_ago=90)
        d2 = self.give_dose(child, self.dtc, days_ago=60)  # 30 days after Penta

        self.evaluate(child)

        d2.refresh_from_db()
        self.assertTrue(d2.invalid_flag)
        self.assertEqual(d2.invalid_reason, VR.REASON_WRONG_VACCINE)
        self.assertIn("Penta", d2.notes)  # Notes should mention the correct vaccine

    def test_penta_then_penta_valid_at_2y(self):
        """Penta→Penta at 2y (18m-3y bracket): both valid, no flags."""
        child = self.make_child("Penta Penta 2y", age_days=2 * 365)
        self.give_dose(child, self.penta, days_ago=90)
        self.give_dose(child, self.penta, days_ago=60)

        self.evaluate(child)

        self.assertEqual(child.vaccination_records.filter(invalid_flag=True).count(), 0)

