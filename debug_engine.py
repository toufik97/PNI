import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from patients.models import Child
from vaccines.engine import VaccinationEngine

c = Child.objects.get(id="CH-001")
print("CHILD AGE:", (date.today() - c.dob).days)
e = VaccinationEngine(c)
print("VACCINES:", e.vaccines)
for v in e.vaccines:
    v_history = []
    prior_doses = 0
    print(f"\nEvaluating: {v.name}")
    from vaccines.models import CatchupRule, ScheduleRule
    cr = CatchupRule.objects.filter(vaccine=v, min_age_days__lte=e.age_days, max_age_days__gte=e.age_days, prior_doses=prior_doses).first()
    print("Catchup Rule?", cr)
    if cr:
        print("Using catchup!")
    else:
        sr = ScheduleRule.objects.filter(vaccine=v, dose_number=1).first()
        print("Schedule Rule?", sr)
        if sr:
            print("min_age:", sr.min_age_days, "rec:", sr.recommended_age_days)
            print("Is age > rec?", e.age_days > sr.recommended_age_days)
            print("Is age >= min?", e.age_days >= sr.min_age_days)

print("\n--- Evaluate result ---")
res = e.evaluate()
print("Due Today raw:", res['due_today'])
print("Missing Doses raw:", res['missing_doses'])

