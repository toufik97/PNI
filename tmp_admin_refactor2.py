import re

admin_path = 'c:/Users/admiralTOUFIK/PNI/vaccines/admin.py'
with open(admin_path, 'r', encoding='utf-8') as f:
    admin = f.read()

admin = re.sub(r'class ScheduleRuleInline\[\s\S]*?(?=class ProductInline|class SeriesProductInline|class SeriesRuleInline|class VaccineAdmin)', '', admin)
admin = re.sub(r'class CatchupRuleInline\[\s\S]*?(?=class ProductInline|class SeriesProductInline|class SeriesRuleInline|class VaccineAdmin)', '', admin)
admin = re.sub(r'class SubstitutionRuleInline[\s\S]*?(?=class ProductInline|class SeriesProductInline|class SeriesRuleInline|class VaccineAdmin)', '', admin)
admin = re.sub(r'class GroupRuleInline[\s\S]*?(?=class ProductInline|class SeriesProductInline|class SeriesRuleInline|class VaccineAdmin)', '', admin)

# Remove the classes explicitly
admin = re.sub(r'class ScheduleRuleInline\(admin\.TabularInline\):\n    model = ScheduleRule\n    extra = 1\n\n\n', '', admin)
admin = re.sub(r'class CatchupRuleInline\(admin\.TabularInline\):\n    model = CatchupRule\n    extra = 1\n\n\n', '', admin)
admin = re.sub(r'class SubstitutionRuleInline\(admin\.TabularInline\):\n    model = SubstitutionRule\n    fk_name = \'target_vaccine\'\n    extra = 1\n\n\n', '', admin)
admin = re.sub(r'class GroupRuleInline\(admin\.TabularInline\):\n    model = GroupRule\n    extra = 1\n\n\n', '', admin)

# Also remove them from VaccineAdmin
admin = re.sub(r'    inlines = \[ScheduleRuleInline, CatchupRuleInline, SubstitutionRuleInline\]\n', '', admin)

# Remove VaccineGroupAdmin
admin = re.sub(r'@admin\.register\(VaccineGroup\)[\s\S]*?class VaccineGroupAdmin\(admin\.ModelAdmin\):[\s\S]*?inlines = \[GroupRuleInline\]\n\n', '', admin)
admin = re.sub(r'class VaccineGroupAdmin.*?\n    inlines = \[GroupRuleInline\]\n\n\n', '', admin, flags=re.DOTALL)

with open(admin_path, 'w', encoding='utf-8') as f:
    f.write(admin)
