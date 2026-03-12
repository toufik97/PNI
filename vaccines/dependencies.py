from datetime import timedelta


class DependencyEvaluator:
    def __init__(self, *, series_history_cache, dependency_rule_key_builder):
        self.series_history_cache = series_history_cache
        self.dependency_rule_key_builder = dependency_rule_key_builder

    def apply(self, series, slot_number, target_date):
        blocking_constraints = []
        adjusted_target = target_date

        for dependency in series.dependency_rules.all():
            if not dependency.active:
                continue
            if dependency.dependent_slot_number and dependency.dependent_slot_number != slot_number:
                continue

            anchor_slot = dependency.anchor_slot_number or slot_number
            anchor_history = self.series_history_cache.get(dependency.anchor_series_id, [])
            if len(anchor_history) < anchor_slot:
                if dependency.block_if_anchor_missing:
                    blocking_constraints.append({
                        'rule_key': self.dependency_rule_key_builder(dependency, slot_number),
                        'reason_code': 'dependency_anchor_missing',
                        'message': f"Requires {dependency.anchor_series.name} slot {anchor_slot} before {series.name} slot {slot_number}.",
                    })
                continue

            anchor_record = anchor_history[anchor_slot - 1]
            adjusted_target = max(
                adjusted_target,
                anchor_record.date_given + timedelta(days=dependency.min_offset_days),
            )

        return adjusted_target, blocking_constraints
