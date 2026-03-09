import json
import os
from datetime import date
from .base import BaseVaccinationTestCase

class TestDynamicScenarios(BaseVaccinationTestCase):
    """
    Dynamically loads scenarios from scenarios.json and runs them
    against the vaccination engine.
    """

    @classmethod
    def generate_tests(cls):
        scenario_path = os.path.join(os.path.dirname(__file__), 'scenarios.json')
        if not os.path.exists(scenario_path):
            return

        with open(scenario_path, 'r', encoding='utf-8') as f:
            scenarios = json.load(f)

        for i, scenario in enumerate(scenarios):
            test_name = f"test_scenario_{i}_{scenario['name'].replace(' ', '_').replace(':', '').replace('(', '').replace(')', '').replace(',', '').lower()}"
            
            def create_test(s):
                def test(self):
                    child = self.make_child(s['name'], age_days=s['age_days'])
                    
                    # 1. Inject history chronologically
                    history_records = []
                    for entry in s.get('history', []):
                        vax_attr = entry['vax'].lower()
                        vax_obj = getattr(self, vax_attr, None)
                        if not vax_obj:
                            # Fallback for vaccines not directly on self (like Penta/DTC/Td/RR)
                            from vaccines.models import Vaccine
                            vax_obj = Vaccine.objects.filter(name__iexact=entry['vax']).first()
                        
                        if vax_obj:
                            rec = self.give_dose(child, vax_obj, days_ago=entry['days_ago'])
                            history_records.append(rec)
                        else:
                            self.fail(f"Vaccine {entry['vax']} not found in DB or test setup for scenario {s['name']}")

                    # 2. Evaluate
                    result = self.evaluate(child)
                    
                    # 3. Assert Expected Due
                    expected_due = s.get('expected_due', [])
                    actual_due = self.due_names(result)
                    for expected in expected_due:
                        self.assertIn(expected, actual_due, f"Fail: {expected} expected to be DUE in '{s['name']}'")
                    
                    # 4. Assert Expected Upcoming
                    expected_upcoming = s.get('expected_upcoming', [])
                    actual_upcoming = self.upcoming_names(result)
                    for expected in expected_upcoming:
                        self.assertIn(expected, actual_upcoming, f"Fail: {expected} expected to be UPCOMING in '{s['name']}'")

                    # 5. Assert Expected Missing
                    expected_missing = s.get('expected_missing', [])
                    actual_missing = self.missing_names(result)
                    for expected in expected_missing:
                        self.assertIn(expected, actual_missing, f"Fail: {expected} expected to be MISSING in '{s['name']}'")

                    # 6. Assert Expected Invalid Doses (Validation Checks)
                    expected_invalid = s.get('expected_invalid', [])
                    for inv in expected_invalid:
                        # Find the record by index in history
                        if inv['index'] < len(history_records):
                            rec = history_records[inv['index']]
                            rec.refresh_from_db()
                            self.assertTrue(rec.invalid_flag, f"Fail: Dose {inv['index']} ({inv['vax']}) should be INVALID in '{s['name']}'")
                            
                            # Reason mapping to internal codes
                            from patients.models import VaccinationRecord as VR
                            reason_map = {
                                "short_interval": VR.REASON_INTERVAL,
                                "too_early": VR.REASON_TOO_EARLY,
                                "too_late": VR.REASON_TOO_LATE,
                                "wrong_vaccine": VR.REASON_WRONG_VACCINE
                            }
                            expected_code = reason_map.get(inv['reason'])
                            self.assertEqual(rec.invalid_reason, expected_code, f"Fail: Wrong invalid reason for dose {inv['index']} in '{s['name']}'")
                        else:
                            self.fail(f"Invalid dose index {inv['index']} specified for scenario '{s['name']}'")

                return test

            setattr(cls, test_name, create_test(scenario))

# Trigger generation
TestDynamicScenarios.generate_tests()
