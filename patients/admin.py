from django.contrib import admin
from .models import Child, VaccinationRecord

@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'sex', 'dob', 'contact_info', 'unknown_status')
    search_fields = ('id', 'name', 'parents_name')

@admin.register(VaccinationRecord)
class VaccinationRecordAdmin(admin.ModelAdmin):
    list_display = ('child', 'vaccine', 'date_given', 'invalid_flag')
    list_filter = ('vaccine', 'invalid_flag', 'date_given')
    search_fields = ('child__id', 'child__name', 'lot_number')
