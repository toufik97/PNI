import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from patients.models import Child
from vaccines.engine import VaccinationEngine

def run_tests():
    children = Child.objects.all()
    print("--- VACCINATION ENGINE TEST RESULTS ---")
    for child in children:
        print(f"\nChild: {child.name} (ID: {child.id}, Age: {(date.today() - child.dob).days} days)")
        engine = VaccinationEngine(child)
        res = engine.evaluate()
        
        print("Due Today:", [v.name for v in res['due_today']] if res['due_today'] else "None")
        print("Missing Doses:", [v.name for v in res['missing_doses']] if res['missing_doses'] else "None")
        
        if res['next_appointment']:
            print("Next Appointment:", res['next_appointment'])
            print("Upcoming:", [(v.name, d) for v, d in res['upcoming']])
        else:
            print("Next Appointment: None")

if __name__ == "__main__":
    run_tests()
