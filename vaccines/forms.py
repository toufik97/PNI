from django import forms
from django.db import transaction

from .models import (
    CatchupRule,
    DependencyRule,
    GlobalConstraintRule,
    GroupRule,
    PolicyVersion,
    Product,
    ScheduleRule,
    Series,
    SeriesProduct,
    SeriesRule,
    SeriesTransitionRule,
    Vaccine,
    VaccineGroup,
)


class VaccineForm(forms.ModelForm):
    class Meta:
        model = Vaccine
        fields = ['name', 'live', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Penta, BCG, MMR'}),
            'live': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional description of this vaccine'}),
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
    available = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Use this for current stock availability in scheduling decisions.',
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
            initial.setdefault('available', instance.available)
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
            vaccine = Vaccine.objects.create(name=data['name'], live=data['live'], description=data['description'])
            product = Product.objects.create(
                vaccine=vaccine,
                code=data['code'],
                manufacturer=data['manufacturer'],
                description=data['description'],
                active=data['active'],
                available=data['available'],
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
            self.instance.available = data['available']
            self.instance.save()

        return self.instance


class PolicyVersionForm(forms.ModelForm):
    class Meta:
        model = PolicyVersion
        fields = ['name', 'code', 'description', 'effective_date', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Series Policy v2'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional slug code'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional version summary'}),
            'effective_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional rollout or migration notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False


class ScheduleRuleForm(forms.ModelForm):
    class Meta:
        model = ScheduleRule
        fields = ['dose_number', 'min_age_days', 'recommended_age_days', 'overdue_age_days', 'max_age_days', 'min_interval_days', 'dose_amount']
        widgets = {
            'dose_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'min_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 42'}),
            'recommended_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 42'}),
            'max_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Optional'}),
            'min_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'overdue_age_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Optional'}),
            'dose_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 0.05ml'}),
        }


ScheduleRuleFormSet = forms.inlineformset_factory(Vaccine, ScheduleRule, form=ScheduleRuleForm, extra=1, can_delete=True)


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


CatchupRuleFormSet = forms.inlineformset_factory(Vaccine, CatchupRule, form=CatchupRuleForm, extra=1, can_delete=True)


class VaccineGroupForm(forms.ModelForm):
    class Meta:
        model = VaccineGroup
        fields = ['name', 'vaccines', 'min_valid_interval_days']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., DTP Family'}),
            'vaccines': forms.CheckboxSelectMultiple(),
            'min_valid_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
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


GroupRuleFormSet = forms.inlineformset_factory(VaccineGroup, GroupRule, form=GroupRuleForm, extra=1, can_delete=True)


class SeriesForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['legacy_group'].queryset = VaccineGroup.objects.order_by('name')
        self.fields['legacy_group'].required = False
        self.fields['legacy_group'].disabled = True
        self.fields['legacy_group'].help_text = 'Legacy group linkage is now read-only migration metadata and is no longer used for new policy edits.'
        self.fields['policy_version'].queryset = PolicyVersion.objects.order_by('-is_active', 'name')
        active_version = PolicyVersion.get_active()
        if not self.instance.pk and active_version:
            self.fields['policy_version'].initial = active_version

    class Meta:
        model = Series
        fields = ['name', 'code', 'description', 'active', 'policy_version', 'mixing_policy', 'min_valid_interval_days', 'legacy_group']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Pneumo'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional slug code'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Clinical series description'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'policy_version': forms.Select(attrs={'class': 'form-select'}),
            'mixing_policy': forms.Select(attrs={'class': 'form-select'}),
            'min_valid_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'legacy_group': forms.Select(attrs={'class': 'form-select'}),
        }


class SeriesProductForm(forms.ModelForm):
    class Meta:
        model = SeriesProduct
        fields = ['product', 'priority']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.select_related('vaccine').order_by('vaccine__name')


