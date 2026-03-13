import json

policy_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/policy_reference.json'
with open(policy_path, 'r', encoding='utf-8') as f:
    policy = json.load(f)

# Add RR and BCG series
rr_series = {
    "name": "RR Series",
    "optional": False,
    "min_valid_interval_days": 28,
    "mixing_policy": "strict",
    "products": ["RR"],
    "rules": [
        {
            "slot_number": 1,
            "prior_valid_doses": 0,
            "product": "RR",
            "min_age_days": 270,
            "recommended_age_days": 270,
            "overdue_age_days": 365,
            "max_age_days": None,
            "min_interval_days": 0
        },
        {
            "slot_number": 2,
            "prior_valid_doses": 1,
            "product": "RR",
            "min_age_days": 540,
            "recommended_age_days": 540,
            "overdue_age_days": 600,
            "max_age_days": None,
            "min_interval_days": 28
        }
    ]
}

bcg_series = {
    "name": "BCG Series",
    "optional": False,
    "min_valid_interval_days": 28,
    "mixing_policy": "strict",
    "products": ["BCG"],
    "rules": [
        {
            "slot_number": 1,
            "prior_valid_doses": 0,
            "product": "BCG",
            "min_age_days": 0,
            "recommended_age_days": 0,
            "overdue_age_days": 30,
            "max_age_days": 365,
            "min_interval_days": 0,
            "dose_amount": "0.1ml"
        }
    ]
}

policy['series'].append(rr_series)
policy['series'].append(bcg_series)

with open(policy_path, 'w', encoding='utf-8') as f:
    json.dump(policy, f, indent=4)
