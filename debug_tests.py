"""
Runs the failing tests and prints full tracebacks.
Run: python debug_tests.py
"""
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'vaxapp.settings'
django.setup()

import unittest
from django.test.utils import get_runner
from django.conf import settings

TestRunner = get_runner(settings)
test_runner = TestRunner(verbosity=2, keepdb=False)

# Run only the two failing tests
failures = test_runner.run_tests([
    "tests.test_validation.TestWrongVaccineValidation",
    "tests.test_dtp_group_rules.TestDTPFiveDoses",
])
print(f"\nTotal failures: {failures}")
