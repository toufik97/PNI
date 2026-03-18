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
        Uses a savepoint so all temp records are rolled back.
        """
        sid = transaction.savepoint()
        try:
            result = ScenarioRunner._execute(scenario)
        finally:
            transaction.savepoint_rollback(sid)

        # Update the scenario record
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

        # Extract actuals
        actual_due = sorted([d['vaccine'].name for d in engine_result.get('due_today', [])])
        actual_upcoming = sorted([item[0].name for item in engine_result.get('upcoming', [])])
        actual_missing = sorted([d['vaccine'].name for d in engine_result.get('missing_doses', [])])
        actual_blocked = sorted([b['vaccine'].name for b in engine_result.get('blocked', [])])

        # Build check results
        checks = []

        # Check DUE
        if scenario.expected_due:
            expected = sorted(scenario.expected_due)
            match = _list_match(expected, actual_due)
            checks.append({
                'category': 'Due Today',
                'expected': expected,
                'actual': actual_due,
                'passed': match,
                'extra': sorted(set(actual_due) - set(expected)),
                'missing_from_actual': sorted(set(expected) - set(actual_due)),
            })

        # Check UPCOMING
        if scenario.expected_upcoming:
            expected = sorted(scenario.expected_upcoming)
            match = all(e in actual_upcoming for e in expected)
            checks.append({
                'category': 'Upcoming',
                'expected': expected,
                'actual': actual_upcoming,
                'passed': match,
                'extra': [],
                'missing_from_actual': sorted(set(expected) - set(actual_upcoming)),
            })

        # Check MISSING
        if scenario.expected_missing:
            expected = sorted(scenario.expected_missing)
            match = all(e in actual_missing for e in expected)
            checks.append({
                'category': 'Missing',
                'expected': expected,
                'actual': actual_missing,
                'passed': match,
                'extra': [],
                'missing_from_actual': sorted(set(expected) - set(actual_missing)),
            })

        # Check BLOCKED
        if scenario.expected_blocked:
            expected = sorted(scenario.expected_blocked)
            match = all(e in actual_blocked for e in expected)
            checks.append({
                'category': 'Blocked',
                'expected': expected,
                'actual': actual_blocked,
                'passed': match,
                'extra': [],
                'missing_from_actual': sorted(set(expected) - set(actual_blocked)),
            })

        # Check INVALID doses
        if scenario.expected_invalid:
            for inv_spec in scenario.expected_invalid:
                idx = inv_spec.get('index', -1)
                expected_reason = inv_spec.get('reason', '')
                vax_name = inv_spec.get('vax', '')

                if 0 <= idx < len(history_records):
                    rec = history_records[idx]
                    rec.refresh_from_db()
                    reason_map = {
                        'short_interval': VaccinationRecord.REASON_INTERVAL,
                        'too_early': VaccinationRecord.REASON_TOO_EARLY,
                        'too_late': VaccinationRecord.REASON_TOO_LATE,
                        'wrong_vaccine': VaccinationRecord.REASON_WRONG_VACCINE,
                    }
                    actual_invalid = rec.invalid_flag
                    actual_reason = rec.invalid_reason
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


def _list_match(expected, actual):
    """Check if two sorted lists contain the same elements."""
    return expected == actual
