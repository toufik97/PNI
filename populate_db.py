import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from vaccines.models import Vaccine, ScheduleRule, CatchupRule
from patients.models import Child, VaccinationRecord

def populate():
    print("Populating DB with sandboxed policies...")
    
    # 1. Create Vaccines
    penta, _ = Vaccine.objects.get_or_create(name="Penta", live=False)
    mr, _ = Vaccine.objects.get_or_create(name="Measles/Rubella", live=True)

    # 2. Create Schedule
    # Penta: 3 doses at 2, 3, 4 months (60, 90, 120 days). Min interval 28 days.
    ScheduleRule.objects.get_or_create(vaccine=penta, dose_number=1, min_age_days=42, recommended_age_days=60, min_interval_days=0)
    ScheduleRule.objects.get_or_create(vaccine=penta, dose_number=2, min_age_days=70, recommended_age_days=90, min_interval_days=28)
    ScheduleRule.objects.get_or_create(vaccine=penta, dose_number=3, min_age_days=98, recommended_age_days=120, min_interval_days=28)

    # Measles: 2 doses at 9 months and 18 months (270, 540 days)
    ScheduleRule.objects.get_or_create(vaccine=mr, dose_number=1, min_age_days=250, recommended_age_days=270, min_interval_days=0)
    ScheduleRule.objects.get_or_create(vaccine=mr, dose_number=2, min_age_days=500, recommended_age_days=540, min_interval_days=28)

    # 3. Create Catchup Rule
    CatchupRule.objects.get_or_create(
        vaccine=penta,
        min_age_days=365,
        max_age_days=2000,
        prior_doses=0,
        doses_required=2,
        min_interval_days=28
    )

    # 4. Create dummy children
    child1, _ = Child.objects.get_or_create(
        id="CH-001", defaults={'name': "Normal Routine Baby", 'sex': 'F', 'dob': date.today() - timedelta(days=65)}
    ) # 2 months old, due for Penta 1
    
    child2, _ = Child.objects.get_or_create(
        id="CH-002", defaults={'name': "Late Catchup Toddler", 'sex': 'M', 'dob': date.today() - timedelta(days=400)}
    ) # 13 months old
    
    print("Database populated successfully.")

if __name__ == "__main__":
    populate()
