from django import forms
from django.db import transaction

from .models import (
    DependencyRule,
    GlobalConstraintRule,
    PolicyVersion,
    Product,
    Series,
    SeriesProduct,
    SeriesRule,
    SeriesTransitionRule,
    Vaccine,
)


class ProductForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Prevenar13'}),
        help_text='Concrete product or brand name used at administration time.',
    )
    display_name = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Pentavalent (DTP+HBV+Hib)'}),
        help_text='Full human-readable name shown for general identification.',
    )
    protects_against = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Diphtheria, Tetanus, Pertussis'}),
        help_text='Comma-separated list of diseases this vaccine prevents.',
    )
    clinical_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Clinical administration or catch-up guidelines'}),
        help_text='Specific clinical notes displayed to providers.',
    )
    live = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Use for products that participate in live-vaccine spacing rules.',
    )
    compatible_with = forms.ModelMultipleChoiceField(
        queryset=Vaccine.objects.filter(live=True).order_by('name'),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input-list'}),
        help_text='Tick boxes for other live vaccines that are compatible (safe to give same-day or within spacing period).',
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
            initial.setdefault('display_name', instance.vaccine.display_name)
            initial.setdefault('protects_against', instance.vaccine.protects_against)
            initial.setdefault('clinical_notes', instance.vaccine.clinical_notes)
            initial.setdefault('live', instance.vaccine.live)
            initial.setdefault('compatible_with', instance.vaccine.compatible_live_vaccines.all())
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
            vaccine = Vaccine.objects.create(
                name=data['name'], 
                display_name=data['display_name'],
                protects_against=data['protects_against'],
                clinical_notes=data['clinical_notes'],
                live=data['live'], 
                description=data['description']
            )
            if data['compatible_with']:
                vaccine.compatible_live_vaccines.set(data['compatible_with'])
            
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
            vaccine.display_name = data['display_name']
            vaccine.protects_against = data['protects_against']
            vaccine.clinical_notes = data['clinical_notes']
            vaccine.live = data['live']
            vaccine.description = data['description']
            vaccine.save()
            vaccine.compatible_live_vaccines.set(data['compatible_with'])

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



class SeriesForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['policy_version'].queryset = PolicyVersion.objects.order_by('-is_active', 'name')
        active_version = PolicyVersion.get_active()
        if not self.instance.pk and active_version:
            self.fields['policy_version'].initial = active_version

    class Meta:
        model = Series
        fields = ['name', 'code', 'description', 'active', 'policy_version', 'mixing_policy', 'min_valid_interval_days']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Pneumo'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional slug code'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Clinical series description'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'policy_version': forms.Select(attrs={'class': 'form-select'}),
            'mixing_policy': forms.Select(attrs={'class': 'form-select'}),
            'min_valid_interval_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 28'}),
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
        product_qs = Product.objects.select_related('vaccine').order_by('vaccine__name')
        if not self.instance or not self.instance.pk:
            product_qs = product_qs.filter(active=True)
        self.fields['product'].queryset = product_qs


SeriesProductFormSet = forms.inlineformset_factory(Series, SeriesProduct, form=SeriesProductForm, extra=1, can_delete=True)


