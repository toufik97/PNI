"""
ScenarioRunner — Executes a TestScenario against the live vaccination engine
inside a rolled-back transaction so no database records persist.
"""
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone

from patients.models import Child, VaccinationRecord
from vaccines.models import Vaccine
from vaccines.engine import VaccinationEngine


class ScenarioRunner:
    """Run a TestScenario against the vaccination engine and compare results."""

    @staticmethod
    def run(scenario):
        """
        Execute a scenario and return a structured result dict.
        Uses a savepoint inside an atomic block so all temp records are rolled back.
        """
        with transaction.atomic():
            sid = transaction.savepoint()
            try:
                result = ScenarioRunner._execute(scenario)
            finally:
                transaction.savepoint_rollback(sid)

        # Update the scenario record (outside the rolled-back savepoint)
        scenario.last_status = 'pass' if result['passed'] else 'fail'
        scenario.last_result = result
        scenario.last_run_at = timezone.now()
        scenario.save(update_fields=['last_status', 'last_result', 'last_run_at'])

        return result

    @staticmethod
    def _execute(scenario):
        """Core execution: create child, inject history, evaluate, compare."""
        # Create virtual child
        child_id = f"__scenario_{scenario.pk}_{timezone.now().timestamp()}"
        dob = date.today() - timedelta(days=scenario.age_days)
        child = Child.objects.create(
            id=child_id, name=f"[Test] {scenario.name}", sex='M', dob=dob
        )

        # Inject vaccination history
        history_records = []
        vaccine_cache = {}
        for entry in scenario.history:
            vax_name = entry['vax']
            if vax_name not in vaccine_cache:
                vax_obj = Vaccine.objects.filter(name__iexact=vax_name).first()
                if not vax_obj:
                    return {
                        'passed': False,
                        'error': f"Vaccine '{vax_name}' not found in database.",
                        'checks': [],
                    }
                vaccine_cache[vax_name] = vax_obj

            rec = VaccinationRecord.objects.create(
                child=child,
                vaccine=vaccine_cache[vax_name],
                date_given=date.today() - timedelta(days=entry.get('days_ago', 0)),
                administered_elsewhere=entry.get('administered_elsewhere', False),
            )
            history_records.append(rec)

        # Run engine
        engine = VaccinationEngine(child, evaluation_date=date.today())
        engine_result = engine.evaluate()

        # Extract actuals with dose amounts
        def _fmt(item):
            if not item: return ""
            # Most items are dicts from _build_decision_item
            if isinstance(item, dict):
                vax = item.get('vaccine')
                base = vax.name if vax else "Unknown"
                if item.get('dose_amount'):
                    return f"{base} ({item['dose_amount']})"
                return base
            # Fallback for Vaccine objects
            if hasattr(item, 'name'):
                return item.name
            return str(item)

        due_list = engine_result.get('due_today', []) + engine_result.get('due_but_unavailable', [])
        actual_due = sorted([_fmt(d) for d in due_list])
        actual_upcoming = sorted([_fmt(d) for d in engine_result.get('upcoming_details', [])])
        actual_missing = sorted([_fmt(d) for d in engine_result.get('missing_doses', [])])
        actual_blocked = sorted([_fmt(d) for d in engine_result.get('blocked', [])])

        # Build check results
        checks = []

        # Build check results using smart matching
        checks = []

        def run_list_check(category, expected, actual):
            if not expected: return
            exp_sorted = sorted(expected)
            # Find items from the expected list that aren't found in actual results
            # A match counts if it's exact OR if the actual result starts with the name + dose brackets
            missing = [
                e for e in exp_sorted 
                if not any(a == e or a.startswith(f"{e} (") for a in actual)
            ]
            passed = (len(missing) == 0)
            
            checks.append({
                'category': category,
                'expected': exp_sorted,
                'actual': actual,
                'passed': passed,
                'missing_from_actual': missing,
            })

        run_list_check('Due Today', scenario.expected_due, actual_due)
        run_list_check('Upcoming', scenario.expected_upcoming, actual_upcoming)
        run_list_check('Missing', scenario.expected_missing, actual_missing)
        run_list_check('Blocked', scenario.expected_blocked, actual_blocked)

        # Check INVALID doses
        if scenario.expected_invalid:
            # Build a lookup from record ID to invalid info from the engine result
            invalid_by_record_id = {
                entry['record_id']: entry
                for entry in engine_result.get('invalid_history', [])
            }
            for inv_spec in scenario.expected_invalid:
                idx = inv_spec.get('index', -1)
                expected_reason = inv_spec.get('reason', '')
                vax_name = inv_spec.get('vax', '')

                if 0 <= idx < len(history_records):
                    rec = history_records[idx]
                    reason_map = {
                        'short_interval': VaccinationRecord.REASON_INTERVAL,
                        'too_early': VaccinationRecord.REASON_TOO_EARLY,
                        'too_late': VaccinationRecord.REASON_TOO_LATE,
                        'wrong_vaccine': VaccinationRecord.REASON_WRONG_VACCINE,
                    }
                    inv_entry = invalid_by_record_id.get(rec.id)
                    actual_invalid = inv_entry is not None
                    actual_reason = inv_entry['reason_code'] if inv_entry else None
                    expected_code = reason_map.get(expected_reason, expected_reason)

                    flag_match = actual_invalid is True
                    reason_match = actual_reason == expected_code

                    checks.append({
                        'category': f'Invalid Dose #{idx} ({vax_name})',
                        'expected': [f"invalid=True, reason={expected_reason}"],
                        'actual': [f"invalid={actual_invalid}, reason={actual_reason}"],
                        'passed': flag_match and reason_match,
                        'extra': [],
                        'missing_from_actual': [] if (flag_match and reason_match) else [f"Expected {expected_reason}"],
                    })
                else:
                    checks.append({
                        'category': f'Invalid Dose #{idx} ({vax_name})',
                        'expected': [f"invalid=True, reason={expected_reason}"],
                        'actual': ['Index out of range'],
                        'passed': False,
                        'extra': [],
                        'missing_from_actual': ['Record not found'],
                    })


        overall = all(c['passed'] for c in checks) if checks else True

        return {
            'passed': overall,
            'error': None,
            'checks': checks,
            'actual_summary': {
                'due': actual_due,
                'upcoming': actual_upcoming,
                'missing': actual_missing,
                'blocked': actual_blocked,
            },
        }

    @staticmethod
    def run_all(queryset=None):
        """Run all active scenarios and return aggregate results."""
        from .test_models import TestScenario

        if queryset is None:
            queryset = TestScenario.objects.filter(active=True)

        results = []
        for scenario in queryset:
            result = ScenarioRunner.run(scenario)
            results.append({
                'scenario': scenario,
                'result': result,
            })

        passed = sum(1 for r in results if r['result']['passed'])
        failed = sum(1 for r in results if not r['result']['passed'])

        return {
            'total': len(results),
            'passed': passed,
            'failed': failed,
            'details': results,
        }



