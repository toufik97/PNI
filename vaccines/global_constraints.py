from datetime import timedelta
from typing import List

from patients.models import VaccinationRecord


class LiveVaccineConstraintService:
    def __init__(
        self,
        *,
        global_live_rule_key,
        product_lookup,
        flag_invalid,
        build_live_deferral_item,
        spacing_days_resolver,
    ):
        self.global_live_rule_key = global_live_rule_key
        self.product_lookup = product_lookup
        self.flag_invalid = flag_invalid
        self.build_live_deferral_item = build_live_deferral_item
        self.spacing_days_resolver = spacing_days_resolver
        self._compat_cache = {}

    def _is_compatible(self, vaccine_a, vaccine_b_id):
        """Check if vaccine_a is compatible with vaccine_b using in-memory cache."""
        if vaccine_a.id not in self._compat_cache:
            self._compat_cache[vaccine_a.id] = set(vaccine_a.compatible_live_vaccines.values_list('id', flat=True))
        return vaccine_b_id in self._compat_cache[vaccine_a.id]

    def validate_history(self, records: List[VaccinationRecord], source_global_constraint: str):
        spacing_days = self.spacing_days_resolver()
        valid_live = []
        for record in records:
            if not record.vaccine.live or record.invalid_flag:
                continue

            if valid_live:
                previous = valid_live[-1]
                gap = (record.date_given - previous.date_given).days
                if gap < spacing_days:
                    is_compatible = self._is_compatible(record.vaccine, previous.vaccine.id)
                    if gap == 0 and is_compatible:
                        pass
                    else:
                        self.flag_invalid(
                            record,
                            VaccinationRecord.REASON_INTERVAL,
                            f"Live vax conflict: {record.vaccine.name} given {gap} days after live {previous.vaccine.name}. Standard protocol requires {spacing_days}-day gap.",
                            decision_source=source_global_constraint,
                            rule_key=self.global_live_rule_key,
                            product=self.product_lookup(record.vaccine),
                        )
                        continue

            valid_live.append(record)

    def defer_recommendations(self, records: List[VaccinationRecord], due_today_items, evaluation_date):
        spacing_days = self.spacing_days_resolver()
        recent_live_doses = [
            record for record in records
            if record.vaccine.live and not record.invalid_flag and (evaluation_date - record.date_given).days < spacing_days
        ]
        if not recent_live_doses:
            return due_today_items, []

        latest_live_date = max(record.date_given for record in recent_live_doses)
        safe_date = latest_live_date + timedelta(days=spacing_days)

        non_deferred_due = []
        deferred_upcoming = []
        for item in due_today_items:
            vaccine = item['vaccine']
            if vaccine.live:
                is_compatible = True
                for record in recent_live_doses:
                    if not self._is_compatible(vaccine, record.vaccine.id):
                        is_compatible = False
                        break

                if not is_compatible:
                    deferred_upcoming.append(self.build_live_deferral_item(item, safe_date, recent_live_doses))
                    continue

            non_deferred_due.append(item)

        return non_deferred_due, deferred_upcoming
