from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Child, VaccinationRecord
from vaccines.models import Vaccine
from vaccines.engine import VaccinationEngine
from datetime import date

def dashboard(request):
    children = Child.objects.prefetch_related('vaccination_records__vaccine').exclude(id__startswith='__scenario_').all()
    # For MVP, we'll just evaluate everyone. In production, we'd optimize this.
    due_today_list = []
    upcoming_list = []
    completed_list = []
    registered_list = []
    
    for child in children:
        engine = VaccinationEngine(child)
        eval_result = engine.evaluate()
        
        has_pending = (
            eval_result['due_today'] or 
            eval_result['due_but_unavailable'] or 
            eval_result['missing_doses'] or 
            eval_result['upcoming'] or
            eval_result['blocked']
        )
        
        if not has_pending and child.vaccination_records.exists():
            completed_list.append(child)
        
        registered_list.append(child)

        if eval_result['due_today']:
            due_today_list.append({
                'child': child,
                'due_vaccines': eval_result['due_today'],
                'due_ids': [d['vaccine'].id for d in eval_result['due_today']]
            })
        elif eval_result['next_appointment']:
            upcoming_list.append({
                'child': child,
                'date': eval_result['next_appointment']
            })
            
    # sort upcoming
    upcoming_list.sort(key=lambda x: x['date'] if x['date'] else date.max)
    
    context = {
        'due_today': due_today_list,
        'upcoming': upcoming_list[:10],
        'completed': completed_list,
        'registered': registered_list,
        'stats': {'total_children': children.count()}
    }
    return render(request, 'patients/dashboard.html', context)

def register(request):
    if request.method == 'POST':
        child_id = request.POST.get('id')
        if not child_id:
            messages.error(request, "ID is required.")
            return render(request, 'patients/register.html')
            
        name = request.POST.get('name')
        sex = request.POST.get('sex')
        dob = request.POST.get('dob')
        address = request.POST.get('address')
        parents_name = request.POST.get('parents_name')
        contact_info = request.POST.get('contact_info')
        
        child = Child.objects.create(
            id=child_id,
            name=name,
            sex=sex,
            dob=dob,
            address=address,
            parents_name=parents_name,
            contact_info=contact_info
        )
        messages.success(request, f"Registered child {child.name}")
        return redirect('patients:profile', child_id=child.id)
        
    return render(request, 'patients/register.html')

def profile(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    engine = VaccinationEngine(child)
    eval_result = engine.evaluate()
    
    records = child.vaccination_records.all()
    all_vaccines = Vaccine.objects.all()
    
    context = {
        'child': child,
        'records': records,
        'eval': eval_result,
        'vaccines': all_vaccines,
        'due_ids': [d['vaccine'].id for d in eval_result['due_today']]
    }
    return render(request, 'patients/profile.html', context)

def record_dose(request, child_id):
    if request.method == 'POST':
        child = get_object_or_404(Child, id=child_id)
        vaccine_id = request.POST.get('vaccine_id')
        date_given = request.POST.get('date_given') or date.today()
        lot_number = request.POST.get('lot_number')
        administer_site = request.POST.get('administer_site')
        
        vaccine = get_object_or_404(Vaccine, id=vaccine_id)
        
        administered_elsewhere = request.POST.get('administered_elsewhere') == 'on'
        
        VaccinationRecord.objects.create(
            child=child,
            vaccine=vaccine,
            date_given=date_given,
            lot_number=lot_number,
            administer_site=administer_site,
            administered_elsewhere=administered_elsewhere
        )
        messages.success(request, f"Recorded {vaccine.name} for {child.name}")
        return redirect('patients:profile', child_id=child.id)
    return redirect('patients:dashboard')
