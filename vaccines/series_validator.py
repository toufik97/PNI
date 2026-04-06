from typing import Dict, List

from patients.models import VaccinationRecord
from vaccines.models import Series
import logging

logger = logging.getLogger(__name__)


class SeriesHistoryValidator:
    def __init__(self, engine, history_by_vaccine: Dict[int, List[VaccinationRecord]]):
        self.engine = engine
        self.history_by_vaccine = history_by_vaccine

    def validate(self, series: Series) -> List[VaccinationRecord]:
        from patients.models import VaccinationRecord as VR
        logger.debug(f">> Validating history for series: {series.name}")

        series_vaccine_ids = {link.product.vaccine_id for link in series.series_products.all()}
        if not series_vaccine_ids:
            return []

        series_records = []
        for vaccine_id in series_vaccine_ids:
            if vaccine_id in self.history_by_vaccine:
                for record in self.history_by_vaccine[vaccine_id]:
                    if not record.invalid_flag:
                        series_records.append(record)
                    else:
                        logger.debug(f"Ignoring record {record.id} ({record.vaccine.name}) in {series.name} validation because it's marked invalid globally.")
        series_records.sort(key=lambda record: record.date_given)

        valid_records = []
        for record in series_records:
            age_at_dose = self.engine.history.age_at_dose(record)
            slot_number = len(valid_records) + 1
            product = self.engine._product_for_vaccine(record.vaccine)

            if valid_records:
                previous = valid_records[-1]
                days_since = (record.date_given - previous.date_given).days
                if days_since < series.min_valid_interval_days:
                    self.engine._flag_invalid(
                        record,
                        VR.REASON_INTERVAL,
                        f"Too soon: Must wait {series.min_valid_interval_days} days between {series.name} doses. Only {days_since} days elapsed since last dose.",
                        decision_source=self.engine.SOURCE_SERIES_RULE,
                        rule_key=self.engine._series_interval_rule_key(series, slot_number),
                        series=series,
                        product=product,
                        slot_number=slot_number,
                    )
                    continue

            candidates = self.engine._series_age_candidates(series, len(valid_records), age_at_dose)
            candidates = self.engine._filter_series_candidates(series, candidates, valid_records)

            if candidates:
                matching_candidates = [rule for rule in candidates if rule.product.vaccine_id == record.vaccine.id]
                if not matching_candidates:
                    age_months = round(age_at_dose / 30.44, 1)
                    allowed = ', '.join(sorted({rule.product.vaccine.name for rule in candidates}))
                    self.engine._flag_invalid(
                        record,
                        VR.REASON_WRONG_VACCINE,
                        f"Wrong vaccine: {record.vaccine.name} was given at {age_months} months, but allowed products for slot {slot_number} are {allowed}.",
                        decision_source=self.engine.SOURCE_SERIES_RULE,
                        rule_key=self.engine._series_candidate_rule_key(series, slot_number),
                        series=series,
                        product=product,
                        slot_number=slot_number,
                    )
                    continue
            else:
                future_rule = self.engine._first_series_future_rule(series, len(valid_records), valid_records, reference_age_days=age_at_dose)
                if future_rule:
                    age_months = round(age_at_dose / 30.44, 1)
                    min_months = round(future_rule.min_age_days / 30.44, 1)
                    self.engine._flag_invalid(
                        record,
                        VR.REASON_TOO_EARLY,
                        f"Too early: {record.vaccine.name} slot {future_rule.slot_number} requires min age {min_months} months. Child was {age_months} months old.",
                        decision_source=self.engine.SOURCE_SERIES_RULE,
                        rule_key=self.engine._series_rule_key(future_rule),
                        series=series,
                        product=product,
                        slot_number=future_rule.slot_number,
                    )
                    continue

                slot_rules = [r for r in series.rules.all() if r.slot_number == slot_number]
                too_late_rules = [rule for rule in slot_rules if rule.max_age_days is not None and age_at_dose > rule.max_age_days]
                if too_late_rules:
                    age_months = round(age_at_dose / 30.44, 1)
                    self.engine._flag_invalid(
                        record,
                        VR.REASON_TOO_LATE,
                        f"Too late: {record.vaccine.name} given at {age_months} months, but maximum age for this series slot is {round(max(r.max_age_days for r in too_late_rules)/30.44, 1)} months.",
                        decision_source=self.engine.SOURCE_SERIES_RULE,
                        rule_key=self.engine._series_candidate_rule_key(series, slot_number),
                        series=series,
                        product=product,
                        slot_number=slot_number,
                    )
                    continue

            # Dependency check
            _, blocking_constraints, _ = self.engine._apply_dependency_rules(
                series, slot_number, record.date_given, product=product
            )
            if blocking_constraints:
                reasons = [c['message'] for c in blocking_constraints]
                rule_key = blocking_constraints[0]['rule_key']
                
                self.engine._flag_invalid(
                    record,
                    VR.REASON_INTERVAL,
                    f"Dependency conflict: {record.vaccine.name} at slot {slot_number} violates dependency rules: {' '.join(reasons)}",
                    decision_source=self.engine.SOURCE_SERIES_RULE,
                    rule_key=rule_key,
                    series=series,
                    product=product,
                    slot_number=slot_number,
                )
                continue

            valid_records.append(record)

        return valid_records
