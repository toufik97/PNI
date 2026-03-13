import re
import os

# urls.py
url_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/urls.py'
with open(url_path, 'r', encoding='utf-8') as f:
    urls = f.read()
urls = re.sub(r'\s*path\(\'settings/vaccine/.*?\n', '\n', urls)
urls = re.sub(r'\s*path\(\'settings/group/.*?\n', '\n', urls)
with open(url_path, 'w', encoding='utf-8') as f:
    f.write(urls)

# views.py
views_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/views.py'
with open(views_path, 'r', encoding='utf-8') as f:
    views = f.read()

# Remove legacy tab sets
views = views.replace('LEGACY_TABS = {\'vaccines\', \'groups\'}\n', '')
views = views.replace('ALL_TABS = LEGACY_TABS.union(NEW_TABS)\n', 'ALL_TABS = NEW_TABS\n')
views = views.replace('LEGACY_POLICY_READ_ONLY = True\n', '')
views = re.sub(r'\n\ndef _redirect_legacy_policy_read_only.*?\n\n', '\n\n', views, flags=re.DOTALL)

# Remove context from vaccine_settings
views = re.sub(r'    vaccines = Vaccine.*?\n', '', views)
views = re.sub(r'    groups = VaccineGroup.*?\n', '', views)
views = views.replace('        \'vaccines\': vaccines,\n', '')
views = views.replace('        \'groups\': groups,\n', '')

# Remove Legacy CRUD Methods
views = re.sub(r'# Legacy Vaccine CRUD\s*def vaccine_create.*', '', views, flags=re.DOTALL)

with open(views_path, 'w', encoding='utf-8') as f:
    f.write(views)

# settings.html
html_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/templates/vaccines/settings.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

html = re.sub(r'\s*<li class="nav-item"><a class="nav-link.*?\'vaccines\'.*?</li>', '', html)
html = re.sub(r'\s*<li class="nav-item"><a class="nav-link.*?\'groups\'.*?</li>', '', html)

html = re.sub(r'\s*{% elif active_tab == \'vaccines\' %}[\s\S]*?(?={% else %}\n\s*<div class="info-box">)', '\n    ', html)

html = re.sub(r'\s*<div class="guide-step"><strong>7\.</strong> Use the legacy tabs only when you still need to maintain old schedule/group policy during the migration\.</div>', '', html)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

# Delete templates
for tmpl in ['group_form.html', 'vaccine_form.html', 'group_confirm_delete.html', 'vaccine_confirm_delete.html', 'rule_form.html', 'catchup_form.html']:
    tmpl_path = f'c:/Users/admiralTOUFIK/PNI/vaccines/templates/vaccines/{tmpl}'
    if os.path.exists(tmpl_path):
        os.remove(tmpl_path)

