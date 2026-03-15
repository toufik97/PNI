from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from patients.models import Child, VaccinationRecord
from vaccines.availability import AvailabilityResolver
from vaccines.dependencies import DependencyEvaluator
from vaccines.global_constraints import LiveVaccineConstraintService
from vaccines.history_normalizer import HistoryNormalizer
from vaccines.models import GlobalConstraintRule, Product, Series, Vaccine
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
        active_series = self.policy_loader.get_active_series()
        self._validate_history(history_by_vaccine, active_series)

        due_today = []
        due_but_unavailable = []
        blocked = []
        missing_doses = []
        upcoming_details = []

        for series in active_series:
            self.series_history_cache[series.id] = self._validate_series_history(series, history_by_vaccine)

        for series in active_series:
            series_eval = self._recommend_series(series)
            due_today.extend(series_eval['due_today'])
            due_but_unavailable.extend(series_eval['due_but_unavailable'])
            blocked.extend(series_eval['blocked'])
            missing_doses.extend(series_eval['missing_doses'])
            upcoming_details.extend(series_eval['upcoming'])

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
        return self._deduplicate_by_vaccine(normalized)

    def _deduplicate_by_vaccine(self, items):
        seen = {}
        for item in items:
            vid = item['vaccine'].id
            if vid not in seen:
                item['contributing_series'] = [item.get('series_code')]
                # Preserve slot_number for internal reference, but replace dose_number with true physical dose count
                item['dose_number'] = self._true_dose_number(item['vaccine'])
                seen[vid] = item
            else:
                existing = seen[vid]
                if item.get('series_code') and item.get('series_code') not in existing.get('contributing_series', []):
                    existing.setdefault('contributing_series', []).append(item.get('series_code'))
                
                if 'target_date' in item:
                    if 'target_date' not in existing or item['target_date'] < existing['target_date']:
                        existing['target_date'] = item['target_date']
                
                if item.get('blocking_constraints'):
                    existing.setdefault('blocking_constraints', []).extend(item['blocking_constraints'])
        return list(seen.values())

    def _true_dose_number(self, vaccine: Vaccine) -> int:
        valid_count = sum(
            1 for r in self.records
            if r.vaccine_id == vaccine.id and not getattr(r, 'invalid_flag', False)
        )
        return valid_count + 1

    def _upcoming_tuple(self, item):
        return (item['vaccine'], item['target_date'], item['dose_number'])

    def _group_history(self) -> Dict[str, List[VaccinationRecord]]:
        return self.history.history_by_vaccine

    def _product_for_vaccine(self, vaccine: Vaccine):
        try:
            return vaccine.product_profile
        except Product.DoesNotExist:
            return None

    def _series_rule_key(self, rule) -> str:
        return f"series:{rule.series.code}:slot:{rule.slot_number}:product:{rule.product.code}"

    def _series_interval_rule_key(self, series: Series, slot_number: int) -> str:
        return f"series:{series.code}:slot:{slot_number}:interval"

    def _series_candidate_rule_key(self, series: Series, slot_number: int) -> str:
        return f"series:{series.code}:slot:{slot_number}:candidate-set"

    def _dependency_rule_key(self, dependency, slot_number: int) -> str:
        anchor_slot = dependency.anchor_slot_number or slot_number
        return f"dependency:{dependency.dependent_series.code}:{slot_number}:{dependency.anchor_series.code}:{anchor_slot}:{dependency.min_offset_days}"

    def _policy_version_code(self, series: Optional[Series] = None) -> str:
        if series and series.policy_version_id:
            return series.policy_version.code
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
        product: Optional[Product] = None,
        target_date: Optional[date] = None,
        blocking_constraints: Optional[List[Dict[str, Any]]] = None,
        warning_constraints: Optional[List[Dict[str, Any]]] = None,
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
            'product_code': product.code if product else None,
            'product_name': product.vaccine.name if product else vaccine.name,
            'blocking_constraints': list(blocking_constraints or []),
            'warning_constraints': list(warning_constraints or []),
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
            'product_code': product.code if product else None,
            'product_name': product.vaccine.name if product else record.vaccine.name,
            'blocking_constraints': [],
        })
    def _validate_history(
        self,
        history_by_vaccine: Dict[str, List[VaccinationRecord]],
        active_series: List[Series],
    ):
        self.global_constraints.validate_history(self.records, self.SOURCE_GLOBAL_CONSTRAINT)

    def _active_series_vaccine_ids(self, active_series: List[Series]) -> set[int]:
        return {
            link.product.vaccine_id
            for series in active_series
            for link in series.series_products.all()
        }
    def _active_series_vaccine_ids(self, active_series: List[Series]) -> set[int]:
        return {
            link.product.vaccine_id
            for series in active_series
            for link in series.series_products.all()
        }

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
            warning_constraints=state.get('warning_constraints'),
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
            warning_constraints=state.get('warning_constraints'),
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
            warning_constraints=state.get('warning_constraints'),
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

