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
from vaccines.models import Vaccine, ScheduleRule, CatchupRule, VaccineGroup, GroupRule


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

        import json
        import os
        from django.conf import settings

        policy_path = os.path.join(settings.BASE_DIR, 'vaccines', 'policy_reference.json')
        with open(policy_path, 'r') as f:
            policy = json.load(f)

        # --- Vaccines ---
        self.vaccine_map = {}
        for v_data in policy['vaccines']:
            v = Vaccine.objects.create(name=v_data['name'], live=v_data['live'])
            self.vaccine_map[v_data['name']] = v
        
        # Shortcuts for existing tests
        self.penta = self.vaccine_map.get('Penta')
        self.dtc = self.vaccine_map.get('DTC')
        self.td = self.vaccine_map.get('Td')
        self.rr = self.vaccine_map.get('RR')
        self.bcg = self.vaccine_map.get('BCG')

        # --- Schedule Rules ---
        for sr_data in policy['schedule_rules']:
            vaccine = self.vaccine_map[sr_data['vaccine']]
            for rule in sr_data['rules']:
                ScheduleRule.objects.create(vaccine=vaccine, **rule)

        # --- Catch-up Rules ---
        for cr_data in policy['catchup_rules']:
            vaccine = self.vaccine_map[cr_data['vaccine']]
            for rule in cr_data['rules']:
                CatchupRule.objects.create(vaccine=vaccine, **rule)

        # --- Vaccine Groups ---
        for g_data in policy['groups']:
            group = VaccineGroup.objects.create(
                name=g_data['name'], 
                min_valid_interval_days=g_data['min_valid_interval_days']
            )
            g_vaccines = [self.vaccine_map[name] for name in g_data['vaccines']]
            group.vaccines.set(g_vaccines)
            
            for r_data in g_data['rules']:
                v_name = r_data.pop('vaccine_to_give')
                v_to_give = self.vaccine_map[v_name]
                GroupRule.objects.create(group=group, vaccine_to_give=v_to_give, **r_data)
            
            if g_data['name'] == 'DTP Family':
                self.dtp_group = group



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
        return sorted([d['vaccine'].name for d in result['due_today']])

    def missing_names(self, result):
        """Helper: get sorted list of missing vaccine names."""
        return sorted([v.name for v in result['missing_doses']])

    def upcoming_names(self, result):
        """Helper: get sorted list of upcoming vaccine names."""
        return sorted([v.name for v, d in result['upcoming']])
