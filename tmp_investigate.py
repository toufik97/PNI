import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from patients.models import Child
from vaccines.engine import VaccinationEngine

def run():
    with open('investigate_out.txt', 'w') as f:
        c = Child.objects.get(id='penta1-schedule')
        engine = VaccinationEngine(c)
        res = engine.evaluate()
        
        f.write("=== ENGINE OUTPUT ===\n")
        f.write("Due Today:\n")
        for d in res.get('due_today', []):
            f.write(f" - {d['vaccine'].name} (Slot {d.get('slot_number')})\n")
            
        f.write("\nMissing:\n")
        for m in res.get('missing_doses', []):
            f.write(f" - {m['vaccine'].name} (Slot {m.get('slot_number')})\n")
            
        f.write("\nUpcoming:\n")
        for item in res.get('upcoming', []):
            f.write(f" - {item}\n")

        f.write("\n=== CANDIDATE STATES ===\n")
        for series in res.get('active_series', []):
            state = engine._recommend_series(series)
            if state and state.get('status') in ['due', 'upcoming', 'missing']:
                f.write(f"\nSeries: {series.name}\n")
                f.write(f"  Status: {state['status']}\n")
                f.write(f"  Target Date: {state['target_date']}\n")
                f.write(f"  Products: {[p.vaccine.name for p in state['products']]}\n")
                f.write(f"  Rule Source: Slot {state['rule'].slot_number} (Min: {state['rule'].min_age_days}, Rec: {state['rule'].recommended_age_days})\n")

if __name__ == '__main__':
    run()
