from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    CatchupRuleFormSet,
    GroupRuleFormSet,
    ProductForm,
    ScheduleRuleFormSet,
    SeriesForm,
    SeriesProductFormSet,
    SeriesRuleFormSet,
    VaccineForm,
    VaccineGroupForm,
)
from .models import Product, Series, Vaccine, VaccineGroup


LEGACY_TABS = {'vaccines', 'groups'}
NEW_TABS = {'products', 'series', 'guide'}
ALL_TABS = LEGACY_TABS.union(NEW_TABS)


def vaccine_settings(request, tab=None):
    active_tab = tab or request.GET.get('tab', 'products')
    if active_tab not in ALL_TABS:
        active_tab = 'products'

    vaccines = Vaccine.objects.prefetch_related('schedule_rules', 'catchup_rules').all()
    groups = VaccineGroup.objects.prefetch_related('vaccines', 'rules').all()
    products = Product.objects.select_related('vaccine').prefetch_related('series_memberships').all()
    series = Series.objects.prefetch_related('series_products__product__vaccine', 'rules__product__vaccine').all()

    context = {
        'vaccines': vaccines,
        'groups': groups,
        'products': products,
        'series_list': series,
        'active_tab': active_tab,
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

    return render(request, 'vaccines/product_form.html', {
        'form': form,
        'title': 'Add New Product',
        'submit_label': 'Create Product',
    })


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

    return render(request, 'vaccines/product_form.html', {
        'form': form,
        'title': f'Edit Product: {product.vaccine.name}',
        'submit_label': 'Save Changes',
        'product': product,
    })


def product_delete(request, pk):
    product = get_object_or_404(Product.objects.select_related('vaccine'), pk=pk)
    if request.method == 'POST':
        name = product.vaccine.name
        product.delete()
        messages.success(request, f'Product profile "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='products')
    return render(request, 'vaccines/confirm_delete.html', {
        'object': product,
        'object_type': 'Product Profile',
        'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'products'}),
    })


def series_create(request):
    if request.method == 'POST':
        form = SeriesForm(request.POST)
        product_formset = SeriesProductFormSet(request.POST, prefix='products')
        rule_formset = SeriesRuleFormSet(request.POST, prefix='rules')
        if form.is_valid():
            series = form.save()
            product_formset = SeriesProductFormSet(request.POST, instance=series, prefix='products')
            rule_formset = SeriesRuleFormSet(request.POST, instance=series, prefix='rules')
            if product_formset.is_valid() and rule_formset.is_valid():
                product_formset.save()
                rule_formset.save()
                messages.success(request, f'Series "{series.name}" created successfully.')
                return redirect('vaccines:settings_tab', tab='series')
            series.delete()
            messages.error(request, 'Error in series products or series rules. Please check the forms.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SeriesForm()
        product_formset = SeriesProductFormSet(prefix='products')
        rule_formset = SeriesRuleFormSet(prefix='rules')

    return render(request, 'vaccines/series_form.html', {
        'form': form,
        'product_formset': product_formset,
        'rule_formset': rule_formset,
        'title': 'Add New Series',
        'submit_label': 'Create Series',
    })


def series_edit(request, pk):
    series = get_object_or_404(Series, pk=pk)
    if request.method == 'POST':
        form = SeriesForm(request.POST, instance=series)
        product_formset = SeriesProductFormSet(request.POST, instance=series, prefix='products')
        rule_formset = SeriesRuleFormSet(request.POST, instance=series, prefix='rules')
        if form.is_valid() and product_formset.is_valid() and rule_formset.is_valid():
            form.save()
            product_formset.save()
            rule_formset.save()
            messages.success(request, f'Series "{series.name}" updated successfully.')
            return redirect('vaccines:settings_tab', tab='series')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = SeriesForm(instance=series)
        product_formset = SeriesProductFormSet(instance=series, prefix='products')
        rule_formset = SeriesRuleFormSet(instance=series, prefix='rules')

    return render(request, 'vaccines/series_form.html', {
        'form': form,
        'product_formset': product_formset,
        'rule_formset': rule_formset,
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
    return render(request, 'vaccines/confirm_delete.html', {
        'object': series,
        'object_type': 'Series',
        'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'series'}),
    })


# Legacy Vaccine CRUD

def vaccine_create(request):
    if request.method == 'POST':
        form = VaccineForm(request.POST)
        schedule_formset = ScheduleRuleFormSet(request.POST, prefix='schedule')
        catchup_formset = CatchupRuleFormSet(request.POST, prefix='catchup')
        if form.is_valid():
            vaccine = form.save()
            schedule_formset = ScheduleRuleFormSet(request.POST, instance=vaccine, prefix='schedule')
            catchup_formset = CatchupRuleFormSet(request.POST, instance=vaccine, prefix='catchup')
            if schedule_formset.is_valid() and catchup_formset.is_valid():
                schedule_formset.save()
                catchup_formset.save()
                messages.success(request, f'Vaccine "{vaccine.name}" created successfully.')
                return redirect('vaccines:settings_tab', tab='vaccines')
            vaccine.delete()
            messages.error(request, 'Error in schedule or catchup rules. Please check the forms.')
    else:
        form = VaccineForm()
        schedule_formset = ScheduleRuleFormSet(prefix='schedule')
        catchup_formset = CatchupRuleFormSet(prefix='catchup')

    return render(request, 'vaccines/vaccine_form.html', {
        'form': form,
        'schedule_formset': schedule_formset,
        'catchup_formset': catchup_formset,
        'title': 'Add New Vaccine',
        'submit_label': 'Create Vaccine',
    })


def vaccine_edit(request, pk):
    vaccine = get_object_or_404(Vaccine, pk=pk)
    if request.method == 'POST':
        form = VaccineForm(request.POST, instance=vaccine)
        schedule_formset = ScheduleRuleFormSet(request.POST, instance=vaccine, prefix='schedule')
        catchup_formset = CatchupRuleFormSet(request.POST, instance=vaccine, prefix='catchup')
        if form.is_valid() and schedule_formset.is_valid() and catchup_formset.is_valid():
            form.save()
            schedule_formset.save()
            catchup_formset.save()
            messages.success(request, f'Vaccine "{vaccine.name}" updated successfully.')
            return redirect('vaccines:settings_tab', tab='vaccines')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = VaccineForm(instance=vaccine)
        schedule_formset = ScheduleRuleFormSet(instance=vaccine, prefix='schedule')
        catchup_formset = CatchupRuleFormSet(instance=vaccine, prefix='catchup')

    return render(request, 'vaccines/vaccine_form.html', {
        'form': form,
        'schedule_formset': schedule_formset,
        'catchup_formset': catchup_formset,
        'title': f'Edit Vaccine: {vaccine.name}',
        'submit_label': 'Save Changes',
        'vaccine': vaccine,
    })


def vaccine_delete(request, pk):
    vaccine = get_object_or_404(Vaccine, pk=pk)
    if request.method == 'POST':
        name = vaccine.name
        vaccine.delete()
        messages.success(request, f'Vaccine "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='vaccines')
    return render(request, 'vaccines/confirm_delete.html', {
        'object': vaccine,
        'object_type': 'Vaccine',
        'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'vaccines'}),
    })


# Legacy Group CRUD

def group_create(request):
    if request.method == 'POST':
        form = VaccineGroupForm(request.POST)
        rule_formset = GroupRuleFormSet(request.POST, prefix='rules')
        if form.is_valid():
            group = form.save()
            rule_formset = GroupRuleFormSet(request.POST, instance=group, prefix='rules')
            if rule_formset.is_valid():
                rule_formset.save()
                messages.success(request, f'Group "{group.name}" created successfully.')
                return redirect('vaccines:settings_tab', tab='groups')
            group.delete()
            messages.error(request, 'Error in group rules. Please check the forms.')
    else:
        form = VaccineGroupForm()
        rule_formset = GroupRuleFormSet(prefix='rules')

    return render(request, 'vaccines/group_form.html', {
        'form': form,
        'rule_formset': rule_formset,
        'title': 'Add New Vaccine Group',
        'submit_label': 'Create Group',
    })


def group_edit(request, pk):
    group = get_object_or_404(VaccineGroup, pk=pk)
    if request.method == 'POST':
        form = VaccineGroupForm(request.POST, instance=group)
        rule_formset = GroupRuleFormSet(request.POST, instance=group, prefix='rules')
        if form.is_valid() and rule_formset.is_valid():
            form.save()
            rule_formset.save()
            messages.success(request, f'Group "{group.name}" updated successfully.')
            return redirect('vaccines:settings_tab', tab='groups')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = VaccineGroupForm(instance=group)
        rule_formset = GroupRuleFormSet(instance=group, prefix='rules')

    return render(request, 'vaccines/group_form.html', {
        'form': form,
        'rule_formset': rule_formset,
        'title': f'Edit Group: {group.name}',
        'submit_label': 'Save Changes',
        'group': group,
    })


def group_delete(request, pk):
    group = get_object_or_404(VaccineGroup, pk=pk)
    if request.method == 'POST':
        name = group.name
        group.delete()
        messages.success(request, f'Group "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='groups')
    return render(request, 'vaccines/confirm_delete.html', {
        'object': group,
        'object_type': 'Vaccine Group',
        'cancel_href': reverse('vaccines:settings_tab', kwargs={'tab': 'groups'}),
    })
