import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from vaccines.models import Vaccine, ScheduleRule, CatchupRule
from patients.models import Child

def v():
    print("Vaccines")
    for v in Vaccine.objects.all(): print(v.id, v.name)
    print("Schedule")
    for s in ScheduleRule.objects.all(): print(f"{s.vaccine.name} Dose {s.dose_number} min {s.min_age_days} rec {s.recommended_age_days}")
    print("Catchup")
    for c in CatchupRule.objects.all(): print(f"{c.vaccine.name} min {c.min_age_days} doses req {c.doses_required}")

if __name__ == "__main__": v()
