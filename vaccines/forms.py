from django import forms
from .models import Vaccine, ScheduleRule, CatchupRule, VaccineGroup, GroupRule


class VaccineForm(forms.ModelForm):
    class Meta:
        model = Vaccine
        fields = ['name', 'live', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Penta, BCG, MMR',
            }),
            'live': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional description of this vaccine',
            }),
        }
        labels = {
            'name': 'Vaccine Name',
            'live': 'Live Attenuated Vaccine',
            'description': 'Description',
        }
        help_texts = {
            'live': 'Check if this is a live vaccine (e.g., BCG, MMR, OPV). Live vaccines require a 28-day interval between each other.',
        }


class ScheduleRuleForm(forms.ModelForm):
    class Meta:
        model = ScheduleRule
        fields = [
            'dose_number', 'min_age_days', 'recommended_age_days', 
            'overdue_age_days', 'max_age_days', 'min_interval_days',
            'dose_amount'
        ]
        widgets = {
            'dose_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'min_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 42'}),
            'recommended_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 42'}),
            'max_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Optional'}),
            'min_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'overdue_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Optional'}),
            'dose_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 0.05ml'}),
        }
        labels = {
            'dose_number': 'Dose #',
            'min_age_days': 'Min Age (days)',
            'recommended_age_days': 'Recommended Age (days)',
            'max_age_days': 'Max Age (days)',
            'min_interval_days': 'Min Interval (days)',
            'overdue_age_days': 'Overdue Age (days)',
            'dose_amount': 'Dose Amount',
        }
        help_texts = {
            'min_age_days': '6wk=42, 10wk=70, 14wk=98, 6mo=180, 9mo=270, 12mo=365, 18mo=548',
            'recommended_age_days': 'The ideal age to give this dose',
            'max_age_days': 'Leave blank if no upper age limit',
            'min_interval_days': 'Minimum days since previous dose. Use 0 for first dose.',
            'overdue_age_days': 'Age (days) when marked MISSING (e.g., 30 for BCG)',
            'dose_amount': 'e.g., 0.05ml',
        }


ScheduleRuleFormSet = forms.inlineformset_factory(
    Vaccine,
    ScheduleRule,
    form=ScheduleRuleForm,
    extra=1,
    can_delete=True,
)


class CatchupRuleForm(forms.ModelForm):
    class Meta:
        model = CatchupRule
        fields = ['min_age_days', 'max_age_days', 'prior_doses', 'doses_required', 'min_interval_days', 'dose_amount']
        widgets = {
            'min_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 365'}),
            'max_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 1825'}),
            'prior_doses': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'doses_required': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'min_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'dose_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 0.1ml'}),
        }
        labels = {
            'min_age_days': 'From Age (days)',
            'max_age_days': 'To Age (days)',
            'prior_doses': 'Prior Doses',
            'doses_required': 'Total Doses Needed',
            'min_interval_days': 'Min Interval (days)',
            'dose_amount': 'Dose Amount',
        }
        help_texts = {
            'min_age_days': '6wk=42, 6mo=180, 12mo=365, 5yr=1825',
            'prior_doses': 'How many doses the child already has',
            'doses_required': 'Total doses needed to complete catch-up',
            'dose_amount': 'Optional override for catch-up (e.g., 0.1ml)',
        }


CatchupRuleFormSet = forms.inlineformset_factory(
    Vaccine,
    CatchupRule,
    form=CatchupRuleForm,
    extra=1,
    can_delete=True,
)


class VaccineGroupForm(forms.ModelForm):
    class Meta:
        model = VaccineGroup
        fields = ['name', 'vaccines', 'min_valid_interval_days']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., DTP Family',
            }),
            'vaccines': forms.CheckboxSelectMultiple(),
            'min_valid_interval_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': 'e.g., 28',
            }),
        }
        labels = {
            'name': 'Group Name',
            'vaccines': 'Vaccines in this Group',
            'min_valid_interval_days': 'Min Valid Interval (days)',
        }
        help_texts = {
            'vaccines': 'Select all vaccines that belong to this group (e.g., Penta + DTC + Td for the DTP family)',
            'min_valid_interval_days': 'Minimum days between any two doses within this group (usually 28)',
        }


class GroupRuleForm(forms.ModelForm):
    class Meta:
        model = GroupRule
        fields = ['prior_doses', 'min_age_days', 'max_age_days', 'vaccine_to_give', 'min_interval_days', 'dose_amount']
        widgets = {
            'prior_doses': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'min_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 42'}),
            'max_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Optional'}),
            'vaccine_to_give': forms.Select(attrs={'class': 'form-select'}),
            'min_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'dose_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 0.1ml'}),
        }
        labels = {
            'prior_doses': 'Prior Doses in Group',
            'min_age_days': 'From Age (days)',
            'max_age_days': 'To Age (days)',
            'vaccine_to_give': 'Vaccine to Give',
            'min_interval_days': 'Min Interval (days)',
            'dose_amount': 'Dose Amount',
        }
        help_texts = {
            'prior_doses': 'Number of valid doses already received from this group',
            'min_age_days': '6wk=42, 10wk=70, 14wk=98, 6mo=180, 9mo=270, 12mo=365',
            'max_age_days': 'Leave blank if no upper age limit for this rule',
            'min_interval_days': 'Minimum days from the last dose in the group',
            'dose_amount': 'Specific dose for this rule',
        }


GroupRuleFormSet = forms.inlineformset_factory(
    VaccineGroup,
    GroupRule,
    form=GroupRuleForm,
    extra=1,
    can_delete=True,
)
