from django.contrib import admin
from .models import Vaccine, ScheduleRule, CatchupRule, SubstitutionRule, VaccineGroup, GroupRule

class ScheduleRuleInline(admin.TabularInline):
    model = ScheduleRule
    extra = 1

class CatchupRuleInline(admin.TabularInline):
    model = CatchupRule
    extra = 1

@admin.register(Vaccine)
class VaccineAdmin(admin.ModelAdmin):
    list_display = ('name', 'live')
    inlines = [ScheduleRuleInline, CatchupRuleInline]

@admin.register(ScheduleRule)
class ScheduleRuleAdmin(admin.ModelAdmin):
    list_display = ('vaccine', 'dose_number', 'min_age_days', 'recommended_age_days', 'min_interval_days')
    list_filter = ('vaccine',)

@admin.register(CatchupRule)
class CatchupRuleAdmin(admin.ModelAdmin):
    list_display = ('vaccine', 'min_age_days', 'max_age_days', 'prior_doses', 'doses_required')
    list_filter = ('vaccine',)

@admin.register(SubstitutionRule)
class SubstitutionRuleAdmin(admin.ModelAdmin):
    list_display = ('substitute_vaccine', 'target_vaccine', 'condition')

class GroupRuleInline(admin.TabularInline):
    model = GroupRule
    extra = 1

@admin.register(VaccineGroup)
class VaccineGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_valid_interval_days')
    filter_horizontal = ('vaccines',)
    inlines = [GroupRuleInline]
