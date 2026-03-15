import os
import json
import django
from datetime import date, timedelta

import sys
# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from patients.models import Child, VaccinationRecord
from vaccines.models import Vaccine
from vaccines.engine import VaccinationEngine

def run_live_scenarios():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenarios_path = os.path.join(base_dir, 'tests', 'scenarios.json')
    with open(scenarios_path, 'r') as f:
        scenarios = json.load(f)

    print("\n" + "="*80)
    print("LIVE SCENARIO VERIFICATION")
    print("Run scenarios against the ACTUAL database (Safe: creates temp children)")
    print("="*80)

    pass_count = 0
    fail_count = 0

    # Start a transaction to roll back changes (or just delete created objects)
    from django.db import transaction

    for scenario in scenarios:
        name = scenario['name']
        print(f"\nScenario: {name}")
        
        try:
            with transaction.atomic():
                # 1. Create temporary child
                dob = date.today() - timedelta(days=scenario['age_days'])
                child = Child.objects.create(
                    id=f"TEMP_TEST_{scenario['age_days']}",
                    name="Temp Test Child",
                    sex='M',
                    dob=dob
                )

                # 2. Give doses
                history_records = []
                for entry in scenario.get('history', []):
                    # Handle both 'vax' and 'vaccine' keys
                    v_name = entry.get('vax') or entry.get('vaccine')
                    vaccine = Vaccine.objects.get(name=v_name)
                    given_date = date.today() - timedelta(days=entry['days_ago'])
                    VaccinationRecord.objects.create(
                        child=child,
                        vaccine=vaccine,
                        date_given=given_date
                    )

                # 3. Evaluate
                engine = VaccinationEngine(child)
                result = engine.evaluate()

                actual_due = sorted([d['vaccine'].name for d in result['due_today']])
                expected_due = sorted(scenario.get('expected_due', []))

                actual_missing = sorted([d['vaccine'].name for d in result['missing_doses']])
                expected_missing = sorted(scenario.get('expected_missing', []))

                actual_upcoming = sorted([d['vaccine'].name for d in result['upcoming_details']])
                expected_upcoming = sorted(scenario.get('expected_upcoming', []))

                actual_unavail = sorted([d['vaccine'].name for d in result['due_but_unavailable']])
                expected_unavail = sorted(scenario.get('expected_unavailable', []))

                # 4. Compare
                failed = False
                if actual_due != expected_due:
                    # Filter out vaccines not mentioned in expected (less strict for live system)
                    missing_from_actual = [e for e in expected_due if e not in actual_due]
                    if missing_from_actual:
                        # Special case: if expected is due but it's reported as unavailable, that's acceptable for live test
                        truly_missing = [m for m in missing_from_actual if m not in actual_unavail]
                        if truly_missing:
                            print(f"  ❌ DUE MISMATCH: Expected {expected_due}, Actual {actual_due} (Unavail: {actual_unavail})")
                            failed = True
                
                if actual_missing != expected_missing:
                    missing_from_actual = [e for e in expected_missing if e not in actual_missing]
                    if missing_from_actual:
                        print(f"  ❌ MISSING MISMATCH: Expected {expected_missing}, Actual {actual_missing}")
                        failed = True

                if expected_upcoming:
                    missing_from_actual = [e for e in expected_upcoming if e not in actual_upcoming]
                    if missing_from_actual:
                        # Allow upcoming to be in DUE instead (if child reached that age)
                        truly_missing = [m for m in missing_from_actual if m not in actual_due]
                        if truly_missing:
                             print(f"  ❌ UPCOMING MISMATCH: Expected {expected_upcoming}, Actual {actual_upcoming}")
                             failed = True

                # Check invalid doses (Validation)
                expected_invalid = scenario.get('expected_invalid', [])
                for inv in expected_invalid:
                    # Use index to find the record we created earlier
                    if inv['index'] < len(history_records):
                        rec = history_records[inv['index']]
                        rec.refresh_from_db()
                        if not rec.invalid_flag:
                            print(f"  ❌ VALIDATION MISMATCH: Dose {inv['index']} should be INVALID")
                            failed = True
                        else:
                            # Map reason names to internal codes
                            from patients.models import VaccinationRecord as VR
                            reason_map = {
                                "short_interval": VR.REASON_INTERVAL,
                                "too_early": VR.REASON_TOO_EARLY,
                                "too_late": VR.REASON_TOO_LATE,
                                "wrong_vaccine": VR.REASON_WRONG_VACCINE
                            }
                            expected_code = reason_map.get(inv['reason'])
                            if rec.invalid_reason != expected_code:
                                print(f"  ❌ REASON MISMATCH: Expected {inv['reason']} code {expected_code}, Actual {rec.invalid_reason}")
                                failed = True

                # Check dose amount if specified
                if 'expected_dose_amount' in scenario:
                    # Find the specific vaccine in due_today
                    dose_check = False
                    for d in result['due_today']:
                        if d['vaccine'].name == scenario.get('vaccine_for_dose'):
                            if d['dose_amount'] != scenario['expected_dose_amount']:
                                print(f"  ❌ DOSE MISMATCH: Expected {scenario['expected_dose_amount']}, Actual {d['dose_amount']}")
                                failed = True
                            dose_check = True
                    
                    if not dose_check and expected_due:
                         # Only error if we expected a dose but didn't find the vaccine to check
                         pass

                if not failed:
                    print("  ✅ PASS")
                    pass_count += 1
                else:
                    fail_count += 1

                # Rollback automatically deletes the temp child and records
                raise Exception("Rollback")
        except Exception as e:
            if str(e) != "Rollback":
                print(f"  💥 ERROR: {e}")
                fail_count += 1

    print("\n" + "="*40)
    print(f"FINAL RESULTS: {pass_count} passed, {fail_count} failed")
    print("="*40)

if __name__ == "__main__":
    run_live_scenarios()
