"""
Tests for standard (non-grouped) vaccine scheduling — e.g. RR.
"""
from .base import BaseVaccinationTestCase


class TestRRRoutineSchedule(BaseVaccinationTestCase):
    """RR (Measles/Rubella-like) 2-dose routine schedule."""

    def test_too_young_for_dose1(self):
        """Child < 250 days → RR not due, appears in upcoming."""
        child = self.make_child("Young baby", age_days=200)
        result = self.evaluate(child)
        self.assertNotIn('RR', self.due_names(result))
        self.assertIn('RR', self.upcoming_names(result))

    def test_on_time_dose1(self):
        """Child >= 250 days, 0 doses → RR dose 1 due."""
        child = self.make_child("9mo child", age_days=270)
        result = self.evaluate(child)
        self.assertIn('RR', self.due_names(result))

    def test_dose1_given_dose2_upcoming(self):
        """Dose 1 given, too early for dose 2 → upcoming."""
        child = self.make_child("Dose1 done", age_days=300)
        self.give_dose(child, self.rr, days_ago=30)
        result = self.evaluate(child)
        self.assertNotIn('RR', self.due_names(result))
        self.assertIn('RR', self.upcoming_names(result))

    def test_dose1_given_dose2_due(self):
        """Dose 1 given, child old enough and interval met → dose 2 due."""
        child = self.make_child("Dose2 due", age_days=540)
        self.give_dose(child, self.rr, days_ago=240)
        result = self.evaluate(child)
        self.assertIn('RR', self.due_names(result))

    def test_both_doses_done_nothing_due(self):
        """Both doses given → nothing due for RR."""
        child = self.make_child("RR Complete", age_days=600)
        self.give_dose(child, self.rr, days_ago=330)
        self.give_dose(child, self.rr, days_ago=60)
        result = self.evaluate(child)
        self.assertNotIn('RR', self.due_names(result))

    def test_missed_dose1_flagged_missing(self):
        """Child > recommended age with 0 doses → flagged as missing."""
        child = self.make_child("Missed RR", age_days=400)
        result = self.evaluate(child)
        self.assertIn('RR', self.missing_names(result))