SeriesProductFormSet = forms.inlineformset_factory(Series, SeriesProduct, form=SeriesProductForm, extra=1, can_delete=True)


class SeriesRuleForm(forms.ModelForm):
    class Meta:
        model = SeriesRule
        fields = ['slot_number', 'prior_valid_doses', 'product', 'min_age_days', 'recommended_age_days', 'overdue_age_days', 'max_age_days', 'min_interval_days', 'dose_amount', 'notes']
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.select_related('vaccine').order_by('vaccine__name')


SeriesRuleFormSet = forms.inlineformset_factory(Series, SeriesRule, form=SeriesRuleForm, extra=1, can_delete=True)



class GlobalConstraintRuleForm(forms.ModelForm):
    class Meta:
        model = GlobalConstraintRule
        fields = ['name', 'code', 'constraint_type', 'min_spacing_days', 'policy_version', 'active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Standard Live Spacing'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional slug code'}),
            'constraint_type': forms.Select(attrs={'class': 'form-select'}),
            'min_spacing_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
            'policy_version': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['policy_version'].queryset = PolicyVersion.objects.order_by('-is_active', 'name')
        active_version = PolicyVersion.get_active()
        if not self.instance.pk and active_version:
            self.fields['policy_version'].initial = active_version


class SeriesTransitionRuleInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen_ranges = []

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue

            cleaned_data = form.cleaned_data
            if not cleaned_data or cleaned_data.get('DELETE'):
                continue

            to_product = cleaned_data.get('to_product')
            if not to_product or not cleaned_data.get('active'):
                continue

            from_product = cleaned_data.get('from_product')
            start_slot = cleaned_data.get('start_slot_number') or 1
            end_slot = cleaned_data.get('end_slot_number') or 10 ** 9
            transition_key = (
                from_product.pk if from_product else None,
                to_product.pk,
                bool(cleaned_data.get('allow_if_unavailable')),
            )

            for existing_key, existing_start, existing_end in seen_ranges:
                if transition_key == existing_key and start_slot <= existing_end and end_slot >= existing_start:
                    raise forms.ValidationError(
                        'Active transition rules cannot overlap for the same source, destination, and availability condition.'
                    )

            seen_ranges.append((transition_key, start_slot, end_slot))


class SeriesTransitionRuleForm(forms.ModelForm):
    class Meta:
        model = SeriesTransitionRule
        fields = ['from_product', 'to_product', 'start_slot_number', 'end_slot_number', 'allow_if_unavailable', 'active', 'notes']
        widgets = {
            'from_product': forms.Select(attrs={'class': 'form-select'}),
            'to_product': forms.Select(attrs={'class': 'form-select'}),
            'start_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'end_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'allow_if_unavailable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product_queryset = Product.objects.select_related('vaccine').order_by('vaccine__name')
        self.fields['from_product'].queryset = product_queryset
        self.fields['to_product'].queryset = product_queryset


SeriesTransitionRuleFormSet = forms.inlineformset_factory(
    Series,
    SeriesTransitionRule,
    form=SeriesTransitionRuleForm,
    formset=SeriesTransitionRuleInlineFormSet,
    extra=1,
    can_delete=True,
)


class DependencyRuleForm(forms.ModelForm):
    class Meta:
        model = DependencyRule
        fields = ['dependent_series', 'dependent_slot_number', 'anchor_series', 'anchor_slot_number', 'min_offset_days', 'block_if_anchor_missing', 'active', 'notes']
        widgets = {
            'dependent_series': forms.Select(attrs={'class': 'form-select'}),
            'dependent_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'anchor_series': forms.Select(attrs={'class': 'form-select'}),
            'anchor_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'min_offset_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 15'}),
            'block_if_anchor_missing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        series_queryset = Series.objects.select_related('policy_version').order_by('policy_version__name', 'name')
        self.fields['dependent_series'].queryset = series_queryset
        self.fields['anchor_series'].queryset = series_queryset