class SeriesRuleForm(forms.ModelForm):
    class Meta:
        model = SeriesRule
        fields = ['slot_number', 'prior_valid_doses', 'category', 'product', 'min_age_days', 'recommended_age_days', 'overdue_age_days', 'max_age_days', 'min_interval_days', 'dose_amount', 'notes']
        widgets = {
            'slot_number': forms.NumberInput(attrs={'class': 'form-control slot-number-input', 'min': 1}),
            'prior_valid_doses': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'category': forms.Select(attrs={'class': 'form-select rule-category-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'min_age_days': forms.NumberInput(attrs={'class': 'form-control age-input', 'min': 0, 'placeholder': 'e.g., 60'}),
            'recommended_age_days': forms.NumberInput(attrs={'class': 'form-control age-input', 'min': 0, 'placeholder': 'e.g., 75'}),
            'overdue_age_days': forms.NumberInput(attrs={'class': 'form-control age-input', 'min': 0, 'placeholder': 'Optional'}),
            'max_age_days': forms.NumberInput(attrs={'class': 'form-control age-input', 'min': 0, 'placeholder': 'Optional'}),
            'min_interval_days': forms.NumberInput(attrs={'class': 'form-control age-input', 'min': 0, 'placeholder': 'e.g., 28'}),
            'dose_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional dose amount'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product_qs = Product.objects.select_related('vaccine').order_by('vaccine__name')
        if not self.instance or not self.instance.pk:
            product_qs = product_qs.filter(active=True)
        self.fields['product'].queryset = product_qs


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
        fields = ['from_product', 'to_product', 'start_slot_number', 'end_slot_number', 'min_age_days', 'max_age_days', 'allow_if_unavailable', 'active', 'notes']
        widgets = {
            'from_product': forms.Select(attrs={'class': 'form-select'}),
            'to_product': forms.Select(attrs={'class': 'form-select'}),
            'start_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'end_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'min_age_days': forms.NumberInput(attrs={'class': 'form-control age-input', 'min': 0, 'placeholder': 'Optional'}),
            'max_age_days': forms.NumberInput(attrs={'class': 'form-control age-input', 'min': 0, 'placeholder': 'Optional'}),
            'allow_if_unavailable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product_qs = Product.objects.select_related('vaccine').order_by('vaccine__name')
        if not self.instance.pk:
            product_qs = product_qs.filter(active=True)
        self.fields['from_product'].queryset = product_qs
        self.fields['to_product'].queryset = product_qs


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
        fields = [
            'dependent_series', 'dependent_product', 'dependent_slot_number', 
            'anchor_series', 'anchor_product', 'anchor_slot_number',
            'min_offset_days', 'block_if_anchor_missing', 'is_coadmin', 'active', 'notes'
        ]
        widgets = {
            'dependent_series': forms.Select(attrs={'class': 'form-select'}),
            'dependent_product': forms.Select(attrs={'class': 'form-select'}),
            'dependent_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'anchor_series': forms.Select(attrs={'class': 'form-select'}),
            'anchor_product': forms.Select(attrs={'class': 'form-select'}),
            'anchor_slot_number': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Optional'}),
            'min_offset_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'e.g., 15'}),
            'block_if_anchor_missing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_coadmin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Determine the target policy version
        policy_version = None
        if self.instance and self.instance.pk and self.instance.dependent_series_id:
            policy_version = self.instance.dependent_series.policy_version
        else:
            policy_version = PolicyVersion.get_active()
            
        series_queryset = Series.objects.order_by('name')
        if policy_version:
            series_queryset = series_queryset.filter(policy_version=policy_version)
        else:
            # Fallback for empty DB scenario (though uncommon in production)
            series_queryset = series_queryset.select_related('policy_version').order_by('policy_version__name', 'name')

        self.fields['dependent_series'].queryset = series_queryset
        self.fields['anchor_series'].queryset = series_queryset
        
        # We also filter products to active ones for better UX, 
        # as inactive products are generally legacy and hidden from new policy edits.
        product_queryset = Product.objects.filter(active=True).select_related('vaccine').order_by('vaccine__name')
        self.fields['dependent_product'].queryset = product_queryset
        self.fields['anchor_product'].queryset = product_queryset

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data:
            return cleaned_data

        if not cleaned_data.get('block_if_anchor_missing') or not cleaned_data.get('active'):
            return cleaned_data

        dependent_series = cleaned_data.get('dependent_series')
        anchor_series = cleaned_data.get('anchor_series')
        
        if not dependent_series or not anchor_series:
            return cleaned_data

        visited = set()
        
        def has_path(current_node, target_node):
            if current_node == target_node:
                return True
            visited.add(current_node)
            
            dependencies = DependencyRule.objects.filter(
                dependent_series_id=current_node,
                block_if_anchor_missing=True,
                active=True
            )
            if self.instance and self.instance.pk:
                dependencies = dependencies.exclude(pk=self.instance.pk)
                
            for dep in dependencies:
                next_node = dep.anchor_series_id
                if next_node not in visited:
                    if has_path(next_node, target_node):
                        return True
            return False
            
        if has_path(anchor_series.id, dependent_series.id):
            raise forms.ValidationError("Dependency rules cannot create a blocking cycle across multiple series slots.")
            
        return cleaned_data
