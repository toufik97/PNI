from django.contrib import admin

from .models import (
    DependencyRule,
    PolicyVersion,
    Product,
    Series,
    SeriesProduct,
    SeriesRule,
    Vaccine,
)


@admin.register(Vaccine)
class VaccineAdmin(admin.ModelAdmin):
    list_display = ('name', 'live')
class SeriesProductInline(admin.TabularInline):
    model = SeriesProduct
    extra = 0


class SeriesRuleInline(admin.TabularInline):
    model = SeriesRule
    extra = 0


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'policy_version', 'active', 'mixing_policy', 'min_valid_interval_days')
    list_filter = ('active', 'mixing_policy', 'policy_version')
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
