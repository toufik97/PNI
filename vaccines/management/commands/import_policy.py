import json
from django.core.management.base import BaseCommand
from vaccines.policy_management import PolicyManager

class Command(BaseCommand):
    help = 'Import vaccine policies from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('input_file', type=str, help='Path to the input JSON file')

    def handle(self, *args, **options):
        input_file = options['input_file']

        self.stdout.write(f"Importing policy from {input_file}...")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {input_file}"))
            return
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f"Error decoding JSON: {e}"))
            return

        PolicyManager.import_from_dict(data, stdout=self.stdout)
            
        self.stdout.write(self.style.SUCCESS(f"Successfully imported policy from {input_file}"))
