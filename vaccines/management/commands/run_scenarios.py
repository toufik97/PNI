import sys
from django.core.management.base import BaseCommand
from vaccines.test_models import TestScenario
from vaccines.scenario_runner import ScenarioRunner


class Command(BaseCommand):
    help = 'Run clinical test scenarios against the vaccination engine'

    def add_arguments(self, parser):
        parser.add_argument('--category', type=str, help='Filter by category (routine, catchup, validation, dependency, edge_case, regression)')
        parser.add_argument('--fail-fast', action='store_true', help='Stop on first failure')
        parser.add_argument('--name', type=str, help='Run a single scenario by name (partial match)')

    def handle(self, *args, **options):
        qs = TestScenario.objects.filter(active=True)

        if options.get('category'):
            qs = qs.filter(category=options['category'])
        if options.get('name'):
            qs = qs.filter(name__icontains=options['name'])

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No scenarios found.'))
            return

        self.stdout.write(f"\nRunning {total} scenario(s)...\n")
        self.stdout.write("=" * 60)

        passed = 0
        failed = 0
        errors = []

        for scenario in qs:
            result = ScenarioRunner.run(scenario)

            if result['passed']:
                passed += 1
                self.stdout.write(self.style.SUCCESS(f"  ✅ {scenario.name}"))
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  ❌ {scenario.name}"))
                if result.get('error'):
                    self.stdout.write(f"     ERROR: {result['error']}")
                for check in result.get('checks', []):
                    if not check['passed']:
                        self.stdout.write(f"     [{check['category']}]")
                        self.stdout.write(f"       Expected: {check['expected']}")
                        self.stdout.write(f"       Actual:   {check['actual']}")
                        if check.get('missing_from_actual'):
                            self.stdout.write(f"       Missing:  {check['missing_from_actual']}")
                errors.append(scenario.name)

                if options.get('fail_fast'):
                    self.stdout.write(self.style.WARNING('\n⛔ Stopped on first failure (--fail-fast).'))
                    break

        self.stdout.write("=" * 60)
        self.stdout.write(f"\n📊 Results: {passed} passed, {failed} failed out of {total}")

        if errors:
            self.stdout.write(self.style.ERROR(f"\nFailed scenarios:"))
            for name in errors:
                self.stdout.write(f"  - {name}")
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ All scenarios passed!'))
