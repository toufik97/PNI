from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Vaccine, ScheduleRule, CatchupRule, VaccineGroup, GroupRule
from .forms import (
    VaccineForm, ScheduleRuleFormSet, CatchupRuleFormSet,
    VaccineGroupForm, GroupRuleFormSet,
)


def vaccine_settings(request, tab=None):
    """Main settings page with tabbed view: Vaccines, Groups, Policy Guide."""
    vaccines = Vaccine.objects.prefetch_related('schedule_rules', 'catchup_rules').all()
    groups = VaccineGroup.objects.prefetch_related('vaccines', 'rules').all()
    context = {
        'vaccines': vaccines,
        'groups': groups,
        'active_tab': tab or request.GET.get('tab', 'vaccines'),
    }
    return render(request, 'vaccines/settings.html', context)


# ─── Vaccine CRUD ────────────────────────────────────────────────────────────

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
                return redirect('vaccines:settings')
            else:
                vaccine.delete()  # Rollback if formsets fail
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
            return redirect('vaccines:settings')
        else:
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
        return redirect('vaccines:settings')
    return render(request, 'vaccines/confirm_delete.html', {
        'object': vaccine,
        'object_type': 'Vaccine',
        'cancel_url': 'vaccines:settings',
    })


# ─── Vaccine Group CRUD ─────────────────────────────────────────────────────

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
            else:
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
        else:
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
        'cancel_url': 'vaccines:settings',
    })
