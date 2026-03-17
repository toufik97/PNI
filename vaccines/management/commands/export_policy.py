import json
from django.core.management.base import BaseCommand
from vaccines.policy_management import PolicyManager

class Command(BaseCommand):
    help = 'Export all vaccine policies to a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('output_file', type=str, help='Path to the output JSON file')
        parser.add_argument('--indent', type=int, default=4, help='Indentation for JSON output')

    def handle(self, *args, **options):
        output_file = options['output_file']
        indent = options['indent']

        self.stdout.write(f"Exporting policy to {output_file}...")
        
        data = PolicyManager.export_to_dict()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            
        self.stdout.write(self.style.SUCCESS(f"Successfully exported policy to {output_file}"))
