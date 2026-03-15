import os
import sys
import json
import django
from datetime import date

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from vaccines.models import (
    Vaccine, Product, Series, SeriesProduct, SeriesRule, 
    SeriesTransitionRule, DependencyRule, PolicyVersion,
    GlobalConstraintRule
)

def audit_policy(sync=False):
    # Absolute path to policy file relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    policy_path = os.path.join(os.path.dirname(script_dir), 'vaccines', 'policy_reference.json')
    if not os.path.exists(policy_path):
        print(f"Error: Policy file not found at {policy_path}")
        return

    with open(policy_path, 'r') as f:
        policy = json.load(f)

    active_version = PolicyVersion.get_active()
    print("\n" + "="*80)
    print(f"VACCINATION SERIES POLICY AUDIT (Active Version: {active_version.name if active_version else 'None'})")
    print("="*80)

    # 1. Audit Vaccines & Products
    print("\n[1] VACCINES & PRODUCTS")
    print("-" * 40)
    for v_data in policy['vaccines']:
        name = v_data['name']
        live = v_data['live']
        display_name = v_data.get('display_name', '')
        protects_against = v_data.get('protects_against', '')
        clinical_notes = v_data.get('clinical_notes', '')
        manufacturer = v_data.get('manufacturer')
        
        try:
            v_obj = Vaccine.objects.get(name=name)
            status = "MATCH" if v_obj.live == live else f"MISMATCH (Live DB: {v_obj.live}, Expected: {live})"
            
            # Check for metadata mismatches
            meta_diffs = []
            if v_obj.display_name != display_name: meta_diffs.append(f"display_name: DB='{v_obj.display_name}', Expected='{display_name}'")
            if v_obj.protects_against != protects_against: meta_diffs.append(f"protects_against: DB='{v_obj.protects_against}', Expected='{protects_against}'")
            if v_obj.clinical_notes != clinical_notes: meta_diffs.append(f"clinical_notes: DB='{v_obj.clinical_notes}', Expected='{clinical_notes}'")
            
            print(f"{name:15} | {status}")
            if meta_diffs:
                print(f"  -> METADATA MISMATCH:")
                for d in meta_diffs: print(f"     - {d}")

            if sync:
                changed = False
                if v_obj.live != live:
                    v_obj.live = live
                    changed = True
                if v_obj.display_name != display_name:
                    v_obj.display_name = display_name
                    changed = True
                if v_obj.protects_against != protects_against:
                    v_obj.protects_against = protects_against
                    changed = True
                if v_obj.clinical_notes != clinical_notes:
                    v_obj.clinical_notes = clinical_notes
                    changed = True
                
                if changed:
                    v_obj.save()
                    print(f"  -> FIXED: Updated Vaccine metadata/status")
            
            # Ensure Product exists
            p_obj, created = Product.objects.get_or_create(vaccine=v_obj)
            if created:
                print(f"  -> FIXED: Created Product for {name}")
            if manufacturer and p_obj.manufacturer != manufacturer:
                 print(f"  -> MISMATCH: Manufacturer DB={p_obj.manufacturer}, Expected={manufacturer}")
                 if sync:
                     p_obj.manufacturer = manufacturer
                     p_obj.save()

        except Vaccine.DoesNotExist:
            print(f"{name:15} | MISSING")
            if sync:
                v_obj = Vaccine.objects.create(
                    name=name, 
                    live=live,
                    display_name=display_name,
                    protects_against=protects_against,
                    clinical_notes=clinical_notes
                )
                Product.objects.create(vaccine=v_obj, manufacturer=manufacturer)
                print(f"  -> FIXED: Created Vaccine and Product for {name}")

    # 1b. Audit Compatibility (Pass 2)
    print("\n[1b] LIVE VACCINE COMPATIBILITY")
    print("-" * 40)
    for v_data in policy['vaccines']:
        if 'compatible_with' in v_data:
            v_obj = Vaccine.objects.get(name=v_data['name'])
            expected_compat = v_data['compatible_with']
            actual_compat = [v.name for v in v_obj.compatible_live_vaccines.all()]
            
            for compat_name in expected_compat:
                if compat_name not in actual_compat:
                    print(f"{v_data['name']} -> {compat_name} compat | MISSING")
                    if sync:
                        compat_v = Vaccine.objects.get(name=compat_name)
                        v_obj.compatible_live_vaccines.add(compat_v)
                        print(f"  -> FIXED: Linked compatibility")


    # 2. Audit Series
    print("\n[2] SERIES & SERIES RULES")
    print("-" * 40)
    for s_data in policy['series']:
        s_name = s_data['name']
        print(f"\nSeries: {s_name}")
        try:
            s_obj = Series.objects.get(name=s_name)
            # Check basic fields
            if s_obj.min_valid_interval_days != s_data.get('min_valid_interval_days', 28):
                print(f"  Interval mismatch: DB={s_obj.min_valid_interval_days}, Expected={s_data.get('min_valid_interval_days', 28)}")
                if sync: 
                    s_obj.min_valid_interval_days = s_data.get('min_valid_interval_days', 28)
                    s_obj.save()

            # Audit Products in Series
            expected_products = s_data.get('products', [])
            actual_products = [sp.product.vaccine.name for sp in s_obj.series_products.all()]
            for p_name in expected_products:
                if p_name not in actual_products:
                    print(f"  Product MISSING: {p_name}")
                    if sync:
                        p_obj = Product.objects.get(vaccine__name=p_name)
                        SeriesProduct.objects.create(series=s_obj, product=p_obj)
                        print(f"    -> FIXED: Added {p_name} to series")

            # Audit Rules
            for i, r_data in enumerate(s_data['rules']):
                # Finding a unique match for a rule is tricky, we'll use slot, prior_doses, and product
                p_obj = Product.objects.get(vaccine__name=r_data['product'])
                actual_rule = SeriesRule.objects.filter(
                    series=s_obj,
                    slot_number=r_data['slot_number'],
                    prior_valid_doses=r_data['prior_valid_doses'],
                    product=p_obj,
                    min_age_days=r_data['min_age_days']
                ).first()

                if not actual_rule:
                    print(f"  Rule S:{r_data['slot_number']} P:{r_data['prior_valid_doses']} V:{r_data['product']} | MISSING")
                    if sync:
                        SeriesRule.objects.create(series=s_obj, product=p_obj, **{k: v for k, v in r_data.items() if k != 'product'})
                        print(f"    -> FIXED: Created Rule")
                else:
                    diffs = []
                    for key, val in r_data.items():
                        if key == 'product': continue
                        actual_val = getattr(actual_rule, key)
                        if actual_val != val:
                            diffs.append(f"{key}: DB={actual_val}, Expected={val}")
                    
                    if diffs:
                        print(f"  Rule S:{r_data['slot_number']} P:{r_data['prior_valid_doses']} V:{r_data['product']} | MISMATCH")
                        for d in diffs: print(f"    - {d}")
                        if sync:
                            for key, val in r_data.items():
                                if key == 'product': continue
                                setattr(actual_rule, key, val)
                            actual_rule.save()
                            print(f"    -> FIXED: Updated Rule")

        except Series.DoesNotExist:
            print(f"{s_name:15} | MISSING")
            if sync:
                s_obj = Series.objects.create(name=s_name, min_valid_interval_days=s_data.get('min_valid_interval_days', 28))
                print(f"  -> FIXED: Created Series {s_name}. Rerun sync to add products/rules.")

    # 3. Transitions
    print("\n[3] TRANSITIONS")
    print("-" * 40)
    for t_data in policy.get('transitions', []):
        try:
            s_obj = Series.objects.get(name=t_data['series'])
            to_p = Product.objects.get(vaccine__name=t_data['to_product'])
            from_p = Product.objects.get(vaccine__name=t_data['from_product']) if t_data.get('from_product') else None
            
            actual_t = SeriesTransitionRule.objects.filter(
                series=s_obj,
                from_product=from_p,
                to_product=to_p,
                start_slot_number=t_data.get('start_slot_number')
            ).first()

            if not actual_t:
                print(f"  Transition {t_data['series']}: {t_data.get('from_product', 'Any')} -> {t_data['to_product']} | MISSING")
                if sync:
                    SeriesTransitionRule.objects.create(
                        series=s_obj,
                        from_product=from_p,
                        to_product=to_p,
                        start_slot_number=t_data.get('start_slot_number'),
                        end_slot_number=t_data.get('end_slot_number'),
                        allow_if_unavailable=t_data.get('allow_if_unavailable', False)
                    )
                    print(f"    -> FIXED: Created Transition")
        except (Series.DoesNotExist, Product.DoesNotExist):
            print(f"  Transition for {t_data.get('series')} | Series or Product missing")

    # 4. Dependencies
    print("\n[4] DEPENDENCIES")
    print("-" * 40)
    for d_data in policy.get('dependencies', []):
        try:
            dep_s = Series.objects.get(name=d_data['dependent_series'])
            anc_s = Series.objects.get(name=d_data['anchor_series'])
            
            actual_d = DependencyRule.objects.filter(
                dependent_series=dep_s,
                dependent_slot_number=d_data.get('dependent_slot_number'),
                anchor_series=anc_s,
                anchor_slot_number=d_data.get('anchor_slot_number'),
                min_offset_days=d_data['min_offset_days']
            ).first()

            if not actual_d:
                print(f"  Dependency: {d_data['dependent_series']} slot {d_data.get('dependent_slot_number')} after {d_data['anchor_series']} | MISSING")
                if sync:
                    DependencyRule.objects.create(
                        dependent_series=dep_s,
                        dependent_slot_number=d_data.get('dependent_slot_number'),
                        anchor_series=anc_s,
                        anchor_slot_number=d_data.get('anchor_slot_number'),
                        min_offset_days=d_data['min_offset_days'],
                        block_if_anchor_missing=d_data.get('block_if_anchor_missing', True),
                        is_coadmin=d_data.get('is_coadmin', False)
                    )
                    print(f"    -> FIXED: Created Dependency")
            else:
                expected_block = d_data.get('block_if_anchor_missing', True)
                expected_coadmin = d_data.get('is_coadmin', False)
                if actual_d.block_if_anchor_missing != expected_block or actual_d.is_coadmin != expected_coadmin:
                    print(f"  Dependency: {d_data['dependent_series']} slot {d_data.get('dependent_slot_number')} | MISMATCH (DB: Block={actual_d.block_if_anchor_missing}, CoAdmin={actual_d.is_coadmin})")
                    if sync:
                        actual_d.block_if_anchor_missing = expected_block
                        actual_d.is_coadmin = expected_coadmin
                        actual_d.save()
                        print(f"    -> FIXED: Updated Dependency Blocking/Co-admin")
        except Series.DoesNotExist:
             print(f"  Dependency | Series missing")

    # 5. Global Constraints
    print("\n[5] GLOBAL CONSTRAINTS")
    print("-" * 40)
    for c_data in policy.get('global_constraints', []):
        try:
            actual_c = GlobalConstraintRule.objects.filter(code=c_data['code']).first()
            if not actual_c:
                print(f"Constraint {c_data['name']} | MISSING")
                if sync:
                    GlobalConstraintRule.objects.create(**c_data)
                    print(f"  -> FIXED: Created Constraint")
            else:
                if actual_c.min_spacing_days != c_data['min_spacing_days']:
                    print(f"Constraint {c_data['name']} | MISMATCH (DB={actual_c.min_spacing_days}, Expected={c_data['min_spacing_days']})")
                    if sync:
                        actual_c.min_spacing_days = c_data['min_spacing_days']
                        actual_c.save()
                        print(f"  -> FIXED: Updated Constraint")
        except Exception as e:
            print(f"  Error auditing constraint {c_data.get('name')}: {e}")


    print("\nAudit Complete.")

if __name__ == "__main__":
    is_sync = "--sync" in sys.argv
    audit_policy(sync=is_sync)
