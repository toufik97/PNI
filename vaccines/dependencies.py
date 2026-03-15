from datetime import timedelta


class DependencyEvaluator:
    def __init__(self, *, series_history_cache, dependency_rule_key_builder):
        self.series_history_cache = series_history_cache
        self.dependency_rule_key_builder = dependency_rule_key_builder

    def apply(self, series, slot_number, target_date, product=None):
        blocking_constraints = []
        warning_constraints = []
        adjusted_target = target_date

        for dependency in series.dependency_rules.all():
            if not dependency.active:
                continue
            if dependency.dependent_slot_number and dependency.dependent_slot_number != slot_number:
                continue
            
            # If a specific product is required for this dependency, check if it matches
            if dependency.dependent_product_id and product and dependency.dependent_product_id != product.id:
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
                elif dependency.is_coadmin:
                    warning_constraints.append({
                        'rule_key': self.dependency_rule_key_builder(dependency, slot_number),
                        'reason_code': 'coadmin_anchor_missing',
                        'message': f"Standard practice: Administer with {dependency.anchor_series.name} (Dose {anchor_slot}).",
                    })
                continue

            anchor_record = anchor_history[anchor_slot - 1]
            
            # If a specific anchor product is required (e.g. only space from Penta, not standalone HB)
            if dependency.anchor_product_id:
                # We check the vaccine's product profile to find the product ID
                try:
                    anchor_product_profile = anchor_record.vaccine.product_profile
                    if anchor_product_profile.id != dependency.anchor_product_id:
                        continue
                except Exception:
                    # If vaccine has no product profile or doesn't match, we skip this dependency rule for this anchor record
                    continue

            adjusted_target = max(
                adjusted_target,
                anchor_record.date_given + timedelta(days=dependency.min_offset_days),
            )

        return adjusted_target, blocking_constraints, warning_constraints

