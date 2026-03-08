import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from patients.models import Child, VaccinationRecord
from vaccines.models import Vaccine
from vaccines.engine import VaccinationEngine

def ensure_vaccines():
    Vaccine.objects.get_or_create(name='Penta')
    Vaccine.objects.get_or_create(name='DTC')
    Vaccine.objects.get_or_create(name='Td')

ensure_vaccines()

def run_tests():
    with open('output_dtp.txt', 'w') as f:
        def log(msg=""):
            f.write(msg + "\n")
            
        def run_case(name, dob, eval_date, past_doses):
            log(f"\n--- Test Case: {name} ---")
            child, _ = Child.objects.get_or_create(
                id=f"test_{name.replace(' ', '_').lower()}",
                defaults={'name': name, 'sex': 'M', 'dob': dob}
            )
            VaccinationRecord.objects.filter(child=child).delete()
            for v_name, days_ago in past_doses:
                v = Vaccine.objects.get(name=v_name)
                d = eval_date - timedelta(days=days_ago)
                VaccinationRecord.objects.create(child=child, vaccine=v, date_given=d)
            
            engine = VaccinationEngine(child, evaluation_date=eval_date)
            res = engine.evaluate()
            
            age_months = (eval_date - dob).days / 30.44
            log(f"Age: {age_months:.1f} months")
            log(f"Due Today: {[v.name for v in res['due_today']] if res['due_today'] else 'None'}")
            log(f"Missing Doses: {[v.name for v in res['missing_doses']] if res['missing_doses'] else 'None'}")
            log(f"Upcoming: {[(v.name, d) for v, d in res['upcoming']] if res['upcoming'] else 'None'}")
            
            invalid_records = VaccinationRecord.objects.filter(child=child, invalid_flag=True)
            if invalid_records.exists():
                log("Invalid Records Found:")
                for r in invalid_records:
                    log(f"  - {r.vaccine.name} given on {r.date_given}: {r.notes}")
            child.delete()

        eval_today = date.today()
        # 1. 0 doses, < 12 months (should get Penta)
        run_case("0 doses baby", eval_today - timedelta(days=90), eval_today, [])
        # 2. 1 dose Penta 2 months ago, child now 4 months old (should get Penta)
        run_case("1 dose 4mo", eval_today - timedelta(days=120), eval_today, [('Penta', 60)])
        # 3. 3 doses Penta, child now 17 months old (should wait for 18mo B1 DTC)
        run_case("3 doses 17mo", eval_today - timedelta(days=17*30), eval_today, [
            ('Penta', 15*30), ('Penta', 14*30), ('Penta', 13*30)
        ])
        # 4. 3 doses Penta, child now 19 months old (should get DTC)
        run_case("3 doses 19mo", eval_today - timedelta(days=19*30), eval_today, [
            ('Penta', 17*30), ('Penta', 16*30), ('Penta', 15*30)
        ])
        # 5. Invalid interval (< 4 weeks)
        run_case("Invalid interval", eval_today - timedelta(days=120), eval_today, [
            ('Penta', 60), ('Penta', 40)
        ])
        # 6. > 7 years, 0 doses (Should get Td)
        run_case("8 years old", eval_today - timedelta(days=8*365), eval_today, [])
        # 7. > 7 years, 4 doses (Need dose 5 Td)
        run_case("8 years old missing B2", eval_today - timedelta(days=8*365), eval_today, [
            ('Penta', 7*365), ('Penta', 7*365 - 30), ('Penta', 7*365 - 60), ('DTC', 6*365)
        ])

if __name__ == '__main__':
    run_tests()
