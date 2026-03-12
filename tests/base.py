"""
Shared test setup for vaccination engine tests.
Creates vaccines, schedule rules, vaccine groups, and series policies
that mirror the production DTP Family configuration.

Note: We use setUp() (per-test) rather than setUpTestData() (per-class)
because the engine modifies VaccinationRecord objects via .save() during
evaluation. Using setUpTestData would corrupt shared reference objects
across test methods within the same class.
"""
from datetime import date, timedelta

from django.conf import settings
from django.test import TestCase

from patients.models import Child, VaccinationRecord
from vaccines.models import (
    CatchupRule,
    GroupRule,
    Product,
    ScheduleRule,
    Series,
    SeriesProduct,
    SeriesRule,
    Vaccine,
    VaccineGroup,
)


class BaseVaccinationTestCase(TestCase):
    include_dtp_legacy_group = True

    """
    Base class that sets up the full vaccine configuration per test:
    - Penta, DTC, Td (grouped as DTP Family)
    - RR (standard schedule vaccine, live)
    - All GroupRules for DTP Family
    - ScheduleRules for standard vaccines
    - Explicit series policy for DTP Family
    """

    def setUp(self):
        super().setUp()
        self._child_counter = 0

        import json
        import os

        policy_path = os.path.join(settings.BASE_DIR, 'vaccines', 'policy_reference.json')
        with open(policy_path, 'r') as handle:
            policy = json.load(handle)

        self.vaccine_map = {}
        self.product_map = {}
        self.series_map = {}
        self.group_map = {}

        for vaccine_data in policy['vaccines']:
            vaccine = Vaccine.objects.create(name=vaccine_data['name'], live=vaccine_data['live'])
            self.vaccine_map[vaccine_data['name']] = vaccine
            product = Product.objects.create(vaccine=vaccine, manufacturer=vaccine_data.get('manufacturer'))
            self.product_map[vaccine_data['name']] = product

        self.penta = self.vaccine_map.get('Penta')
        self.dtc = self.vaccine_map.get('DTC')
        self.td = self.vaccine_map.get('Td')
        self.rr = self.vaccine_map.get('RR')
        self.bcg = self.vaccine_map.get('BCG')

        for schedule_data in policy['schedule_rules']:
            vaccine = self.vaccine_map[schedule_data['vaccine']]
            for rule in schedule_data['rules']:
                ScheduleRule.objects.create(vaccine=vaccine, **rule)

        for catchup_data in policy['catchup_rules']:
            vaccine = self.vaccine_map[catchup_data['vaccine']]
            for rule in catchup_data['rules']:
                CatchupRule.objects.create(vaccine=vaccine, **rule)

        self.dtp_group = None

        for group_data in policy['groups']:
            if group_data['name'] == 'DTP Family' and not self.include_dtp_legacy_group:
                continue

            group = VaccineGroup.objects.create(
                name=group_data['name'],
                min_valid_interval_days=group_data['min_valid_interval_days'],
            )
            group_vaccines = [self.vaccine_map[name] for name in group_data['vaccines']]
            group.vaccines.set(group_vaccines)
            self.group_map[group_data['name']] = group

            for rule_data in group_data['rules']:
                GroupRule.objects.create(
                    group=group,
                    vaccine_to_give=self.vaccine_map[rule_data['vaccine_to_give']],
                    prior_doses=rule_data['prior_doses'],
                    min_age_days=rule_data['min_age_days'],
                    max_age_days=rule_data['max_age_days'],
                    min_interval_days=rule_data['min_interval_days'],
                    dose_amount=rule_data.get('dose_amount'),
                )

            if group_data['name'] == 'DTP Family':
                self.dtp_group = group

        explicit_series_names = set()
        for series_data in policy.get('series', []):
            series = Series.objects.create(
                name=series_data['name'],
                min_valid_interval_days=series_data['min_valid_interval_days'],
                mixing_policy=series_data.get('mixing_policy', Series.MIXING_AGE_RULE),
                legacy_group=self.group_map.get(series_data.get('legacy_group')) if series_data.get('legacy_group') else None,
            )
            self.series_map[series_data['name']] = series
            explicit_series_names.add(series_data['name'])

            for index, product_name in enumerate(series_data['products']):
                SeriesProduct.objects.create(
                    series=series,
                    product=self.product_map[product_name],
                    priority=index,
                )

            for rule_data in series_data['rules']:
                SeriesRule.objects.create(
                    series=series,
                    slot_number=rule_data['slot_number'],
                    prior_valid_doses=rule_data['prior_valid_doses'],
                    min_age_days=rule_data['min_age_days'],
                    recommended_age_days=rule_data['recommended_age_days'],
                    overdue_age_days=rule_data.get('overdue_age_days'),
                    max_age_days=rule_data.get('max_age_days'),
                    min_interval_days=rule_data['min_interval_days'],
                    product=self.product_map[rule_data['product']],
                    dose_amount=rule_data.get('dose_amount'),
                    notes=rule_data.get('notes'),
                )

            if series_data['name'] == 'DTP Family':
                self.dtp_series = series

        for group_data in policy['groups']:
            if group_data['name'] in explicit_series_names:
                continue

            group = self.group_map[group_data['name']]
            group_vaccines = [self.vaccine_map[name] for name in group_data['vaccines']]
            series = Series.objects.create(
                name=group_data['name'],
                min_valid_interval_days=group_data['min_valid_interval_days'],
                legacy_group=group,
            )
            self.series_map[group_data['name']] = series

            for index, vaccine in enumerate(group_vaccines):
                SeriesProduct.objects.create(
                    series=series,
                    product=self.product_map[vaccine.name],
                    priority=index,
                )

            for rule_data in group_data['rules']:
                vaccine_name = rule_data['vaccine_to_give']
                product = self.product_map[vaccine_name]
                group_rule = GroupRule.objects.filter(
                    group=group,
                    vaccine_to_give=self.vaccine_map[vaccine_name],
                    prior_doses=rule_data['prior_doses'],
                    min_age_days=rule_data['min_age_days'],
                    max_age_days=rule_data['max_age_days'],
                    min_interval_days=rule_data['min_interval_days'],
                ).first()
                slot_number = rule_data['prior_doses'] + 1
                schedule_rule = ScheduleRule.objects.filter(
                    vaccine=self.vaccine_map[vaccine_name],
                    dose_number=slot_number,
                ).first()
                min_age = max(rule_data['min_age_days'], schedule_rule.min_age_days) if schedule_rule else rule_data['min_age_days']
                recommended_age = max(min_age, schedule_rule.recommended_age_days) if schedule_rule else rule_data['min_age_days']
                overdue_age = schedule_rule.overdue_age_days if schedule_rule and schedule_rule.overdue_age_days is not None else recommended_age
                dose_amount = rule_data.get('dose_amount') or (schedule_rule.dose_amount if schedule_rule else None)
                SeriesRule.objects.create(
                    series=series,
                    slot_number=slot_number,
                    prior_valid_doses=rule_data['prior_doses'],
                    min_age_days=min_age,
                    recommended_age_days=recommended_age,
                    overdue_age_days=overdue_age,
                    max_age_days=rule_data['max_age_days'],
                    min_interval_days=group_rule.min_interval_days if group_rule else rule_data['min_interval_days'],
                    product=product,
                    dose_amount=dose_amount,
                )

    def make_child(self, name, age_days, child_id=None):
        self._child_counter += 1
        uid = child_id or f"{self.__class__.__name__}_{self._testMethodName}_{self._child_counter}"
        dob = date.today() - timedelta(days=age_days)
        return Child.objects.create(id=uid, name=name, sex='M', dob=dob)

    def give_dose(self, child, vaccine, days_ago):
        return VaccinationRecord.objects.create(
            child=child,
            vaccine=vaccine,
            date_given=date.today() - timedelta(days=days_ago),
        )

    def evaluate(self, child):
        from vaccines.engine import VaccinationEngine

        engine = VaccinationEngine(child, evaluation_date=date.today())
        return engine.evaluate()

    def due_names(self, result):
        return sorted([dose['vaccine'].name for dose in result['due_today']])

    def missing_names(self, result):
        return sorted([dose['vaccine'].name for dose in result['missing_doses']])

    def upcoming_names(self, result):
        return sorted([item[0].name for item in result['upcoming']])
