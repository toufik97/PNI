import json
import re

# policy_reference.json
policy_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/policy_reference.json'
with open(policy_path, 'r', encoding='utf-8') as f:
    policy = json.load(f)

if 'schedule_rules' in policy:
    del policy['schedule_rules']
if 'catchup_rules' in policy:
    del policy['catchup_rules']
if 'groups' in policy:
    del policy['groups']

with open(policy_path, 'w', encoding='utf-8') as f:
    json.dump(policy, f, indent=4)


# base.py
base_path = 'c:/Users/admiralTOUFIK/PNI/tests/base.py'
with open(base_path, 'r', encoding='utf-8') as f:
    base = f.read()

# Remove imports
base = re.sub(r'\s*CatchupRule,', '', base)
base = re.sub(r'\s*GroupRule,', '', base)
base = re.sub(r'\s*ScheduleRule,', '', base)
base = re.sub(r'\s*VaccineGroup,', '', base)

# Remove json parsing loops for legacy keys
base = re.sub(r'        for schedule_data in policy\[\'schedule_rules\'\]:.*?required_vaccine_names\.add\(schedule_data\[\'vaccine\'\]\)\n', '', base, flags=re.DOTALL)
base = re.sub(r'        for catchup_data in policy\[\'catchup_rules\'\]:.*?required_vaccine_names\.add\(catchup_data\[\'vaccine\'\]\)\n', '', base, flags=re.DOTALL)
base = re.sub(r'        for group_data in policy\[\'groups\'\]:.*?required_vaccine_names\.update\(rule_data\[\'vaccine_to_give\'\] for rule_data in group_data\[\'rules\'\]\)\n', '', base, flags=re.DOTALL)

# Default to get() for backwards compat if they were using it
base = base.replace('policy[\'schedule_rules\']', 'policy.get(\'schedule_rules\', [])')
base = base.replace('policy[\'catchup_rules\']', 'policy.get(\'catchup_rules\', [])')
base = base.replace('policy[\'groups\']', 'policy.get(\'groups\', [])')

# Remove the actual object creation loops from base.py
base = re.sub(r'        for schedule_data in policy\.get\(\'schedule_rules\', \[\]\):.*?ScheduleRule\.objects\.create\(vaccine=vaccine, \*\*rule\)\n', '', base, flags=re.DOTALL)
base = re.sub(r'        for catchup_data in policy\.get\(\'catchup_rules\', \[\]\):.*?CatchupRule\.objects\.create\(vaccine=vaccine, \*\*rule\)\n', '', base, flags=re.DOTALL)

# Delete group creation entirely
base = re.sub(r'        self\.dtp_group = None\n.*?if group_data\[\'name\'\] == \'DTP Family\':\n\s*self\.dtp_group = group\n', '', base, flags=re.DOTALL)

# Remove legacy_group from series creation
base = re.sub(r'\s*legacy_group=self\.group_map\.get.*?,\n', '\n', base)
base = re.sub(r'\s*legacy_group=group,\n', '\n', base)

# Delete creating Series from Groups
group_series_creation = r'        for group_data in policy\.get\(\'groups\', \[\]\):[\s\S]*?(?=        for transition_data in policy\.get\(\'transitions\', \[\]\):)'
base = re.sub(group_series_creation, '', base)

base = base.replace('    include_dtp_legacy_group = True\n', '')

with open(base_path, 'w', encoding='utf-8') as f:
    f.write(base)
