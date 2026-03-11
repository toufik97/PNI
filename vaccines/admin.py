from django.contrib import admin

from .models import (
    CatchupRule,
    DependencyRule,
    GroupRule,
    Product,
    ScheduleRule,
    Series,
    SeriesProduct,
    SeriesRule,
    SubstitutionRule,
    Vaccine,
    VaccineGroup,
)


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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('vaccine', 'code', 'manufacturer', 'active', 'available')
    list_filter = ('active', 'available', 'manufacturer')
    search_fields = ('vaccine__name', 'code', 'manufacturer')


class SeriesProductInline(admin.TabularInline):
    model = SeriesProduct
    extra = 0


class SeriesRuleInline(admin.TabularInline):
    model = SeriesRule
    extra = 0


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'active', 'mixing_policy', 'min_valid_interval_days', 'legacy_group')
    list_filter = ('active', 'mixing_policy')
    search_fields = ('name', 'code')
    inlines = [SeriesProductInline, SeriesRuleInline]


@admin.register(SeriesRule)
class SeriesRuleAdmin(admin.ModelAdmin):
    list_display = ('series', 'slot_number', 'prior_valid_doses', 'product', 'min_age_days', 'recommended_age_days', 'min_interval_days')
    list_filter = ('series', 'product')


@admin.register(DependencyRule)
class DependencyRuleAdmin(admin.ModelAdmin):
    list_display = ('dependent_series', 'dependent_slot_number', 'anchor_series', 'anchor_slot_number', 'min_offset_days', 'active')
    list_filter = ('active', 'dependent_series', 'anchor_series')
