"""
Shared test setup for vaccination engine tests.
Creates vaccines, schedule rules, vaccine groups, and group rules
that mirror the production DTP Family configuration.

Note: We use setUp() (per-test) rather than setUpTestData() (per-class)
because the engine modifies VaccinationRecord objects via .save() during
evaluation. Using setUpTestData would corrupt shared reference objects
across test methods within the same class.
"""
from datetime import date, timedelta
from django.test import TestCase
from patients.models import Child, VaccinationRecord
from vaccines.models import Vaccine, ScheduleRule, VaccineGroup, GroupRule


class BaseVaccinationTestCase(TestCase):
    """
    Base class that sets up the full vaccine configuration per test:
    - Penta, DTC, Td (grouped as DTP Family)
    - RR (standard schedule vaccine, live)
    - All GroupRules for DTP Family
    - ScheduleRules for standard vaccines
    """

    def setUp(self):
        super().setUp()
        self._child_counter = 0

        # --- Vaccines ---
        self.penta = Vaccine.objects.create(name='Penta', live=False)
        self.dtc = Vaccine.objects.create(name='DTC', live=False)
        self.td = Vaccine.objects.create(name='Td', live=False)
        self.rr = Vaccine.objects.create(name='RR', live=True)

        # --- Standard ScheduleRules for RR ---
        ScheduleRule.objects.create(
            vaccine=self.rr, dose_number=1,
            min_age_days=250, recommended_age_days=270, min_interval_days=0
        )
        ScheduleRule.objects.create(
            vaccine=self.rr, dose_number=2,
            min_age_days=500, recommended_age_days=540, min_interval_days=28
        )

        # --- Standard ScheduleRules for DTP family (Safety Floors vs Recommendations) ---
        # Penta 1: Safety floor 42d, Recommended 60d (2mo)
        ScheduleRule.objects.create(
            vaccine=self.penta, dose_number=1, 
            min_age_days=42, recommended_age_days=60
        )
        # Penta 2: Safety floor 70d, Recommended 90d (3mo)
        ScheduleRule.objects.create(
            vaccine=self.penta, dose_number=2, 
            min_age_days=70, recommended_age_days=90
        )
        # Penta 3: Safety floor 98d, Recommended 120d (4mo)
        ScheduleRule.objects.create(
            vaccine=self.penta, dose_number=3, 
            min_age_days=98, recommended_age_days=120
        )
        # DTC (Booster 1 at 18m, Booster 2 at 5y)
        ScheduleRule.objects.create(
            vaccine=self.dtc, dose_number=1, 
            min_age_days=18*30, recommended_age_days=18*30
        )
        ScheduleRule.objects.create(
            vaccine=self.dtc, dose_number=2, 
            min_age_days=5*365, recommended_age_days=5*365
        )
        # Td (Catchup/Booster > 7y)
        ScheduleRule.objects.create(
            vaccine=self.td, dose_number=1, 
            min_age_days=7*365, recommended_age_days=7*365
        )



        # --- DTP Family Group ---
        self.dtp_group = VaccineGroup.objects.create(
            name='DTP Family', min_valid_interval_days=28
        )
        self.dtp_group.vaccines.set([self.penta, self.dtc, self.td])

        # Age constants (days)
        MO_12 = 365
        MO_18 = 18 * 30
        YR_3 = 3 * 365
        YR_5 = 5 * 365
        YR_7 = 7 * 365

        # --- GroupRules for DTP Family ---
        group_rules = [
            # 0 prior doses
            (0, 0, MO_12 - 1, self.penta, 0),
            (0, MO_12, YR_3 - 1, self.penta, 0),
            (0, YR_3, YR_7 - 1, self.dtc, 0),
            (0, YR_7, None, self.td, 0),
            # 1 prior dose
            (1, 0, MO_18 - 1, self.penta, 28),
            (1, MO_18, YR_3 - 1, self.penta, 28),
            (1, YR_3, YR_7 - 1, self.dtc, 28),
            (1, YR_7, None, self.td, 28),
            # 2 prior doses
            (2, 0, MO_18 - 1, self.penta, 28),
            (2, MO_18, YR_3 - 1, self.penta, 28),
            (2, YR_3, YR_7 - 1, self.dtc, 28),
            (2, YR_7, None, self.td, 28),
            # 3 prior doses (primary complete, boosters)
            (3, MO_18, None, self.dtc, 180),
            (3, YR_7, None, self.td, 180),
            # 4 prior doses (B1 complete)
            (4, YR_5, None, self.dtc, 4 * 365),
            (4, YR_7, None, self.td, 365),
        ]
        for prior, min_age, max_age, vaccine, interval in group_rules:
            GroupRule.objects.create(
                group=self.dtp_group,
                prior_doses=prior,
                min_age_days=min_age,
                max_age_days=max_age,
                vaccine_to_give=vaccine,
                min_interval_days=interval,
            )



    def make_child(self, name, age_days, child_id=None):
        """Helper: create a child with given age in days. ID is unique per test."""
        self._child_counter += 1
        uid = child_id or f"{self.__class__.__name__}_{self._testMethodName}_{self._child_counter}"
        dob = date.today() - timedelta(days=age_days)
        return Child.objects.create(id=uid, name=name, sex='M', dob=dob)

    def give_dose(self, child, vaccine, days_ago):
        """Helper: record a dose given `days_ago` days before today."""
        return VaccinationRecord.objects.create(
            child=child, vaccine=vaccine,
            date_given=date.today() - timedelta(days=days_ago)
        )

    def evaluate(self, child):
        """Helper: run the engine and return results."""
        from vaccines.engine import VaccinationEngine
        engine = VaccinationEngine(child, evaluation_date=date.today())
        return engine.evaluate()

    def due_names(self, result):
        """Helper: get sorted list of vaccine names due today."""
        return sorted([v.name for v in result['due_today']])

    def missing_names(self, result):
        """Helper: get sorted list of missing vaccine names."""
        return sorted([v.name for v in result['missing_doses']])

    def upcoming_names(self, result):
        """Helper: get sorted list of upcoming vaccine names."""
        return sorted([v.name for v, d in result['upcoming']])
