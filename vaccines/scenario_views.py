"""
Views for the Clinical Scenario Simulator.
"""
import json
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .test_models import TestScenario
from .scenario_runner import ScenarioRunner
from .models import Vaccine


def scenario_create(request):
    vaccines = list(Vaccine.objects.order_by('name').values_list('name', flat=True))
    if request.method == 'POST':
        data = _parse_scenario_form(request.POST)
        scenario = TestScenario.objects.create(**data)
        messages.success(request, f'Scenario "{scenario.name}" created.')
        return redirect('vaccines:settings_tab', tab='scenarios')

    return render(request, 'vaccines/scenario_form.html', {
        'title': 'New Scenario',
        'submit_label': 'Create Scenario',
        'vaccines_json': json.dumps(vaccines),
        'categories': TestScenario.CATEGORY_CHOICES,
    })


def scenario_edit(request, pk):
    scenario = get_object_or_404(TestScenario, pk=pk)
    vaccines = list(Vaccine.objects.order_by('name').values_list('name', flat=True))
    if request.method == 'POST':
        data = _parse_scenario_form(request.POST)
        for key, val in data.items():
            setattr(scenario, key, val)
        scenario.last_status = 'untested'
        scenario.save()
        messages.success(request, f'Scenario "{scenario.name}" updated.')
        return redirect('vaccines:settings_tab', tab='scenarios')

    return render(request, 'vaccines/scenario_form.html', {
        'title': f'Edit: {scenario.name}',
        'submit_label': 'Save Changes',
        'scenario': scenario,
        'vaccines_json': json.dumps(vaccines),
        'categories': TestScenario.CATEGORY_CHOICES,
    })


def scenario_delete(request, pk):
    scenario = get_object_or_404(TestScenario, pk=pk)
    if request.method == 'POST':
        name = scenario.name
        scenario.delete()
        messages.success(request, f'Scenario "{name}" deleted.')
        return redirect('vaccines:settings_tab', tab='scenarios')
    return render(request, 'vaccines/confirm_delete.html', {
        'object': scenario,
        'object_type': 'Test Scenario',
        'cancel_href': '/vaccines/settings/scenarios/',
    })


@require_POST
def scenario_run(request, pk):
    scenario = get_object_or_404(TestScenario, pk=pk)
    result = ScenarioRunner.run(scenario)
    if result['passed']:
        messages.success(request, f'✅ "{scenario.name}" passed all checks.')
    else:
        messages.error(request, f'❌ "{scenario.name}" failed.')
    return redirect('vaccines:settings_tab', tab='scenarios')


@require_POST
def scenario_run_all(request):
    aggregate = ScenarioRunner.run_all()
    messages.info(
        request,
        f'Ran {aggregate["total"]} scenarios: '
        f'{aggregate["passed"]} passed, {aggregate["failed"]} failed.'
    )
    return redirect('vaccines:settings_tab', tab='scenarios')


def scenario_export(request):
    scenarios = TestScenario.objects.filter(active=True)
    data = []
    for s in scenarios:
        entry = {
            'name': s.name,
            'description': s.description,
            'category': s.category,
            'age_days': s.age_days,
            'history': s.history,
        }
        if s.expected_due:
            entry['expected_due'] = s.expected_due
        if s.expected_upcoming:
            entry['expected_upcoming'] = s.expected_upcoming
        if s.expected_missing:
            entry['expected_missing'] = s.expected_missing
        if s.expected_blocked:
            entry['expected_blocked'] = s.expected_blocked
        if s.expected_invalid:
            entry['expected_invalid'] = s.expected_invalid
        data.append(entry)

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json',
    )
    response['Content-Disposition'] = 'attachment; filename="test_scenarios.json"'
    return response


@require_POST
def scenario_import(request):
    if not request.FILES.get('scenario_file'):
        messages.error(request, 'No file provided.')
        return redirect('vaccines:settings_tab', tab='scenarios')

    try:
        content = request.FILES['scenario_file'].read().decode('utf-8')
        data = json.loads(content)
    except Exception as e:
        messages.error(request, f'Invalid file: {e}')
        return redirect('vaccines:settings_tab', tab='scenarios')

    created = 0
    updated = 0
    for entry in data:
        defaults = {
            'description': entry.get('description', ''),
            'category': entry.get('category', 'routine'),
            'age_days': entry['age_days'],
            'history': entry.get('history', []),
            'expected_due': entry.get('expected_due', []),
            'expected_upcoming': entry.get('expected_upcoming', []),
            'expected_missing': entry.get('expected_missing', []),
            'expected_blocked': entry.get('expected_blocked', []),
            'expected_invalid': entry.get('expected_invalid', []),
        }
        _, was_created = TestScenario.objects.update_or_create(
            name=entry['name'], defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    messages.success(request, f'Imported {created} new + {updated} updated scenarios.')
    return redirect('vaccines:settings_tab', tab='scenarios')


def _parse_scenario_form(POST):
    """Parse the scenario form POST data into a dict for model creation."""
    history = []
    i = 0
    while f'history_{i}_vax' in POST:
        vax = POST.get(f'history_{i}_vax', '').strip()
        days_ago = POST.get(f'history_{i}_days_ago', '0')
        elsewhere = POST.get(f'history_{i}_elsewhere') == 'on'
        if vax:
            history.append({
                'vax': vax,
                'days_ago': int(days_ago) if days_ago else 0,
                'administered_elsewhere': elsewhere,
            })
        i += 1

    def _split_list(key):
        val = POST.get(key, '').strip()
        if not val:
            return []
        return [v.strip() for v in val.split(',') if v.strip()]

    expected_invalid = []
    j = 0
    while f'invalid_{j}_vax' in POST:
        vax = POST.get(f'invalid_{j}_vax', '').strip()
        idx = POST.get(f'invalid_{j}_index', '')
        reason = POST.get(f'invalid_{j}_reason', '').strip()
        if vax and idx:
            expected_invalid.append({
                'vax': vax,
                'index': int(idx),
                'reason': reason,
            })
        j += 1

    return {
        'name': POST.get('name', '').strip(),
        'description': POST.get('description', '').strip(),
        'category': POST.get('category', 'routine'),
        'age_days': int(POST.get('age_days', 0)),
        'history': history,
        'expected_due': _split_list('expected_due'),
        'expected_upcoming': _split_list('expected_upcoming'),
        'expected_missing': _split_list('expected_missing'),
        'expected_blocked': _split_list('expected_blocked'),
        'expected_invalid': expected_invalid,
    }
