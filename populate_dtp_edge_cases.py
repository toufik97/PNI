import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from patients.models import Child, VaccinationRecord
from vaccines.models import Vaccine

def create_case(name_suffix, dob_days_ago, past_doses):
    name = f"Edge Case: {name_suffix}"
    child_id = f"dtp_edge_{name_suffix.replace(' ', '_').replace('<', 'lt').replace('>', 'gt').lower()}"
    
    dob = date.today() - timedelta(days=dob_days_ago)
    
    child, created = Child.objects.get_or_create(
        id=child_id,
        defaults={'name': name, 'sex': 'M', 'dob': dob}
    )
    
    if not created:
        # Update DOB and clear old records if it existed
        child.dob = dob
        child.name = name
        child.save()
        VaccinationRecord.objects.filter(child=child).delete()
        
    for v_name, days_ago in past_doses:
        v, _ = Vaccine.objects.get_or_create(name=v_name)
        d = date.today() - timedelta(days=days_ago)
        VaccinationRecord.objects.create(child=child, vaccine=v, date_given=d)

    print(f"Created: {name} (ID: {child.id}, Age: {dob_days_ago/30.44:.1f} months)")

def populate():
    # 1. 0 doses baby (< 12 months)
    # Age: 3 months, 0 doses. Needs Penta.
    create_case("0 doses baby", 90, [])

    # 2. 1 dose 4mo
    # Age: 4 months, 1 dose given at 2 months. Needs Penta.
    create_case("1 dose 4mo", 120, [('Penta', 60)])

    # 3. 3 doses 17mo (Wait for 18mo)
    # Age 17 months, 3 doses in primary series. Needs to wait until 18mo for DTC B1.
    create_case("3 doses 17mo Wait", 17*30, [
        ('Penta', 15*30), ('Penta', 14*30), ('Penta', 13*30)
    ])

    # 4. 3 doses 19mo (Ready for DTC)
    # Age 19 months, 3 doses in primary series. Ready for DTC B1.
    create_case("3 doses 19mo Ready", 19*30, [
        ('Penta', 17*30), ('Penta', 16*30), ('Penta', 15*30)
    ])

    # 5. Invalid interval (< 4 weeks)
    # Age 4 months, 2 doses given 20 days apart. Second dose will be flagged as invalid.
    create_case("Invalid interval lt 4w", 120, [
        ('Penta', 60), ('Penta', 40)
    ])

    # 6. 8 years old, 0 doses -> Needs Td
    create_case("8 years old 0 doses", 8*365, [])

    # 7. 8 years old, missing B2 -> Needs Td
    # 4 prior doses containing DTP
    create_case("8 yr old missing B2", 8*365, [
        ('Penta', 7*365), ('Penta', 7*365 - 30), ('Penta', 7*365 - 60), ('DTC', 6*365)
    ])
    
    # 8. Child received 2 doses, age 18mo - 3y -> Needs Penta (acting as dose 3)
    create_case("2 doses 2yr old", 2*365, [
        ('Penta', 2*365 - 60), ('Penta', 2*365 - 120)
    ])
    
    # 9. Child received 1 dose, age 5 years -> Needs DTC
    create_case("1 dose 5yr old", 5*365, [
        ('Penta', 5*365 - 60)
    ])

if __name__ == '__main__':
    populate()
    print("Edge cases populated successfully.")
