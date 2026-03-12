from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    CatchupRuleFormSet,
    DependencyRuleForm,
    GlobalConstraintRuleForm,
    GroupRuleFormSet,
    PolicyVersionForm,
    ProductForm,
    ScheduleRuleFormSet,
    SeriesForm,
    SeriesProductFormSet,
    SeriesRuleFormSet,
    SeriesTransitionRuleFormSet,
    VaccineForm,
    VaccineGroupForm,
)
from .models import DependencyRule, GlobalConstraintRule, PolicyVersion, Product, Series, Vaccine, VaccineGroup


LEGACY_TABS = {'vaccines', 'groups'}
NEW_TABS = {'products', 'series', 'dependencies', 'constraints', 'versions', 'guide'}
ALL_TABS = LEGACY_TABS.union(NEW_TABS)
LEGACY_POLICY_READ_ONLY = True


def _redirect_legacy_policy_read_only(request, tab):
    messages.warning(request, 'Legacy vaccine and group configuration is read-only during the series policy migration.')
    return redirect('vaccines:settings_tab', tab=tab)


def vaccine_settings(request, tab=None):
    active_tab = tab or request.GET.get('tab', 'products')
    if active_tab not in ALL_TABS:
        active_tab = 'products'

    active_policy_version = PolicyVersion.get_active()

    vaccines = Vaccine.objects.prefetch_related('schedule_rules', 'catchup_rules').all()
    groups = VaccineGroup.objects.prefetch_related('vaccines', 'rules').all()
    products = Product.objects.select_related('vaccine').prefetch_related('series_memberships').all()
    series = Series.objects.select_related('policy_version').prefetch_related('series_products__product__vaccine', 'rules__product__vaccine', 'transition_rules__from_product__vaccine', 'transition_rules__to_product__vaccine')
    dependencies = DependencyRule.objects.select_related('dependent_series__policy_version', 'anchor_series__policy_version')
    global_constraints = GlobalConstraintRule.objects.select_related('policy_version')
    if active_policy_version is not None:
        series = series.filter(policy_version=active_policy_version)
        dependencies = dependencies.filter(dependent_series__policy_version=active_policy_version, anchor_series__policy_version=active_policy_version)
        global_constraints = global_constraints.filter(policy_version=active_policy_version)
    else:
        series = series.none()
        dependencies = dependencies.none()
        global_constraints = global_constraints.none()
    policy_versions = PolicyVersion.objects.order_by('-is_active', 'name')

    context = {
        'vaccines': vaccines,
        'groups': groups,
        'products': products,
        'series_list': series,
        'dependencies': dependencies,
        'global_constraints': global_constraints,
        'policy_versions': policy_versions,
        'active_policy_version': active_policy_version,
        'active_tab': active_tab,
        'legacy_policy_read_only': LEGACY_POLICY_READ_ONLY,
    }
    return render(request, 'vaccines/settings.html', context)


def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.vaccine.name}" created successfully.')
            return redirect('vaccines:settings_tab', tab='products')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductForm()

    return render(request, 'vaccines/product_form.html', {'form': form, 'title': 'Add New Product', 'submit_label': 'Create Product'})


def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.vaccine.name}" updated successfully.')
            return redirect('vaccines:settings_tab', tab='products')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductForm(instance=product)

    return render(request, 'vaccines/product_form.html', {'form': form, 'title': f'Edit Product: {product.vaccine.name}', 'submit_label': 'Save Changes', 'product': product})


