from datetime import timedelta
from typing import List, Optional

from patients.models import VaccinationRecord
from vaccines.models import Series


class SeriesRecommender:
    def __init__(
        self,
        *,
        child,
        evaluation_date,
        age_days,
        availability,
        dependencies,
        series_history_cache,
        state_to_due_item,
        state_to_missing_item,
        state_to_upcoming_item,
        state_to_blocked_item,
    ):
        self.child = child
        self.evaluation_date = evaluation_date
        self.age_days = age_days
        self.availability = availability
        self.dependencies = dependencies
        self.series_history_cache = series_history_cache
        self.state_to_due_item = state_to_due_item
        self.state_to_missing_item = state_to_missing_item
        self.state_to_upcoming_item = state_to_upcoming_item
        self.state_to_blocked_item = state_to_blocked_item

    def recommend(self, series: Series):
        result = {
            'due_today': [],
            'due_but_unavailable': [],
            'blocked': [],
            'missing_doses': [],
            'upcoming': [],
        }

        valid_records = self.series_history_cache.get(series.id, [])
        prior_doses = len(valid_records)
        last_dose_date = valid_records[-1].date_given if valid_records else None

        current_candidates = self.filter_series_candidates(
            series,
            self.series_age_candidates(series, prior_doses, self.age_days),
            valid_records,
        )
        candidate_states = [
            self.build_series_candidate_state(series, valid_records, last_dose_date, rule)
            for rule in current_candidates
        ]
        candidate_states = [state for state in candidate_states if state is not None]

        # If all candidates for the current age bracket are unavailable, 
        # consider the next available future rule as a candidate. 
        # This allows switching to an alternative (like Primovax) that might only be valid in a few days.
        if candidate_states and not any(s['is_available'] for s in candidate_states):
            future_rule = self.first_series_future_rule(series, prior_doses, valid_records)
            if future_rule:
                candidate_states.append(self.build_series_candidate_state(series, valid_records, last_dose_date, future_rule, future=True))

        if candidate_states:
            due_states = [
                state for state in candidate_states
                if not state['blocking_constraints'] and self.evaluation_date >= state['target_date']
            ]
            if due_states:
                chosen_due_state = self.availability.choose_due_state(series, valid_records, due_states)
                if chosen_due_state['is_available']:
                    result['due_today'].append(self.state_to_due_item(series, chosen_due_state))
                    if self.evaluation_date > chosen_due_state['overdue_date']:
                        result['missing_doses'].append(self.state_to_missing_item(series, chosen_due_state))
                    return result
                else:
                    result['due_but_unavailable'].append(self.state_to_due_item(series, chosen_due_state, unavailable=True))
                    if self.evaluation_date > chosen_due_state['overdue_date']:
                        result['missing_doses'].append(self.state_to_missing_item(series, chosen_due_state))
                    # Do NOT return here, so we can check for available upcoming alternatives
            
            upcoming_states = [
                state for state in candidate_states
                if not state['blocking_constraints'] and self.evaluation_date < state['target_date']
            ]
            if upcoming_states:
                chosen_upcoming = self.availability.choose_upcoming_state(series, valid_records, upcoming_states)
                result['upcoming'].append(self.state_to_upcoming_item(series, chosen_upcoming))
                return result

            blocked_states = [state for state in candidate_states if state['blocking_constraints']]
            if blocked_states:
                chosen_blocked = self.availability.choose_preferred_state(series, valid_records, blocked_states)
                result['blocked'].append(self.state_to_blocked_item(series, chosen_blocked))
                return result

        future_rule = self.first_series_future_rule(series, prior_doses, valid_records)
        if future_rule:
            future_state = self.build_series_candidate_state(series, valid_records, last_dose_date, future_rule, future=True)
            if future_state['blocking_constraints']:
                result['blocked'].append(self.state_to_blocked_item(series, future_state))
            else:
                result['upcoming'].append(self.state_to_upcoming_item(series, future_state))

        return result

    def series_age_candidates(self, series: Series, prior_doses: int, age_days: int):
        candidates = [
            rule for rule in series.rules.all()
            if rule.prior_valid_doses == prior_doses and rule.min_age_days <= age_days
        ]
        return [rule for rule in candidates if rule.max_age_days is None or age_days <= rule.max_age_days]

    def first_series_future_rule(
        self,
        series: Series,
        prior_doses: int,
        valid_records: List[VaccinationRecord],
        reference_age_days: Optional[int] = None,
    ):
        age_days = self.age_days if reference_age_days is None else reference_age_days
        future_candidates = [
            rule for rule in series.rules.all()
            if rule.prior_valid_doses == prior_doses and rule.min_age_days > age_days
        ]
        filtered = self.filter_series_candidates(series, future_candidates, valid_records)
        if not filtered:
            return None
        available_filtered = [r for r in filtered if self.availability.is_product_available(r.product)]
        if available_filtered:
            filtered = available_filtered

        return sorted(
            filtered,
            key=lambda rule: (
                rule.min_age_days,
                self.availability.series_product_priority(series, rule.product_id),
                rule.product.vaccine.name,
            ),
        )[0]

    def filter_series_candidates(self, series: Series, candidates, valid_records: List[VaccinationRecord]):
        filtered = list(candidates)
        if not valid_records:
            return filtered

        transition_rules = list(
            series.transition_rules.filter(active=True).select_related('from_product__vaccine', 'to_product__vaccine')
        )
        if transition_rules:
            return [
                rule for rule in filtered
                if self.transition_allows_product(rule, valid_records, transition_rules)
            ]

        if series.mixing_policy == Series.MIXING_STRICT:
            last_vaccine_id = valid_records[-1].vaccine_id
            return [rule for rule in filtered if rule.product.vaccine_id == last_vaccine_id]

        return filtered

    def transition_allows_product(self, rule, valid_records: List[VaccinationRecord], transition_rules):
        last_vaccine_id = valid_records[-1].vaccine_id
        if rule.product.vaccine_id == last_vaccine_id:
            return True

        slot_number = rule.slot_number
        matching_rules = [
            transition_rule for transition_rule in transition_rules
            if transition_rule.to_product_id == rule.product_id
            and (transition_rule.from_product_id is None or transition_rule.from_product.vaccine_id == last_vaccine_id)
            and (transition_rule.start_slot_number is None or slot_number >= transition_rule.start_slot_number)
            and (transition_rule.end_slot_number is None or slot_number <= transition_rule.end_slot_number)
        ]
        if not matching_rules:
            return False

        for transition_rule in matching_rules:
            if not transition_rule.allow_if_unavailable:
                return True
            if transition_rule.from_product_id and not self.availability.is_product_available(transition_rule.from_product):
                return True

        return False

    def build_series_candidate_state(
        self,
        series: Series,
        valid_records: List[VaccinationRecord],
        last_dose_date,
        rule,
        future: bool = False,
    ):
        # Baseline the target on the recommended age for the child
        target_date = self.child.dob + timedelta(days=rule.recommended_age_days)

        # But we must respect the minimum interval and minimum age floors
        if last_dose_date:
            interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
            target_date = max(target_date, interval_date)
        
        # Absolute safety floor: the minimum age
        age_floor_date = self.child.dob + timedelta(days=rule.min_age_days)
        target_date = max(target_date, age_floor_date)

        overdue_age = rule.overdue_age_days if rule.overdue_age_days is not None else rule.recommended_age_days
        overdue_date = self.child.dob + timedelta(days=overdue_age)
        target_date, blocking_constraints, warning_constraints = self.dependencies.apply(
            series, rule.slot_number, target_date, product=rule.product
        )
        if blocking_constraints:
            overdue_date = max(overdue_date, target_date)

        return {
            'rule': rule,
            'target_date': target_date,
            'overdue_date': overdue_date,
            'blocking_constraints': blocking_constraints,
            'warning_constraints': warning_constraints,
            'is_available': self.availability.is_product_available(rule.product),
            'last_product_match': bool(valid_records and valid_records[-1].vaccine_id == rule.product.vaccine_id),
            'priority': self.availability.series_product_priority(series, rule.product_id),
        }

