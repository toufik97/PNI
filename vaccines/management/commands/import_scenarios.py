"""
Management command to import legacy tests/scenarios.json into the TestScenario model.
"""
import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from vaccines.test_models import TestScenario


# Map scenario names to categories based on prefix/content
CATEGORY_MAP = {
    'DTP': 'routine',
    'RR': 'routine',
    'BCG': 'routine',
    'PCV': 'dependency',
    'Rotasil': 'routine',
    'VPO': 'dependency',
    'VPI': 'routine',
    'HB': 'routine',
    'Validation': 'validation',
    'Live Check': 'edge_case',
    'BUG-': 'regression',
}


class Command(BaseCommand):
    help = 'Import legacy tests/scenarios.json into the TestScenario database model'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, default=None, help='Path to scenarios JSON (default: tests/scenarios.json)')

    def handle(self, *args, **options):
        path = options.get('file') or os.path.join(settings.BASE_DIR, 'tests', 'scenarios.json')

        if not os.path.exists(path):
            self.stderr.write(self.style.ERROR(f'File not found: {path}'))
            return

        with open(path, 'r', encoding='utf-8') as f:
            scenarios = json.load(f)

        created = 0
        updated = 0

        for entry in scenarios:
            name = entry['name']
            category = 'routine'
            for prefix, cat in CATEGORY_MAP.items():
                if name.startswith(prefix):
                    category = cat
                    break

            defaults = {
                'description': entry.get('comment', ''),
                'category': category,
                'age_days': entry['age_days'],
                'history': entry.get('history', []),
                'expected_due': entry.get('expected_due', []),
                'expected_upcoming': entry.get('expected_upcoming', []),
                'expected_missing': entry.get('expected_missing', []),
                'expected_blocked': entry.get('expected_blocked', []),
                'expected_invalid': entry.get('expected_invalid', []),
            }

            _, was_created = TestScenario.objects.update_or_create(
                name=name, defaults=defaults,
            )

            if was_created:
                created += 1
                self.stdout.write(f'  + {name}')
            else:
                updated += 1
                self.stdout.write(f'  ~ {name}')

        self.stdout.write(self.style.SUCCESS(f'\nDone: {created} created, {updated} updated.'))
