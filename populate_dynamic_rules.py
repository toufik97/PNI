import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vaxapp.settings')
django.setup()

from vaccines.models import Vaccine, VaccineGroup, GroupRule

def populate_dtp_rules():
    print("Populating Dynamic DTP Rules...")
    penta, _ = Vaccine.objects.get_or_create(name='Penta')
    dtc, _ = Vaccine.objects.get_or_create(name='DTC')
    td, _ = Vaccine.objects.get_or_create(name='Td')

    # Create Group
    dtp_group, _ = VaccineGroup.objects.get_or_create(
        name="DTP Family",
        defaults={'min_valid_interval_days': 28}
    )
    dtp_group.vaccines.set([penta, dtc, td])

    # Clear old rules to prevent duplication on rerun
    GroupRule.objects.filter(group=dtp_group).delete()

    rules = []
    
    # helper to add a rule
    def add_rule(prior, min_age, max_age, vaccine, min_interval):
        rules.append(GroupRule(
            group=dtp_group,
            prior_doses=prior,
            min_age_days=min_age,
            max_age_days=max_age,
            vaccine_to_give=vaccine,
            min_interval_days=min_interval
        ))

    # Age definitions (approximate in days)
    MO_12 = 365
    MO_18 = 18 * 30
    YR_3 = 3 * 365
    YR_5 = 5 * 365
    YR_7 = 7 * 365

    # 1. Rules for 0 prior doses
    add_rule(0, 0, MO_12 - 1, penta, 0)         # < 12m: Penta
    add_rule(0, MO_12, YR_3 - 1, penta, 0)      # 12m - 3y: Penta
    add_rule(0, YR_3, YR_7 - 1, dtc, 0)         # 3y - 7y: DTC
    add_rule(0, YR_7, None, td, 0)              # > 7y: Td

    # 2. Rules for 1 prior dose
    add_rule(1, 0, MO_18 - 1, penta, 28)        # < 18m: Penta
    add_rule(1, MO_18, YR_3 - 1, penta, 28)     # 18m - 3y: Penta
    add_rule(1, YR_3, YR_7 - 1, dtc, 28)        # 3y - 7y: DTC
    add_rule(1, YR_7, None, td, 28)             # > 7y: Td

    # 3. Rules for 2 prior doses
    add_rule(2, 0, MO_18 - 1, penta, 28)        # < 18m: Penta
    add_rule(2, MO_18, YR_3 - 1, penta, 28)     # 18m - 3y: Penta
    add_rule(2, YR_3, YR_7 - 1, dtc, 28)        # 3y - 7y: DTC
    add_rule(2, YR_7, None, td, 28)             # > 7y: Td

    # 4. Rules for 3 prior doses (Primary series complete)
    add_rule(3, MO_18, None, dtc, 180)           # >= 18m: DTC
    add_rule(3, YR_7, None, td, 180)             # > 7y: Td

    # 5. Rules for 4 prior doses (B1 complete)
    add_rule(4, YR_5, None, dtc, 4 * 365)       # >= 5y: DTC
    add_rule(4, YR_7, None, td, 365)            # > 7y: Td



    # Bulk create
    GroupRule.objects.bulk_create(rules)
    print(f"Created {len(rules)} GroupRules for DTP Family.")

if __name__ == "__main__":
    populate_dtp_rules()
