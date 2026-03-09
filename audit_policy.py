import os
import sys
import json
import django
from datetime import timedelta

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from vaccines.models import Vaccine, ScheduleRule, CatchupRule, VaccineGroup, GroupRule

def audit_policy(sync=False):
    policy_path = os.path.join(os.path.dirname(__file__), 'vaccines', 'policy_reference.json')
    if not os.path.exists(policy_path):
        print(f"Error: Policy file not found at {policy_path}")
        return

    with open(policy_path, 'r') as f:
        policy = json.load(f)

    print("\n" + "="*80)
    print("VACCINATION POLICY AUDIT")
    print("="*80)

    # 1. Audit Vaccines
    print("\n[1] VACCINES")
    print("-" * 40)
    for v_data in policy['vaccines']:
        name = v_data['name']
        live = v_data['live']
        try:
            v_obj = Vaccine.objects.get(name=name)
            status = "MATCH" if v_obj.live == live else f"MISMATCH (DB: {v_obj.live}, Expected: {live})"
            print(f"{name:15} | {status}")
            if sync and v_obj.live != live:
                v_obj.live = live
                v_obj.save()
                print(f"  -> FIXED: Updated {name} live={live}")
        except Vaccine.DoesNotExist:
            print(f"{name:15} | MISSING")
            if sync:
                Vaccine.objects.create(name=name, live=live)
                print(f"  -> FIXED: Created {name}")

    # 2. Audit Schedule Rules
    print("\n[2] SCHEDULE RULES")
    print("-" * 40)
    for sr_data in policy['schedule_rules']:
        v_name = sr_data['vaccine']
        print(f"\nVaccine: {v_name}")
        try:
            v_obj = Vaccine.objects.get(name=v_name)
            for expected_rule in sr_data['rules']:
                dose_num = expected_rule['dose_number']
                actual_rule = ScheduleRule.objects.filter(vaccine=v_obj, dose_number=dose_num).first()
                
                if not actual_rule:
                    print(f"  Dose {dose_num:2} | MISSING")
                    if sync:
                        ScheduleRule.objects.create(vaccine=v_obj, **expected_rule)
                        print(f"    -> FIXED: Created Dose {dose_num}")
                else:
                    differences = []
                    for key, val in expected_rule.items():
                        actual_val = getattr(actual_rule, key)
                        if actual_val != val:
                            differences.append(f"{key}: DB={actual_val}, Expected={val}")
                    
                    if not differences:
                        print(f"  Dose {dose_num:2} | MATCH")
                    else:
                        print(f"  Dose {dose_num:2} | MISMATCH")
                        for diff in differences:
                            print(f"    - {diff}")
                        if sync:
                            for key, val in expected_rule.items():
                                setattr(actual_rule, key, val)
                            actual_rule.save()
                            print(f"    -> FIXED: Updated Dose {dose_num}")
        except Vaccine.DoesNotExist:
            print(f"  {v_name:15} | Vaccine itself missing, cannot audit rules.")

    # 3. Audit Catch-up Rules
    print("\n[3] CATCH-UP RULES")
    print("-" * 40)
    for cr_data in policy['catchup_rules']:
        v_name = cr_data['vaccine']
        print(f"\nVaccine: {v_name}")
        try:
            v_obj = Vaccine.objects.get(name=v_name)
            for expected_rule in cr_data['rules']:
                # Find matching rule by logic fields
                actual_rule = CatchupRule.objects.filter(
                    vaccine=v_obj,
                    min_age_days=expected_rule['min_age_days'],
                    max_age_days=expected_rule['max_age_days'],
                    prior_doses=expected_rule['prior_doses']
                ).first()

                if not actual_rule:
                    print(f"  Rule {expected_rule['min_age_days']}-{expected_rule['max_age_days']}d | MISSING")
                    if sync:
                        CatchupRule.objects.create(vaccine=v_obj, **expected_rule)
                        print(f"    -> FIXED: Created Rule")
                else:
                    differences = []
                    for key, val in expected_rule.items():
                        actual_val = getattr(actual_rule, key)
                        if actual_val != val:
                            differences.append(f"{key}: DB={actual_val}, Expected={val}")
                    
                    if not differences:
                        print(f"  Rule {expected_rule['min_age_days']}-{expected_rule['max_age_days']}d | MATCH")
                    else:
                        print(f"  Rule {expected_rule['min_age_days']}-{expected_rule['max_age_days']}d | MISMATCH")
                        for diff in differences:
                            print(f"    - {diff}")
                        if sync:
                            for key, val in expected_rule.items():
                                setattr(actual_rule, key, val)
                            actual_rule.save()
                            print(f"    -> FIXED: Updated Rule")
        except Vaccine.DoesNotExist:
            print(f"  {v_name:15} | Vaccine missing.")

    # 4. Audit Groups
    print("\n[4] VACCINE GROUPS")
    print("-" * 40)
    for g_data in policy['groups']:
        g_name = g_data['name']
        try:
            g_obj = VaccineGroup.objects.get(name=g_name)
            status = "MATCH" if g_obj.min_valid_interval_days == g_data['min_valid_interval_days'] else "MISMATCH"
            print(f"{g_name:15} | {status}")
            
            # Audit Group Rules
            for expected_rule in g_data['rules']:
                v_to_give = Vaccine.objects.get(name=expected_rule['vaccine_to_give'])
                actual_rule = GroupRule.objects.filter(
                    group=g_obj,
                    prior_doses=expected_rule['prior_doses'],
                    min_age_days=expected_rule['min_age_days']
                ).first()

                if not actual_rule:
                    print(f"  Rule P:{expected_rule['prior_doses']} A:{expected_rule['min_age_days']} | MISSING")
                    if sync:
                        params = {k: v for k, v in expected_rule.items() if k != 'vaccine_to_give'}
                        GroupRule.objects.create(group=g_obj, vaccine_to_give=v_to_give, **params)
                        print(f"    -> FIXED: Created Group Rule")
                else:
                    differences = []
                    if actual_rule.vaccine_to_give.id != v_to_give.id:
                        differences.append(f"vaccine: DB={actual_rule.vaccine_to_give.name}, Expected={v_to_give.name}")
                    
                    for key, val in expected_rule.items():
                        if key == 'vaccine_to_give': continue
                        actual_val = getattr(actual_rule, key)
                        if actual_val != val:
                            differences.append(f"{key}: DB={actual_val}, Expected={val}")

                    if not differences:
                        # print(f"  Rule P:{expected_rule['prior_doses']} A:{expected_rule['min_age_days']} | MATCH")
                        pass
                    else:
                        print(f"  Rule P:{expected_rule['prior_doses']} A:{expected_rule['min_age_days']} | MISMATCH")
                        for diff in differences:
                            print(f"    - {diff}")
                        if sync:
                            for key, val in expected_rule.items():
                                if key == 'vaccine_to_give':
                                    actual_rule.vaccine_to_give = v_to_give
                                else:
                                    setattr(actual_rule, key, val)
                            actual_rule.save()
                            print(f"    -> FIXED: Updated Group Rule")

        except VaccineGroup.DoesNotExist:
            print(f"{g_name:15} | MISSING")
            if sync:
                g_obj = VaccineGroup.objects.create(name=g_name, min_valid_interval_days=g_data['min_valid_interval_days'])
                v_objs = [Vaccine.objects.get(name=name) for name in g_data['vaccines']]
                g_obj.vaccines.set(v_objs)
                print(f"  -> FIXED: Created Group {g_name}")

    print("\nAudit Complete.")

if __name__ == "__main__":
    is_sync = "--sync" in sys.argv
    audit_policy(sync=is_sync)
    if is_sync:
        print("\nAll policies have been synchronized with the Source of Truth.")