def product_delete(request, pk):
    product = get_object_or_404(Product.objects.select_related('vaccine'), pk=pk)
    if request.method == 'POST':
        name = product.vaccine.name
        product.delete()
        messages.success(request, f'Product profile "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='products')
    return render(request, 'vaccines/confirm_delete.html', {'object': product, 'object_type': 'Product Profile', 'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'products'})})


def policy_version_create(request):
    if request.method == 'POST':
        form = PolicyVersionForm(request.POST)
        if form.is_valid():
            version = form.save()
            messages.success(request, f'Policy version "{version.name}" created successfully.')
            return redirect('vaccines:settings_tab', tab='versions')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = PolicyVersionForm()

    return render(request, 'vaccines/policy_version_form.html', {'form': form, 'title': 'Add Policy Version', 'submit_label': 'Create Version'})


def policy_version_edit(request, pk):
    version = get_object_or_404(PolicyVersion, pk=pk)
    if request.method == 'POST':
        form = PolicyVersionForm(request.POST, instance=version)
        if form.is_valid():
            version = form.save()
            messages.success(request, f'Policy version "{version.name}" updated successfully.')
            return redirect('vaccines:settings_tab', tab='versions')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = PolicyVersionForm(instance=version)

    return render(request, 'vaccines/policy_version_form.html', {'form': form, 'title': f'Edit Policy Version: {version.name}', 'submit_label': 'Save Changes', 'policy_version': version})


def policy_version_delete(request, pk):
    version = get_object_or_404(PolicyVersion, pk=pk)
    if request.method == 'POST':
        name = version.name
        version.delete()
        messages.success(request, f'Policy version "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='versions')
    return render(request, 'vaccines/confirm_delete.html', {'object': version, 'object_type': 'Policy Version', 'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'versions'})})


def series_create(request):
    if request.method == 'POST':
        form = SeriesForm(request.POST)
        product_formset = SeriesProductFormSet(request.POST, prefix='products')
        rule_formset = SeriesRuleFormSet(request.POST, prefix='rules')
        transition_formset = SeriesTransitionRuleFormSet(request.POST, prefix='transitions')
        if form.is_valid() and product_formset.is_valid():
            with transaction.atomic():
                series = form.save()
                product_formset = SeriesProductFormSet(request.POST, instance=series, prefix='products')
                if product_formset.is_valid():
                    product_formset.save()
                    rule_formset = SeriesRuleFormSet(request.POST, instance=series, prefix='rules')
                    transition_formset = SeriesTransitionRuleFormSet(request.POST, instance=series, prefix='transitions')
                    if rule_formset.is_valid():
                        rule_formset.save()
                        transition_formset = SeriesTransitionRuleFormSet(request.POST, instance=series, prefix='transitions')
                        if transition_formset.is_valid():
                            transition_formset.save()
                            messages.success(request, f'Series "{series.name}" created successfully.')
                            return redirect('vaccines:settings_tab', tab='series')
                transaction.set_rollback(True)
            messages.error(request, 'Error in linked products, slot rules, or transition rules. Please check the forms below.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SeriesForm()
        product_formset = SeriesProductFormSet(prefix='products')
        rule_formset = SeriesRuleFormSet(prefix='rules')
        transition_formset = SeriesTransitionRuleFormSet(prefix='transitions')

    return render(request, 'vaccines/series_form.html', {
        'form': form,
        'product_formset': product_formset,
        'rule_formset': rule_formset,
        'transition_formset': transition_formset,
        'title': 'Add New Series',
        'submit_label': 'Create Series',
    })


def series_edit(request, pk):
    series = get_object_or_404(Series, pk=pk)
    if request.method == 'POST':
        form = SeriesForm(request.POST, instance=series)
        product_formset = SeriesProductFormSet(request.POST, instance=series, prefix='products')
        rule_formset = SeriesRuleFormSet(request.POST, instance=series, prefix='rules')
        transition_formset = SeriesTransitionRuleFormSet(request.POST, instance=series, prefix='transitions')
        if form.is_valid() and product_formset.is_valid():
            with transaction.atomic():
                form.save()
                product_formset.save()
                rule_formset = SeriesRuleFormSet(request.POST, instance=series, prefix='rules')
                transition_formset = SeriesTransitionRuleFormSet(request.POST, instance=series, prefix='transitions')
                if rule_formset.is_valid():
                    rule_formset.save()
                    transition_formset = SeriesTransitionRuleFormSet(request.POST, instance=series, prefix='transitions')
                    if transition_formset.is_valid():
                        transition_formset.save()
                        messages.success(request, f'Series "{series.name}" updated successfully.')
                        return redirect('vaccines:settings_tab', tab='series')
                transaction.set_rollback(True)
            messages.error(request, 'Error in slot rules or transition rules. Please check the forms below.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SeriesForm(instance=series)
        product_formset = SeriesProductFormSet(instance=series, prefix='products')
        rule_formset = SeriesRuleFormSet(instance=series, prefix='rules')
        transition_formset = SeriesTransitionRuleFormSet(instance=series, prefix='transitions')

    return render(request, 'vaccines/series_form.html', {
        'form': form,
        'product_formset': product_formset,
        'rule_formset': rule_formset,
        'transition_formset': transition_formset,
        'title': f'Edit Series: {series.name}',
        'submit_label': 'Save Changes',
        'series': series,
    })

def series_delete(request, pk):
    series = get_object_or_404(Series, pk=pk)
    if request.method == 'POST':
        name = series.name
        series.delete()
        messages.success(request, f'Series "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='series')
    return render(request, 'vaccines/confirm_delete.html', {'object': series, 'object_type': 'Series', 'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'series'})})


def dependency_create(request):
    if request.method == 'POST':
        form = DependencyRuleForm(request.POST)
        if form.is_valid():
            dependency = form.save()
            messages.success(request, f'Dependency rule for "{dependency.dependent_series.name}" created successfully.')
            return redirect('vaccines:settings_tab', tab='dependencies')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = DependencyRuleForm()

    return render(request, 'vaccines/dependency_form.html', {'form': form, 'title': 'Add Dependency Rule', 'submit_label': 'Create Rule'})


def dependency_edit(request, pk):
    dependency = get_object_or_404(DependencyRule, pk=pk)
    if request.method == 'POST':
        form = DependencyRuleForm(request.POST, instance=dependency)
        if form.is_valid():
            dependency = form.save()
            messages.success(request, f'Dependency rule for "{dependency.dependent_series.name}" updated successfully.')
            return redirect('vaccines:settings_tab', tab='dependencies')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = DependencyRuleForm(instance=dependency)

    return render(request, 'vaccines/dependency_form.html', {'form': form, 'title': 'Edit Dependency Rule', 'submit_label': 'Save Changes', 'dependency': dependency})


def dependency_delete(request, pk):
    dependency = get_object_or_404(DependencyRule, pk=pk)
    if request.method == 'POST':
        label = str(dependency)
        dependency.delete()
        messages.success(request, f'Dependency rule "{label}" deleted.')
        return redirect('vaccines:settings_tab', tab='dependencies')
    return render(request, 'vaccines/confirm_delete.html', {'object': dependency, 'object_type': 'Dependency Rule', 'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'dependencies'})})



def global_constraint_create(request):
    if request.method == 'POST':
        form = GlobalConstraintRuleForm(request.POST)
        if form.is_valid():
            constraint = form.save()
            messages.success(request, f'Global constraint "{constraint.name}" created successfully.')
            return redirect('vaccines:settings_tab', tab='constraints')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = GlobalConstraintRuleForm()

    return render(request, 'vaccines/constraint_form.html', {'form': form, 'title': 'Add Global Constraint', 'submit_label': 'Create Constraint'})


def global_constraint_edit(request, pk):
    constraint = get_object_or_404(GlobalConstraintRule, pk=pk)
    if request.method == 'POST':
        form = GlobalConstraintRuleForm(request.POST, instance=constraint)
        if form.is_valid():
            constraint = form.save()
            messages.success(request, f'Global constraint "{constraint.name}" updated successfully.')
            return redirect('vaccines:settings_tab', tab='constraints')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = GlobalConstraintRuleForm(instance=constraint)

    return render(request, 'vaccines/constraint_form.html', {'form': form, 'title': f'Edit Global Constraint: {constraint.name}', 'submit_label': 'Save Changes', 'constraint': constraint})


def global_constraint_delete(request, pk):
    constraint = get_object_or_404(GlobalConstraintRule, pk=pk)
    if request.method == 'POST':
        name = constraint.name
        constraint.delete()
        messages.success(request, f'Global constraint "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='constraints')
    return render(request, 'vaccines/confirm_delete.html', {'object': constraint, 'object_type': 'Global Constraint', 'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'constraints'})})
# Legacy Vaccine CRUD

def vaccine_create(request):
    return _redirect_legacy_policy_read_only(request, 'vaccines')


def vaccine_edit(request, pk):
    return _redirect_legacy_policy_read_only(request, 'vaccines')


def vaccine_delete(request, pk):
    return _redirect_legacy_policy_read_only(request, 'vaccines')


# Legacy Group CRUD

def group_create(request):
    return _redirect_legacy_policy_read_only(request, 'groups')


def group_edit(request, pk):
    return _redirect_legacy_policy_read_only(request, 'groups')


def group_delete(request, pk):
    return _redirect_legacy_policy_read_only(request, 'groups')
