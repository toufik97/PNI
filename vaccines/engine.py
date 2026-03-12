from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from patients.models import Child, VaccinationRecord
from vaccines.availability import AvailabilityResolver
from vaccines.dependencies import DependencyEvaluator
from vaccines.global_constraints import LiveVaccineConstraintService
from vaccines.history_normalizer import HistoryNormalizer
from vaccines.models import CatchupRule, GlobalConstraintRule, Product, ScheduleRule, Series, Vaccine, VaccineGroup
from vaccines.policy_loader import PolicyLoader
from vaccines.recommender import SeriesRecommender
from vaccines.series_validator import SeriesHistoryValidator


class VaccinationEngine:
    POLICY_VERSION = 'series-policy-v1'

    DECISION_DUE = 'due_today'
    DECISION_DUE_UNAVAILABLE = 'due_but_unavailable'
    DECISION_UPCOMING = 'upcoming'
    DECISION_MISSING = 'missing'
    DECISION_BLOCKED = 'blocked'
    DECISION_INVALID = 'invalid_history'

    SOURCE_SERIES_RULE = 'series_rule'
    SOURCE_SCHEDULE_RULE = 'schedule_rule'
    SOURCE_CATCHUP_RULE = 'catchup_rule'
    SOURCE_GROUP_RULE = 'group_rule'
    SOURCE_GLOBAL_CONSTRAINT = 'global_constraint'
    SOURCE_UNKNOWN = 'unknown'

    GLOBAL_LIVE_RULE_KEY = 'global:live-live-28d'

    def __init__(self, child: Child, evaluation_date: date = None):
        self.child = child
        self.evaluation_date = evaluation_date or date.today()
        self.age_days = (self.evaluation_date - self.child.dob).days
        self.age_months = self.age_days / 30.44
        self.age_years = self.age_days / 365.25
        self.records = list(self.child.vaccination_records.all().order_by('date_given'))
        self.history = HistoryNormalizer(self.child, self.records)
        self.records = self.history.records
        self.policy_loader = PolicyLoader()
        self.vaccines = self.policy_loader.get_all_vaccines()
        self.series_history_cache: Dict[int, List[VaccinationRecord]] = {}
        self.invalid_history: List[Dict[str, Any]] = []
        self.policy_version = self.policy_loader.get_active_policy_version()
        self.policy_version_code = self.policy_version.code if self.policy_version else self.POLICY_VERSION
        self.availability = AvailabilityResolver()
        self.dependencies = DependencyEvaluator(
            series_history_cache=self.series_history_cache,
            dependency_rule_key_builder=self._dependency_rule_key,
        )
        self.global_constraints = LiveVaccineConstraintService(
            global_live_rule_key=self.GLOBAL_LIVE_RULE_KEY,
            product_lookup=self._product_for_vaccine,
            flag_invalid=self._flag_invalid,
            build_live_deferral_item=self._build_live_deferral_item,
            spacing_days_resolver=self._live_spacing_days,
        )
        self.recommender = SeriesRecommender(
            child=self.child,
            evaluation_date=self.evaluation_date,
            age_days=self.age_days,
            availability=self.availability,
            dependencies=self.dependencies,
            series_history_cache=self.series_history_cache,
            state_to_due_item=self._state_to_due_item,
            state_to_missing_item=self._state_to_missing_item,
            state_to_upcoming_item=self._state_to_upcoming_item,
            state_to_blocked_item=self._state_to_blocked_item,
        )

    def evaluate(self) -> Dict[str, Any]:
        history_by_vaccine = self._group_history()
        self._validate_history(history_by_vaccine)

        due_today = []
        due_but_unavailable = []
        blocked = []
        missing_doses = []
        upcoming_details = []

        active_series = self.policy_loader.get_active_series()
        covered_group_ids = set()
        covered_vaccine_names = set()

        for series in active_series:
            self.series_history_cache[series.id] = self._validate_series_history(series, history_by_vaccine)

        for series in active_series:
            series_eval = self._recommend_series(series)
            due_today.extend(series_eval['due_today'])
            due_but_unavailable.extend(series_eval['due_but_unavailable'])
            blocked.extend(series_eval['blocked'])
            missing_doses.extend(series_eval['missing_doses'])
            upcoming_details.extend(series_eval['upcoming'])

            if series.legacy_group_id:
                covered_group_ids.add(series.legacy_group_id)

            for link in series.series_products.all():
                covered_vaccine_names.add(link.product.vaccine.name)

        groups = self.policy_loader.get_vaccine_groups()
        covered_group_ids.update(self._series_owned_group_ids(active_series, groups))
        grouped_vaccine_names = set(covered_vaccine_names)

        for group in groups:
            if group.id in covered_group_ids:
                for vaccine in group.vaccines.all():
                    grouped_vaccine_names.add(vaccine.name)
                continue

            group_eval = self._evaluate_vaccine_group(group, history_by_vaccine)
            due_today.extend(group_eval['due_today'])
            missing_doses.extend(group_eval['missing_doses'])
            upcoming_details.extend(group_eval['upcoming'])
            for vaccine in group.vaccines.all():
                grouped_vaccine_names.add(vaccine.name)

        for vaccine in self.vaccines:
            if vaccine.name in grouped_vaccine_names:
                continue

            v_history = [record for record in history_by_vaccine.get(vaccine.id, []) if not record.invalid_flag]
            prior_doses = len(v_history)
            product = self._product_for_vaccine(vaccine)

            applicable_catchup = CatchupRule.objects.filter(
                vaccine=vaccine,
                min_age_days__lte=self.age_days,
                max_age_days__gte=self.age_days,
                prior_doses=prior_doses,
            ).first()

            if applicable_catchup:
                if prior_doses < applicable_catchup.doses_required:
                    last_dose_date = v_history[-1].date_given if v_history else None
                    standard_rule = ScheduleRule.objects.filter(
                        vaccine=vaccine,
                        dose_number=prior_doses + 1,
                    ).first()
                    dose_val = applicable_catchup.dose_amount or (standard_rule.dose_amount if standard_rule else None)
                    rule_key = self._catchup_rule_key(applicable_catchup)

                    if last_dose_date:
                        days_since_last = (self.evaluation_date - last_dose_date).days
                        if days_since_last >= applicable_catchup.min_interval_days:
                            due_today.append(self._build_decision_item(
                                vaccine=vaccine,
                                dose_amount=dose_val,
                                dose_number=prior_doses + 1,
                                decision_type=self.DECISION_DUE,
                                decision_source=self.SOURCE_CATCHUP_RULE,
                                rule_key=rule_key,
                                reason_code='catchup_due',
                                message=f"{vaccine.name} catch-up dose {prior_doses + 1} is due today.",
                                product=product,
                            ))
                            missing_doses.append(self._build_decision_item(
                                vaccine=vaccine,
                                dose_amount=dose_val,
                                dose_number=prior_doses + 1,
                                decision_type=self.DECISION_MISSING,
                                decision_source=self.SOURCE_CATCHUP_RULE,
                                rule_key=rule_key,
                                reason_code='catchup_missing',
                                message=f"{vaccine.name} catch-up dose {prior_doses + 1} is overdue.",
                                product=product,
                            ))
                        else:
                            next_due_date = last_dose_date + timedelta(days=applicable_catchup.min_interval_days)
                            upcoming_details.append(self._build_decision_item(
                                vaccine=vaccine,
                                dose_amount=dose_val,
                                dose_number=prior_doses + 1,
                                decision_type=self.DECISION_UPCOMING,
                                decision_source=self.SOURCE_CATCHUP_RULE,
                                rule_key=rule_key,
                                reason_code='catchup_upcoming',
                                message=f"{vaccine.name} catch-up dose {prior_doses + 1} becomes eligible on {next_due_date.isoformat()}.",
                                product=product,
                                target_date=next_due_date,
                            ))
                    else:
                        due_today.append(self._build_decision_item(
                            vaccine=vaccine,
                            dose_amount=dose_val,
                            dose_number=prior_doses + 1,
                            decision_type=self.DECISION_DUE,
                            decision_source=self.SOURCE_CATCHUP_RULE,
                            rule_key=rule_key,
                            reason_code='catchup_due',
                            message=f"{vaccine.name} catch-up dose {prior_doses + 1} is due today.",
                            product=product,
                        ))
                        missing_doses.append(self._build_decision_item(
                            vaccine=vaccine,
                            dose_amount=dose_val,
                            dose_number=prior_doses + 1,
                            decision_type=self.DECISION_MISSING,
                            decision_source=self.SOURCE_CATCHUP_RULE,
                            rule_key=rule_key,
                            reason_code='catchup_missing',
                            message=f"{vaccine.name} catch-up dose {prior_doses + 1} is overdue.",
                            product=product,
                        ))
                continue

            next_dose_num = prior_doses + 1
            rule = ScheduleRule.objects.filter(vaccine=vaccine, dose_number=next_dose_num).first()
            if not rule:
                continue

            if prior_doses == 0:
                target_date = self.child.dob + timedelta(days=rule.recommended_age_days)
            else:
                last_dose_date = v_history[-1].date_given
                interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
                age_floor_date = self.child.dob + timedelta(days=rule.min_age_days)
                target_date = max(interval_date, age_floor_date)

            overdue_child_age = rule.overdue_age_days if rule.overdue_age_days is not None else rule.recommended_age_days
            overdue_date = self.child.dob + timedelta(days=overdue_child_age)
            rule_key = self._schedule_rule_key(rule)

            if self.evaluation_date > overdue_date:
                missing_doses.append(self._build_decision_item(
                    vaccine=vaccine,
                    dose_amount=rule.dose_amount,
                    dose_number=next_dose_num,
                    decision_type=self.DECISION_MISSING,
                    decision_source=self.SOURCE_SCHEDULE_RULE,
                    rule_key=rule_key,
                    reason_code='schedule_missing',
                    message=f"{vaccine.name} dose {next_dose_num} is overdue.",
                    product=product,
                ))

            if self.evaluation_date >= target_date:
                if rule.max_age_days and self.age_days > rule.max_age_days:
                    continue
                due_today.append(self._build_decision_item(
                    vaccine=vaccine,
                    dose_amount=rule.dose_amount,
                    dose_number=next_dose_num,
                    decision_type=self.DECISION_DUE,
                    decision_source=self.SOURCE_SCHEDULE_RULE,
                    rule_key=rule_key,
                    reason_code='schedule_due',
                    message=f"{vaccine.name} dose {next_dose_num} is due today.",
                    product=product,
                ))
            else:
                upcoming_details.append(self._build_decision_item(
                    vaccine=vaccine,
                    dose_amount=rule.dose_amount,
                    dose_number=next_dose_num,
                    decision_type=self.DECISION_UPCOMING,
                    decision_source=self.SOURCE_SCHEDULE_RULE,
                    rule_key=rule_key,
                    reason_code='schedule_upcoming',
                    message=f"{vaccine.name} dose {next_dose_num} becomes eligible on {target_date.isoformat()}.",
                    product=product,
                    target_date=target_date,
                ))

        due_today, deferred_upcoming = self.global_constraints.defer_recommendations(
            self.records,
            due_today,
            self.evaluation_date,
        )
        upcoming_details.extend(deferred_upcoming)

        due_today = self._normalize_due_items(due_today)
        due_but_unavailable = self._normalize_due_items(due_but_unavailable)
        missing_doses = self._normalize_due_items(missing_doses)
        blocked = self._normalize_due_items(blocked)
        upcoming_details = self._normalize_due_items(upcoming_details)
        upcoming = [self._upcoming_tuple(item) for item in upcoming_details]
        next_appointment = min([item['target_date'] for item in upcoming_details], default=None)

        return {
            'policy_version': self.policy_version_code,
            'due_today': due_today,
            'due_but_unavailable': due_but_unavailable,
            'blocked': blocked,
            'missing_doses': missing_doses,
            'next_appointment': next_appointment,
            'upcoming': upcoming,
            'upcoming_details': upcoming_details,
            'invalid_history': self.invalid_history,
        }

    def _normalize_due_items(self, items):
        normalized = []
        for item in items:
            if isinstance(item, dict):
                item.setdefault('policy_version', self.policy_version_code)
                item.setdefault('blocking_constraints', [])
                normalized.append(item)
            else:
                normalized.append(self._build_decision_item(
                    vaccine=item,
                    decision_type='legacy_unknown',
                    decision_source=self.SOURCE_UNKNOWN,
                    rule_key='legacy:unknown',
                    reason_code='legacy_item',
                    message=f"{item.name} returned from legacy engine path.",
                ))
        return normalized

    def _upcoming_tuple(self, item):
        return (item['vaccine'], item['target_date'], item['dose_number'])

    def _group_history(self) -> Dict[str, List[VaccinationRecord]]:
        return self.history.history_by_vaccine

    def _product_for_vaccine(self, vaccine: Vaccine):
        try:
            return vaccine.product_profile
        except Product.DoesNotExist:
            return None

    def _schedule_rule_key(self, rule: ScheduleRule) -> str:
        return f"schedule:{rule.vaccine_id}:{rule.dose_number}"

    def _catchup_rule_key(self, rule: CatchupRule) -> str:
        return f"catchup:{rule.vaccine_id}:{rule.prior_doses}:{rule.min_age_days}:{rule.max_age_days}"

    def _series_rule_key(self, rule) -> str:
        return f"series:{rule.series.code}:slot:{rule.slot_number}:product:{rule.product.code}"

    def _series_interval_rule_key(self, series: Series, slot_number: int) -> str:
        return f"series:{series.code}:slot:{slot_number}:interval"

    def _series_candidate_rule_key(self, series: Series, slot_number: int) -> str:
        return f"series:{series.code}:slot:{slot_number}:candidate-set"

    def _group_rule_key(self, group: VaccineGroup, rule, dose_number: int) -> str:
        return f"group:{group.id}:dose:{dose_number}:vaccine:{rule.vaccine_to_give_id}"

    def _group_interval_rule_key(self, group: VaccineGroup, dose_number: int) -> str:
        return f"group:{group.id}:dose:{dose_number}:interval"

    def _dependency_rule_key(self, dependency, slot_number: int) -> str:
        anchor_slot = dependency.anchor_slot_number or slot_number
        return f"dependency:{dependency.dependent_series.code}:{slot_number}:{dependency.anchor_series.code}:{anchor_slot}:{dependency.min_offset_days}"

    def _policy_version_code(self, series: Optional[Series] = None, group: Optional[VaccineGroup] = None) -> str:
        if series and series.policy_version_id:
            return series.policy_version.code
        if group and hasattr(group, 'series_policy') and group.series_policy and group.series_policy.policy_version_id:
            return group.series_policy.policy_version.code
        return self.policy_version_code

    def _build_decision_item(
        self,
        *,
        vaccine: Vaccine,
        decision_type: str,
        decision_source: str,
        rule_key: str,
        reason_code: str,
        message: str,
        dose_number: Optional[int] = None,
        dose_amount: Optional[str] = None,
        series: Optional[Series] = None,
        group: Optional[VaccineGroup] = None,
        product: Optional[Product] = None,
        target_date: Optional[date] = None,
        blocking_constraints: Optional[List[Dict[str, Any]]] = None,
        unavailable: bool = False,
    ) -> Dict[str, Any]:
        item = {
            'vaccine': vaccine,
            'dose_amount': dose_amount,
            'dose_number': dose_number,
            'slot_number': dose_number,
            'decision_type': decision_type,
            'decision_source': decision_source,
            'rule_key': rule_key,
            'reason_code': reason_code,
            'message': message,
            'policy_version': self.policy_version_code,
            'series_code': series.code if series else None,
            'series_name': series.name if series else None,
            'group_code': str(group.id) if group else None,
            'group_name': group.name if group else None,
            'product_code': product.code if product else None,
            'product_name': product.vaccine.name if product else vaccine.name,
            'blocking_constraints': list(blocking_constraints or []),
        }
        if target_date is not None:
            item['target_date'] = target_date
        if unavailable:
            item['unavailable'] = True
        return item

    def _live_spacing_days(self) -> int:
        return GlobalConstraintRule.get_live_spacing_days(self.policy_version)

    def _build_live_deferral_item(self, item: Dict[str, Any], safe_date: date, recent_live_doses: List[VaccinationRecord]) -> Dict[str, Any]:
        reasons = [record.vaccine.name for record in recent_live_doses]
        deferred = dict(item)
        deferred['decision_type'] = self.DECISION_UPCOMING
        deferred['decision_source'] = self.SOURCE_GLOBAL_CONSTRAINT
        deferred['rule_key'] = self.GLOBAL_LIVE_RULE_KEY
        deferred['reason_code'] = 'live_vaccine_deferral'
        deferred['message'] = (
            f"{item['vaccine'].name} is deferred until {safe_date.isoformat()} because of recent live vaccine spacing "
            f"with {', '.join(reasons)}."
        )
        deferred['target_date'] = safe_date
        deferred['blocking_constraints'] = [{
            'rule_key': self.GLOBAL_LIVE_RULE_KEY,
            'reason_code': 'live_vaccine_deferral',
            'message': deferred['message'],
        }]
        return deferred

    def _flag_invalid(
        self,
        record: VaccinationRecord,
        reason_code: str,
        message: str,
        *,
        decision_source: str = SOURCE_UNKNOWN,
        rule_key: str = 'validation:unknown',
        series: Optional[Series] = None,
        group: Optional[VaccineGroup] = None,
        product: Optional[Product] = None,
        slot_number: Optional[int] = None,
    ):
        record.invalid_flag = True
        record.invalid_reason = reason_code
        record.notes = message
        record.save()

        self.invalid_history.append({
            'record_id': record.id,
            'vaccine': record.vaccine,
            'date_given': record.date_given,
            'dose_number': slot_number,
            'slot_number': slot_number,
            'decision_type': self.DECISION_INVALID,
            'decision_source': decision_source,
            'rule_key': rule_key,
            'reason_code': reason_code,
            'message': message,
            'policy_version': self.policy_version_code,
            'series_code': series.code if series else None,
            'series_name': series.name if series else None,
            'group_code': str(group.id) if group else None,
            'group_name': group.name if group else None,
            'product_code': product.code if product else None,
            'product_name': product.vaccine.name if product else record.vaccine.name,
            'blocking_constraints': [],
        })
    def _validate_history(self, history_by_vaccine: Dict[str, List[VaccinationRecord]]):
        from patients.models import VaccinationRecord as VR

        series_vaccine_ids = set(
            Product.objects.filter(series_memberships__active=True).values_list('vaccine_id', flat=True)
        )
        grouped_vaccine_ids = set(VaccineGroup.objects.values_list('vaccines__id', flat=True))
        skip_vaccine_ids = {vaccine_id for vaccine_id in series_vaccine_ids.union(grouped_vaccine_ids) if vaccine_id}

        for vaccine_id, records in history_by_vaccine.items():
            if vaccine_id in skip_vaccine_ids:
                continue

            valid_records = []
            for record in records:
                if record.invalid_flag:
                    continue

                age_at_dose = self.history.age_at_dose(record)
                dose_num = len(valid_records) + 1
                rule = ScheduleRule.objects.filter(vaccine_id=vaccine_id, dose_number=dose_num).first()
                product = self._product_for_vaccine(record.vaccine)

                if rule:
                    rule_key = self._schedule_rule_key(rule)
                    if age_at_dose < rule.min_age_days:
                        age_months = round(age_at_dose / 30.44, 1)
                        min_months = round(rule.min_age_days / 30.44, 1)
                        self._flag_invalid(
                            record,
                            VR.REASON_TOO_EARLY,
                            f"Too early: {record.vaccine.name} dose {dose_num} requires min age {min_months} months. Child was {age_months} months old.",
                            decision_source=self.SOURCE_SCHEDULE_RULE,
                            rule_key=rule_key,
                            product=product,
                            slot_number=dose_num,
                        )
                        continue

                    if rule.max_age_days and age_at_dose > rule.max_age_days:
                        age_months = round(age_at_dose / 30.44, 1)
                        max_months = round(rule.max_age_days / 30.44, 1)
                        self._flag_invalid(
                            record,
                            VR.REASON_TOO_LATE,
                            f"Too late: {record.vaccine.name} dose {dose_num} is not valid after {max_months} months. Child was {age_months} months old.",
                            decision_source=self.SOURCE_SCHEDULE_RULE,
                            rule_key=rule_key,
                            product=product,
                            slot_number=dose_num,
                        )
                        continue

                    if valid_records and rule.min_interval_days:
                        days_since = (record.date_given - valid_records[-1].date_given).days
                        if days_since < rule.min_interval_days:
                            self._flag_invalid(
                                record,
                                VR.REASON_INTERVAL,
                                f"Too soon: {record.vaccine.name} dose {dose_num} requires {rule.min_interval_days} days after previous dose. Only {days_since} days elapsed.",
                                decision_source=self.SOURCE_SCHEDULE_RULE,
                                rule_key=rule_key,
                                product=product,
                                slot_number=dose_num,
                            )
                            continue

                valid_records.append(record)

        self.global_constraints.validate_history(self.records, self.SOURCE_GLOBAL_CONSTRAINT)


    def _series_owned_group_ids(self, active_series: List[Series], groups) -> set[int]:
        owned_group_ids = set()
        series_product_vaccine_ids = [
            {link.product.vaccine_id for link in series.series_products.all()}
            for series in active_series
        ]

        for group in groups:
            group_vaccine_ids = {vaccine.id for vaccine in group.vaccines.all()}
            if not group_vaccine_ids:
                continue

            for series_vaccine_ids in series_product_vaccine_ids:
                if group_vaccine_ids.issubset(series_vaccine_ids):
                    owned_group_ids.add(group.id)
                    break

        return owned_group_ids

    def _validate_series_history(self, series: Series, history_by_vaccine: Dict[str, List[VaccinationRecord]]) -> List[VaccinationRecord]:
        validator = SeriesHistoryValidator(self, history_by_vaccine)
        return validator.validate(series)

    def _recommend_series(self, series: Series) -> Dict[str, Any]:
        return self.recommender.recommend(series)

    def _series_age_candidates(self, series: Series, prior_doses: int, age_days: int):
        return self.recommender.series_age_candidates(series, prior_doses, age_days)

    def _first_series_future_rule(self, series: Series, prior_doses: int, valid_records: List[VaccinationRecord], reference_age_days: Optional[int] = None):
        return self.recommender.first_series_future_rule(series, prior_doses, valid_records, reference_age_days)

    def _filter_series_candidates(self, series: Series, candidates, valid_records: List[VaccinationRecord]):
        return self.recommender.filter_series_candidates(series, candidates, valid_records)

    def _series_product_priority(self, series: Series, product_id: int) -> int:
        return self.availability.series_product_priority(series, product_id)

    def _build_series_candidate_state(self, series: Series, valid_records: List[VaccinationRecord], last_dose_date: Optional[date], rule, future: bool = False):
        return self.recommender.build_series_candidate_state(series, valid_records, last_dose_date, rule, future)

    def _apply_dependency_rules(self, series: Series, slot_number: int, target_date: date):
        return self.dependencies.apply(series, slot_number, target_date)

    def _choose_due_state(self, series: Series, valid_records: List[VaccinationRecord], states):
        return self.availability.choose_due_state(series, valid_records, states)

    def _choose_upcoming_state(self, series: Series, valid_records: List[VaccinationRecord], states):
        return self.availability.choose_upcoming_state(series, valid_records, states)

    def _choose_preferred_state(self, series: Series, valid_records: List[VaccinationRecord], states):
        return self.availability.choose_preferred_state(series, valid_records, states)

    def _state_to_due_item(self, series: Series, state, unavailable: bool = False):
        decision_type = self.DECISION_DUE_UNAVAILABLE if unavailable else self.DECISION_DUE
        reason_code = 'series_due_unavailable' if unavailable else 'series_due'
        message = (
            f"{state['rule'].product.vaccine.name} slot {state['rule'].slot_number} is clinically due but not currently available."
            if unavailable else
            f"{state['rule'].product.vaccine.name} slot {state['rule'].slot_number} is due today under {series.name}."
        )
        return self._build_decision_item(
            vaccine=state['rule'].product.vaccine,
            dose_amount=state['rule'].dose_amount,
            dose_number=state['rule'].slot_number,
            decision_type=decision_type,
            decision_source=self.SOURCE_SERIES_RULE,
            rule_key=self._series_rule_key(state['rule']),
            reason_code=reason_code,
            message=message,
            series=series,
            product=state['rule'].product,
            unavailable=unavailable,
        )

    def _state_to_missing_item(self, series: Series, state):
        return self._build_decision_item(
            vaccine=state['rule'].product.vaccine,
            dose_amount=state['rule'].dose_amount,
            dose_number=state['rule'].slot_number,
            decision_type=self.DECISION_MISSING,
            decision_source=self.SOURCE_SERIES_RULE,
            rule_key=self._series_rule_key(state['rule']),
            reason_code='series_missing',
            message=f"{state['rule'].product.vaccine.name} slot {state['rule'].slot_number} is overdue under {series.name}.",
            series=series,
            product=state['rule'].product,
        )

    def _state_to_upcoming_item(self, series: Series, state):
        return self._build_decision_item(
            vaccine=state['rule'].product.vaccine,
            dose_amount=state['rule'].dose_amount,
            dose_number=state['rule'].slot_number,
            decision_type=self.DECISION_UPCOMING,
            decision_source=self.SOURCE_SERIES_RULE,
            rule_key=self._series_rule_key(state['rule']),
            reason_code='series_upcoming',
            message=f"{state['rule'].product.vaccine.name} slot {state['rule'].slot_number} becomes eligible on {state['target_date'].isoformat()} under {series.name}.",
            series=series,
            product=state['rule'].product,
            target_date=state['target_date'],
            blocking_constraints=state['blocking_constraints'],
        )

    def _state_to_blocked_item(self, series: Series, state):
        reasons = [item['message'] for item in state['blocking_constraints']]
        item = self._build_decision_item(
            vaccine=state['rule'].product.vaccine,
            dose_amount=state['rule'].dose_amount,
            dose_number=state['rule'].slot_number,
            decision_type=self.DECISION_BLOCKED,
            decision_source=self.SOURCE_SERIES_RULE,
            rule_key=self._series_rule_key(state['rule']),
            reason_code='series_blocked',
            message=' '.join(reasons),
            series=series,
            product=state['rule'].product,
            target_date=state['target_date'],
            blocking_constraints=state['blocking_constraints'],
        )
        item['reasons'] = reasons
        return item

    def _evaluate_vaccine_group(self, group: VaccineGroup, history_by_vaccine: Dict[str, List[VaccinationRecord]]) -> Dict[str, Any]:
        result = {'due_today': [], 'missing_doses': [], 'upcoming': []}

        group_records = []
        for vaccine in group.vaccines.all():
            if vaccine.id in history_by_vaccine:
                group_records.extend([
                    record for record in history_by_vaccine[vaccine.id]
                    if not record.invalid_flag
                ])

        group_records.sort(key=lambda record: record.date_given)

        from patients.models import VaccinationRecord as VR

        valid_group_records = []
        for index, record in enumerate(group_records):
            age_at_dose = self.history.age_at_dose(record)
            slot_number = len(valid_group_records) + 1
            product = self._product_for_vaccine(record.vaccine)

            if index > 0 and valid_group_records:
                previous = valid_group_records[-1]
                days_since = (record.date_given - previous.date_given).days
                if days_since < group.min_valid_interval_days:
                    self._flag_invalid(
                        record,
                        VR.REASON_INTERVAL,
                        f"Too soon: Must wait {group.min_valid_interval_days} days between {group.name} doses. Only {days_since} days elapsed since last dose.",
                        decision_source=self.SOURCE_GROUP_RULE,
                        rule_key=self._group_interval_rule_key(group, slot_number),
                        group=group,
                        product=product,
                        slot_number=slot_number,
                    )
                    continue

            expected_rule = group.rules.filter(
                prior_doses=len(valid_group_records),
                min_age_days__lte=age_at_dose,
            ).order_by('-min_age_days').first()

            if expected_rule:
                rule_key = self._group_rule_key(group, expected_rule, slot_number)
                if expected_rule.max_age_days and age_at_dose > expected_rule.max_age_days:
                    age_months = round(age_at_dose / 30.44, 1)
                    max_months = round(expected_rule.max_age_days / 30.44, 1)
                    self._flag_invalid(
                        record,
                        VR.REASON_TOO_LATE,
                        f"Too late: {record.vaccine.name} is not valid after {max_months} months for dose {slot_number}. Child was {age_months} months old.",
                        decision_source=self.SOURCE_GROUP_RULE,
                        rule_key=rule_key,
                        group=group,
                        product=product,
                        slot_number=slot_number,
                    )
                    continue

                if record.vaccine.id != expected_rule.vaccine_to_give.id:
                    age_months = round(age_at_dose / 30.44, 1)
                    self._flag_invalid(
                        record,
                        VR.REASON_WRONG_VACCINE,
                        f"Wrong vaccine: {record.vaccine.name} was given at {age_months} months, but {expected_rule.vaccine_to_give.name} is required at this age for dose {slot_number}.",
                        decision_source=self.SOURCE_GROUP_RULE,
                        rule_key=rule_key,
                        group=group,
                        product=product,
                        slot_number=slot_number,
                    )
                    continue

            valid_group_records.append(record)

        prior_doses = len(valid_group_records)
        last_dose_date = valid_group_records[-1].date_given if valid_group_records else None

        rules = group.rules.filter(
            prior_doses=prior_doses,
            min_age_days__lte=self.age_days,
        )
        valid_rules = [rule for rule in rules if rule.max_age_days is None or self.age_days <= rule.max_age_days]
        if not valid_rules:
            future_rules = group.rules.filter(
                prior_doses=prior_doses,
                min_age_days__gt=self.age_days,
            ).order_by('min_age_days')
            if future_rules.exists():
                next_rule = future_rules.first()
                target_date = self.child.dob + timedelta(days=next_rule.min_age_days)
                if last_dose_date:
                    interval_date = last_dose_date + timedelta(days=next_rule.min_interval_days)
                    target_date = max(target_date, interval_date)

                product = self._product_for_vaccine(next_rule.vaccine_to_give)
                result['upcoming'].append(self._build_decision_item(
                    vaccine=next_rule.vaccine_to_give,
                    dose_amount=next_rule.dose_amount,
                    dose_number=prior_doses + 1,
                    decision_type=self.DECISION_UPCOMING,
                    decision_source=self.SOURCE_GROUP_RULE,
                    rule_key=self._group_rule_key(group, next_rule, prior_doses + 1),
                    reason_code='group_upcoming',
                    message=f"{next_rule.vaccine_to_give.name} dose {prior_doses + 1} becomes eligible on {target_date.isoformat()} via {group.name}.",
                    group=group,
                    product=product,
                    target_date=target_date,
                ))
            return result

        rule = valid_rules[-1]
        vaccine_to_give = rule.vaccine_to_give
        product = self._product_for_vaccine(vaccine_to_give)
        standard_rule = ScheduleRule.objects.filter(
            vaccine=vaccine_to_give,
            dose_number=prior_doses + 1,
        ).first()

        if prior_doses == 0 and standard_rule:
            target_date = self.child.dob + timedelta(days=standard_rule.recommended_age_days)
        elif last_dose_date:
            interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
            age_floor = standard_rule.min_age_days if standard_rule else rule.min_age_days
            age_floor_date = self.child.dob + timedelta(days=age_floor)
            target_date = max(interval_date, age_floor_date)
        else:
            target_date = self.child.dob + timedelta(days=rule.min_age_days)

        dose_val = rule.dose_amount or (standard_rule.dose_amount if standard_rule else None)
        overdue_age = rule.max_age_days
        if standard_rule:
            overdue_age = standard_rule.overdue_age_days if standard_rule.overdue_age_days is not None else standard_rule.recommended_age_days

        overdue_date = self.child.dob + timedelta(days=overdue_age) if overdue_age is not None else target_date
        rule_key = self._group_rule_key(group, rule, prior_doses + 1)

        if self.evaluation_date > overdue_date:
            result['missing_doses'].append(self._build_decision_item(
                vaccine=vaccine_to_give,
                dose_amount=dose_val,
                dose_number=prior_doses + 1,
                decision_type=self.DECISION_MISSING,
                decision_source=self.SOURCE_GROUP_RULE,
                rule_key=rule_key,
                reason_code='group_missing',
                message=f"{vaccine_to_give.name} dose {prior_doses + 1} is overdue via {group.name}.",
                group=group,
                product=product,
            ))

        if self.evaluation_date >= target_date:
            result['due_today'].append(self._build_decision_item(
                vaccine=vaccine_to_give,
                dose_amount=dose_val,
                dose_number=prior_doses + 1,
                decision_type=self.DECISION_DUE,
                decision_source=self.SOURCE_GROUP_RULE,
                rule_key=rule_key,
                reason_code='group_due',
                message=f"{vaccine_to_give.name} dose {prior_doses + 1} is due today via {group.name}.",
                group=group,
                product=product,
            ))
        else:
            result['upcoming'].append(self._build_decision_item(
                vaccine=vaccine_to_give,
                dose_amount=dose_val,
                dose_number=prior_doses + 1,
                decision_type=self.DECISION_UPCOMING,
                decision_source=self.SOURCE_GROUP_RULE,
                rule_key=rule_key,
                reason_code='group_upcoming',
                message=f"{vaccine_to_give.name} dose {prior_doses + 1} becomes eligible on {target_date.isoformat()} via {group.name}.",
                group=group,
                product=product,
                target_date=target_date,
            ))

        return result









