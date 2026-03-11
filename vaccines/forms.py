from django import forms
from django.db import transaction

from .models import (
    CatchupRule,
    GroupRule,
    Product,
    ScheduleRule,
    Series,
    SeriesProduct,
    SeriesRule,
    Vaccine,
    VaccineGroup,
)


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


class ProductForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Prevenar13'}),
        help_text='Concrete product or brand name used at administration time.',
    )
    live = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Use for products that participate in live-vaccine spacing rules.',
    )
    code = forms.SlugField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional slug code'}),
        help_text='Optional machine-readable code. Leave blank to auto-generate from the name.',
    )
    manufacturer = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Pfizer'}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
    )
    active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Inactive products stay in history but are hidden from new policy choices.',
    )

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        initial = kwargs.setdefault('initial', {})
        if instance is not None:
            initial.setdefault('name', instance.vaccine.name)
            initial.setdefault('live', instance.vaccine.live)
            initial.setdefault('code', instance.code)
            initial.setdefault('manufacturer', instance.manufacturer)
            initial.setdefault('description', instance.description or instance.vaccine.description)
            initial.setdefault('active', instance.active)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        existing = Vaccine.objects.filter(name__iexact=name)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.vaccine_id)
        if existing.exists():
            raise forms.ValidationError('A vaccine/product with this name already exists.')
        return name

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code:
            return code
        existing = Product.objects.filter(code=code)
        if self.instance is not None:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError('A product with this code already exists.')
        return code

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        if self.instance is None:
            vaccine = Vaccine.objects.create(
                name=data['name'],
                live=data['live'],
                description=data['description'],
            )
            product = Product.objects.create(
                vaccine=vaccine,
                code=data['code'],
                manufacturer=data['manufacturer'],
                description=data['description'],
                active=data['active'],
            )
            self.instance = product
        else:
            vaccine = self.instance.vaccine
            vaccine.name = data['name']
            vaccine.live = data['live']
            vaccine.description = data['description']
            vaccine.save()

            self.instance.code = data['code'] or self.instance.code
            self.instance.manufacturer = data['manufacturer']
            self.instance.description = data['description']
            self.instance.active = data['active']
            self.instance.save()

        return self.instance


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


class SeriesForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['legacy_group'].queryset = VaccineGroup.objects.order_by('name')

    class Meta:
        model = Series
        fields = ['name', 'code', 'description', 'active', 'mixing_policy', 'min_valid_interval_days', 'legacy_group']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Pneumo'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional slug code'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Clinical series description'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'mixing_policy': forms.Select(attrs={'class': 'form-select'}),
            'min_valid_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'legacy_group': forms.Select(attrs={'class': 'form-select'}),
        }
        help_texts = {
            'code': 'Optional machine-readable code. Leave blank to auto-generate from the name.',
            'legacy_group': 'Optional legacy bridge while old group policies still exist.',
            'min_valid_interval_days': 'Hard floor between any two doses in the series.',
        }


class SeriesProductForm(forms.ModelForm):
    class Meta:
        model = SeriesProduct
        fields = ['product', 'priority']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
        help_texts = {
            'priority': 'Lower values appear first when reviewing the series.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.select_related('vaccine').order_by('vaccine__name')


SeriesProductFormSet = forms.inlineformset_factory(
    Series,
    SeriesProduct,
    form=SeriesProductForm,
    extra=1,
    can_delete=True,
)


class SeriesRuleForm(forms.ModelForm):
    class Meta:
        model = SeriesRule
        fields = [
            'slot_number', 'prior_valid_doses', 'product', 'min_age_days', 'recommended_age_days',
            'overdue_age_days', 'max_age_days', 'min_interval_days', 'dose_amount', 'notes'
        ]
        widgets = {
            'slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'prior_valid_doses': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'min_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 60'}),
            'recommended_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 75'}),
            'overdue_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Optional'}),
            'max_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Optional'}),
            'min_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'dose_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional dose amount'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}),
        }
        help_texts = {
            'prior_valid_doses': 'If the child already has this many valid series doses, this rule becomes the next slot candidate.',
            'product': 'Concrete product allowed for this slot rule.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.select_related('vaccine').order_by('vaccine__name')


SeriesRuleFormSet = forms.inlineformset_factory(
    Series,
    SeriesRule,
    form=SeriesRuleForm,
    extra=1,
    can_delete=True,
)

