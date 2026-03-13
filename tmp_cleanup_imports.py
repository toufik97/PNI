import os
import re

def remove_from_file(filepath, pattern, replacement):
    with open(filepath, 'r') as f:
        content = f.read()
    content = re.sub(pattern, replacement, content)
    with open(filepath, 'w') as f:
        f.write(content)

# 1. test_module_boundaries.py
remove_from_file('c:/Users/admiralTOUFIK/PNI/tests/test_module_boundaries.py', r', ScheduleRule', '')

# 2. test_prevention.py
remove_from_file('c:/Users/admiralTOUFIK/PNI/tests/test_prevention.py', r'GroupRule,\s*Product,\s*ScheduleRule', 'Product')
remove_from_file('c:/Users/admiralTOUFIK/PNI/tests/test_prevention.py', r',\s*VaccineGroup', '')

# 3. test_series_policy_slice.py
remove_from_file('c:/Users/admiralTOUFIK/PNI/tests/test_series_policy_slice.py', r'from vaccines.models import ScheduleRule\n', '')

# 4. test_settings_ui_series.py
remove_from_file('c:/Users/admiralTOUFIK/PNI/tests/test_settings_ui_series.py', r',\s*VaccineGroup', '')

# 5. views.py
remove_from_file('c:/Users/admiralTOUFIK/PNI/vaccines/views.py', r"\s*'legacy_policy_read_only': LEGACY_POLICY_READ_ONLY,", "")
