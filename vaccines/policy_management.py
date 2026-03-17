import json
from django.db import transaction
from django.utils.text import slugify
from vaccines.models import (
    Vaccine, Product, Series, SeriesProduct, SeriesRule, 
    SeriesTransitionRule, DependencyRule, GlobalConstraintRule, PolicyVersion
)

class PolicyManager:
    @staticmethod
    def export_to_dict():
        data = {
            "vaccines": [],
            "series": [],
            "transitions": [],
            "dependencies": [],
            "global_constraints": []
        }

        # 1. Vaccines & Products
        for v in Vaccine.objects.all().order_by('name'):
            v_data = {
                "name": v.name,
                "live": v.live,
                "display_name": v.display_name,
                "protects_against": v.protects_against,
                "clinical_notes": v.clinical_notes,
                "compatible_with": [cv.name for cv in v.compatible_live_vaccines.all()]
            }
            if hasattr(v, 'product_profile'):
                v_data["manufacturer"] = v.product_profile.manufacturer
            data["vaccines"].append({k: v for k, v in v_data.items() if v is not None and v != ""})

        # 2. Series & Rules
        for s in Series.objects.all().order_by('name'):
            s_data = {
                "name": s.name,
                "min_valid_interval_days": s.min_valid_interval_days,
                "mixing_policy": s.mixing_policy,
                "products": [sp.product.vaccine.name for sp in s.series_products.all().order_by('priority')],
                "rules": []
            }
            for r in s.rules.all().order_by('slot_number', 'prior_valid_doses', 'category'):
                r_data = {
                    "slot_number": r.slot_number,
                    "prior_valid_doses": r.prior_valid_doses,
                    "category": r.category,
                    "min_age_days": r.min_age_days,
                    "recommended_age_days": r.recommended_age_days,
                    "overdue_age_days": r.overdue_age_days,
                    "max_age_days": r.max_age_days,
                    "min_interval_days": r.min_interval_days,
                    "product": r.product.vaccine.name,
                    "dose_amount": r.dose_amount,
                    "notes": r.notes
                }
                s_data["rules"].append({k: v for k, v in r_data.items() if v is not None and v != ""})
            data["series"].append(s_data)

        # 3. Transitions
        for t in SeriesTransitionRule.objects.all().order_by('series__name', 'start_slot_number'):
            t_data = {
                "series": t.series.name,
                "from_product": t.from_product.vaccine.name if t.from_product else None,
                "to_product": t.to_product.vaccine.name,
                "start_slot_number": t.start_slot_number,
                "end_slot_number": t.end_slot_number,
                "allow_if_unavailable": t.allow_if_unavailable,
                "active": t.active,
                "notes": t.notes
            }
            data["transitions"].append({k: v for k, v in t_data.items() if v is not None and v != ""})

        # 4. Dependencies
        for d in DependencyRule.objects.all().order_by('dependent_series__name', 'dependent_slot_number'):
            d_data = {
                "dependent_series": d.dependent_series.name,
                "dependent_slot_number": d.dependent_slot_number,
                "anchor_series": d.anchor_series.name,
                "anchor_slot_number": d.anchor_slot_number,
                "dependent_product": d.dependent_product.vaccine.name if d.dependent_product else None,
                "anchor_product": d.anchor_product.vaccine.name if d.anchor_product else None,
                "min_offset_days": d.min_offset_days,
                "block_if_anchor_missing": d.block_if_anchor_missing,
                "is_coadmin": d.is_coadmin,
                "active": d.active,
                "notes": d.notes
            }
            data["dependencies"].append({k: v for k, v in d_data.items() if v is not None and v != ""})

        # 5. Global Constraints
        for c in GlobalConstraintRule.objects.all().order_by('code'):
            c_data = {
                "code": c.code,
                "name": c.name,
                "constraint_type": c.constraint_type,
                "min_spacing_days": c.min_spacing_days,
                "active": c.active,
                "notes": c.notes
            }
            data["global_constraints"].append({k: v for k, v in c_data.items() if v is not None and v != ""})

        return data

    @staticmethod
    @transaction.atomic
    def import_from_dict(data, stdout=None):
        def log(msg):
            if stdout:
                stdout.write(msg)
            else:
                print(msg)

        # Ensure a policy version exists
        active_version = PolicyVersion.get_active()
        if not active_version:
            active_version = PolicyVersion.objects.create(name="Imported Policy", is_active=True)
            log(f"Created new Policy Version: {active_version.name}")

        # 1. Import Vaccines & Products
        log("\nImporting Vaccines & Products...")
        for v_data in data.get('vaccines', []):
            name = v_data['name']
            live = v_data.get('live', False)
            display_name = v_data.get('display_name', '')
            protects_against = v_data.get('protects_against', '')
            clinical_notes = v_data.get('clinical_notes', '')
            manufacturer = v_data.get('manufacturer')

            v_obj, created = Vaccine.objects.update_or_create(
                name=name,
                defaults={
                    'live': live,
                    'display_name': display_name,
                    'protects_against': protects_against,
                    'clinical_notes': clinical_notes,
                }
            )
            log(f"  {'Created' if created else 'Updated'} Vaccine: {name}")

            p_obj, created = Product.objects.update_or_create(
                vaccine=v_obj,
                defaults={
                    'manufacturer': manufacturer,
                    'active': True
                }
            )
            if created:
                log(f"  Created Product for {name}")

        # 1b. Linked Compatibility
        log("\nLinking Live Vaccine Compatibility...")
        for v_data in data.get('vaccines', []):
            if 'compatible_with' in v_data:
                v_obj = Vaccine.objects.get(name=v_data['name'])
                compat_names = v_data['compatible_with']
                compat_vaccines = Vaccine.objects.filter(name__in=compat_names)
                v_obj.compatible_live_vaccines.set(compat_vaccines)
                log(f"  Updated compatibility for {v_obj.name}")

        # 2. Import Series & Rules
        log("\nImporting Series & Rules...")
        for s_data in data.get('series', []):
            s_name = s_data['name']
            min_interval = s_data.get('min_valid_interval_days', 28)
            mixing = s_data.get('mixing_policy', 'age_rule')

            s_obj, created = Series.objects.update_or_create(
                name=s_name,
                defaults={
                    'min_valid_interval_days': min_interval,
                    'mixing_policy': mixing,
                    'policy_version': active_version,
                    'active': True
                }
            )
            log(f"  {'Created' if created else 'Updated'} Series: {s_name}")

            # Link Products to Series
            existing_sp = {sp.product.vaccine.name: sp for sp in s_obj.series_products.all()}
            for priority, p_name in enumerate(s_data.get('products', [])):
                p_obj = Product.objects.get(vaccine__name=p_name)
                SeriesProduct.objects.update_or_create(
                    series=s_obj, product=p_obj,
                    defaults={'priority': priority}
                )
                if p_name in existing_sp:
                    del existing_sp[p_name]
            
            # Remove products no longer in series
            for p_name, sp in existing_sp.items():
                sp.delete()
                log(f"  Removed {p_name} from series {s_name}")

            # Rules
            # For simplicity in this logic, we might want to clear rules and recreate if they've changed significantly,
            # but let's try to match them.
            current_rule_ids = set(s_obj.rules.values_list('id', flat=True))
            for r_data in s_data.get('rules', []):
                p_obj = Product.objects.get(vaccine__name=r_data['product'])
                rule_fields = {
                    'slot_number': r_data['slot_number'],
                    'prior_valid_doses': r_data['prior_valid_doses'],
                    'category': r_data.get('category', 'routine'),
                    'min_age_days': r_data['min_age_days'],
                    'recommended_age_days': r_data['recommended_age_days'],
                    'overdue_age_days': r_data.get('overdue_age_days'),
                    'max_age_days': r_data.get('max_age_days'),
                    'min_interval_days': r_data['min_interval_days'],
                    'dose_amount': r_data.get('dose_amount'),
                    'notes': r_data.get('notes')
                }
                
                # Match by slot, prior doses, product, and min_age
                rule_obj, created = SeriesRule.objects.update_or_create(
                    series=s_obj,
                    slot_number=rule_fields['slot_number'],
                    prior_valid_doses=rule_fields['prior_valid_doses'],
                    product=p_obj,
                    min_age_days=rule_fields['min_age_days'],
                    defaults=rule_fields
                )
                if rule_obj.id in current_rule_ids:
                    current_rule_ids.remove(rule_obj.id)
            
            # Remove old rules
            if current_rule_ids:
                SeriesRule.objects.filter(id__in=current_rule_ids).delete()
                log(f"  Removed {len(current_rule_ids)} obsolete rules from {s_name}")

        # 3. Transitions
        log("\nImporting Transitions...")
        SeriesTransitionRule.objects.all().delete() # Safer to reset transitions as they are small and highly relational
        for t_data in data.get('transitions', []):
            try:
                s_obj = Series.objects.get(name=t_data['series'])
                to_p = Product.objects.get(vaccine__name=t_data['to_product'])
                from_p = Product.objects.get(vaccine__name=t_data['from_product']) if t_data.get('from_product') else None
                
                SeriesTransitionRule.objects.create(
                    series=s_obj,
                    from_product=from_p,
                    to_product=to_p,
                    start_slot_number=t_data.get('start_slot_number'),
                    end_slot_number=t_data.get('end_slot_number'),
                    allow_if_unavailable=t_data.get('allow_if_unavailable', False),
                    active=t_data.get('active', True),
                    notes=t_data.get('notes')
                )
            except Exception as e:
                log(f"  Error creating transition: {e}")

        # 4. Dependencies
        log("\nImporting Dependencies...")
        # Since dependencies can have complex cycles/updates, we'll try to sync them
        existing_deps = {d.id: d for d in DependencyRule.objects.all()}
        for d_data in data.get('dependencies', []):
            try:
                dep_s = Series.objects.get(name=d_data['dependent_series'])
                anc_s = Series.objects.get(name=d_data['anchor_series'])
                dep_p = Product.objects.get(vaccine__name=d_data['dependent_product']) if d_data.get('dependent_product') else None
                anc_p = Product.objects.get(vaccine__name=d_data['anchor_product']) if d_data.get('anchor_product') else None

                dep_obj, created = DependencyRule.objects.update_or_create(
                    dependent_series=dep_s,
                    dependent_slot_number=d_data.get('dependent_slot_number'),
                    dependent_product=dep_p,
                    anchor_series=anc_s,
                    anchor_slot_number=d_data.get('anchor_slot_number'),
                    anchor_product=anc_p,
                    defaults={
                        'min_offset_days': d_data['min_offset_days'],
                        'block_if_anchor_missing': d_data.get('block_if_anchor_missing', True),
                        'is_coadmin': d_data.get('is_coadmin', False),
                        'active': d_data.get('active', True),
                        'notes': d_data.get('notes')
                    }
                )
                if dep_obj.id in existing_deps:
                    del existing_deps[dep_obj.id]
            except Exception as e:
                log(f"  Error creating dependency: {e}")
        
        for dep_id, dep_obj in existing_deps.items():
            dep_obj.delete()

        # 5. Global Constraints
        log("\nImporting Global Constraints...")
        for c_data in data.get('global_constraints', []):
            GlobalConstraintRule.objects.update_or_create(
                code=c_data['code'],
                defaults={
                    'name': c_data['name'],
                    'constraint_type': c_data['constraint_type'],
                    'min_spacing_days': c_data.get('min_spacing_days', 28),
                    'active': c_data.get('active', True),
                    'notes': c_data.get('notes'),
                    'policy_version': active_version
                }
            )

        log("\nImport Complete.")
