from datetime import timedelta


class DependencyEvaluator:
    def __init__(self, *, series_history_cache, dependency_rule_key_builder):
        self.series_history_cache = series_history_cache
        self.dependency_rule_key_builder = dependency_rule_key_builder

    def apply(self, series, slot_number, target_date, product=None):
        blocking_constraints = []
        warning_constraints = []
        recommendation_target = target_date

        for dependency in series.dependency_rules.all():
            if not dependency.active:
                continue
            if dependency.dependent_slot_number and dependency.dependent_slot_number != slot_number:
                continue
            
            # If a specific product is required for this dependency, check if it matches
            if dependency.dependent_product_id:
                if not product or dependency.dependent_product_id != product.id:
                    continue

            anchor_history = self.series_history_cache.get(dependency.anchor_series_id, [])
            
            def process_anchor(anc_record):
                nonlocal recommendation_target
                required_date = anc_record.date_given + timedelta(days=dependency.min_offset_days)
                recommendation_target = max(recommendation_target, required_date)
                
                if target_date < required_date:
                    detail = {
                        'rule_key': self.dependency_rule_key_builder(dependency, slot_number),
                        'reason_code': 'dependency_interval_conflict',
                        'message': f"Insufficient gap from {dependency.anchor_series.name} (need to wait until {required_date}).",
                    }
                    if dependency.is_coadmin or not dependency.block_if_anchor_missing:
                        warning_constraints.append(detail)
                    else:
                        blocking_constraints.append(detail)

            if dependency.anchor_slot_number == 0:
                # Check ALL doses in the anchor series history
                for anchor_record in anchor_history:
                    # safety: skip anchor doses given AFTER the current record being evaluated
                    if anchor_record.date_given > target_date:
                        continue
                    
                    if dependency.anchor_product_id:
                        try:
                            if anchor_record.vaccine.product_profile.id != dependency.anchor_product_id:
                                continue
                        except:
                            continue
                    process_anchor(anchor_record)
                continue

            anchor_slot = dependency.anchor_slot_number or slot_number
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
            if dependency.anchor_product_id:
                try:
                    if anchor_record.vaccine.product_profile.id != dependency.anchor_product_id:
                        continue
                except:
                    continue
            process_anchor(anchor_record)

        return recommendation_target, blocking_constraints, warning_constraints
