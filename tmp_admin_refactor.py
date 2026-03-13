import re

# admin.py
admin_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/admin.py'
with open(admin_path, 'r', encoding='utf-8') as f:
    admin = f.read()

admin = re.sub(r'    CatchupRule,\n', '', admin)
admin = re.sub(r'    GroupRule,\n', '', admin)
admin = re.sub(r'    ScheduleRule,\n', '', admin)
admin = re.sub(r'    SubstitutionRule,\n', '', admin)
admin = re.sub(r'    VaccineGroup,\n', '', admin)

admin = re.sub(r'admin\.site\.register\(CatchupRule\)\n', '', admin)
admin = re.sub(r'admin\.site\.register\(GroupRule\)\n', '', admin)
admin = re.sub(r'admin\.site\.register\(ScheduleRule\)\n', '', admin)
admin = re.sub(r'admin\.site\.register\(SubstitutionRule\)\n', '', admin)
admin = re.sub(r'admin\.site\.register\(VaccineGroup\)\n', '', admin)

with open(admin_path, 'w', encoding='utf-8') as f:
    f.write(admin)

# forms.py
forms_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/forms.py'
with open(forms_path, 'r', encoding='utf-8') as f:
    forms = f.read()

forms = re.sub(r'    CatchupRule,\n', '', forms)
forms = re.sub(r'    GroupRule,\n', '', forms)
forms = re.sub(r'    ScheduleRule,\n', '', forms)
forms = re.sub(r'    VaccineGroup,\n', '', forms)
forms = re.sub(r'    Vaccine,\n', '    Vaccine,\n', forms)

forms = re.sub(r'class VaccineForm[\s\S]*?(?=class ProductForm)', '', forms)
forms = re.sub(r'class GroupForm[\s\S]*?(?=class ProductForm)', '', forms)
forms = re.sub(r'class CatchupRuleForm[\s\S]*?(?=class ProductForm)', '', forms)
forms = re.sub(r'class ScheduleRuleForm[\s\S]*?(?=class ProductForm)', '', forms)

with open(forms_path, 'w', encoding='utf-8') as f:
    f.write(forms)

