from datetime import date, timedelta
from typing import List, Dict, Any

# Note: imported as local alias just to fake it for the IDE if needed, but we'll import correct paths:
from patients.models import Child, VaccinationRecord
from vaccines.models import Vaccine, ScheduleRule, CatchupRule, SubstitutionRule, VaccineGroup, GroupRule

class VaccinationEngine:
    def __init__(self, child: Child, evaluation_date: date = None):
        self.child = child
        self.evaluation_date = evaluation_date or date.today()
        self.age_days = (self.evaluation_date - self.child.dob).days
        self.age_months = self.age_days / 30.44  # Approx months
        self.age_years = self.age_days / 365.25  # Approx years
        self.records = list(self.child.vaccination_records.all().order_by('date_given'))
        self.vaccines = Vaccine.objects.all()
    
    def evaluate(self) -> Dict[str, Any]:
        """
        Returns a comprehensive evaluation for the child:
        - valid_doses
        - invalid_doses
        - due_today
        - missing_doses
        - next_appointment
        """
        history_by_vaccine = self._group_history()
        
        # 1. Validate past doses
        self._validate_history(history_by_vaccine)

        due_today = []
        missing_doses = []
        upcoming_doses = []

        # 1. Process Dynamic Vaccine Groups
        groups = VaccineGroup.objects.prefetch_related('vaccines', 'rules').all()
        grouped_vaccine_names = set()

        for group in groups:
            group_eval = self._evaluate_vaccine_group(group, history_by_vaccine)
            if group_eval:
                due_today.extend(group_eval['due_today'])
                missing_doses.extend(group_eval['missing_doses'])
                upcoming_doses.extend(group_eval['upcoming'])
            for v in group.vaccines.all():
                grouped_vaccine_names.add(v.name)
        
        # 2. Process Standard Single Vaccines
        for vaccine in self.vaccines:
            if vaccine.name in grouped_vaccine_names:
                continue # Handled by group logic

            v_history = [r for r in history_by_vaccine.get(vaccine.id, []) if not r.invalid_flag]
            prior_doses = len(v_history)
            
            # Check catch-up first as they override standard schedule
            applicable_catchup = CatchupRule.objects.filter(
                vaccine=vaccine,
                min_age_days__lte=self.age_days,
                max_age_days__gte=self.age_days,
                prior_doses=prior_doses
            ).first()

            if applicable_catchup:
                if prior_doses < applicable_catchup.doses_required:
                    # Due for catchup dose
                    last_dose_date = v_history[-1].date_given if v_history else None
                    if last_dose_date:
                        days_since_last = (self.evaluation_date - last_dose_date).days
                        if days_since_last >= applicable_catchup.min_interval_days:
                            due_today.append(vaccine)
                            missing_doses.append(vaccine)
                        else:
                            next_due_date = last_dose_date + timedelta(days=applicable_catchup.min_interval_days)
                            upcoming_doses.append((vaccine, next_due_date))
                    else:
                        due_today.append(vaccine)
                        missing_doses.append(vaccine)
                continue

            # Standard Routine Schedule Check
            next_dose_num = prior_doses + 1
            rule = ScheduleRule.objects.filter(vaccine=vaccine, dose_number=next_dose_num).first()
            if not rule:
                continue # Schedule complete or no rule

            if self.age_days > rule.recommended_age_days:
                missing_doses.append(vaccine)
            
            # Can we give it today?
            if self.age_days >= rule.min_age_days:
                if rule.max_age_days and self.age_days > rule.max_age_days:
                    continue # Too old for this routine dose
                
                last_dose_date = v_history[-1].date_given if v_history else None
                if last_dose_date:
                    days_since_last = (self.evaluation_date - last_dose_date).days
                    if days_since_last >= rule.min_interval_days:
                        due_today.append(vaccine)
                    else:
                        next_due_date = last_dose_date + timedelta(days=rule.min_interval_days)
                        upcoming_doses.append((vaccine, next_due_date))
                else:
                    due_today.append(vaccine)
            else:
                child_dob = self.child.dob
                next_due_date = child_dob + timedelta(days=rule.min_age_days)
                upcoming_doses.append((vaccine, next_due_date))

        # Check live vaccines same-day compatibility (simplified MVP: 28 days interval if not given same day)
        due_today_live = [v for v in due_today if v.live]
        recent_live_doses = [
            r for r in self.records 
            if r.vaccine.live and not r.invalid_flag and (self.evaluation_date - r.date_given).days < 28
        ]
        
        # If a live vaccine was given recently (< 28 days) and not today, we cannot give another live vaccine today
        if recent_live_doses:
            due_today = [v for v in due_today if not (v.live and v in due_today_live)]
        
        next_appointment = min([d[1] for d in upcoming_doses]) if upcoming_doses else None

        return {
            'due_today': list(set(due_today)),
            'missing_doses': list(set(missing_doses)),
            'next_appointment': next_appointment,
            'upcoming': upcoming_doses
        }

    def _group_history(self) -> Dict[str, List[VaccinationRecord]]:
        history = {}
        for r in self.records:
            history.setdefault(r.vaccine.id, []).append(r)
        return history

    def _validate_history(self, history_by_vaccine: Dict[str, List[VaccinationRecord]]):
        for vaccine_id, records in history_by_vaccine.items():
            valid_count = 0
            for i, record in enumerate(records):
                if record.invalid_flag:
                    continue # Already flagged
                
                # Check min age and interval based on valid count
                rule = ScheduleRule.objects.filter(vaccine_id=vaccine_id, dose_number=valid_count + 1).first()
                if not rule:
                    continue # Maybe catchup or extra dose; ignore for routine strict validation currently
                
                age_at_dose = (record.date_given - self.child.dob).days
                if age_at_dose < rule.min_age_days:
                    record.invalid_flag = True
                    record.notes = f"Too early: min age {rule.min_age_days} days. " + (record.notes or "")
                    record.save()
                    continue
                
                    if prev_valid:
                        days_since_prev = (record.date_given - prev_valid[-1].date_given).days
                        
                        # Groups handle their own invalidation in _evaluate_vaccine_group
                        is_grouped = VaccineGroup.objects.filter(vaccines=record.vaccine).exists()
                        if is_grouped:
                            valid_count += 1
                            continue
                            
                        if days_since_prev < rule.min_interval_days:
                            record.invalid_flag = True
                            record.notes = f"Invalid interval: requires {rule.min_interval_days} days. " + (record.notes or "")
                            record.save()
                            continue
                valid_count += 1

    def _get_vaccine_by_name(self, name: str) -> Vaccine:
        for v in self.vaccines:
            if v.name == name:
                return v
        return None

    def _evaluate_vaccine_group(self, group: VaccineGroup, history_by_vaccine: Dict[str, List[VaccinationRecord]]) -> Dict[str, Any]:
        """
        Evaluates dynamic rules for a family of interrelated vaccines.
        """
        res = {'due_today': [], 'missing_doses': [], 'upcoming': []}

        # 1. Aggregate group doses
        group_records = []
        for v in group.vaccines.all():
            if v.id in history_by_vaccine:
                group_records.extend([r for r in history_by_vaccine[v.id] if not r.invalid_flag])
        
        group_records.sort(key=lambda x: x.date_given)
        
        # 2. Invalidate doses given too early
        valid_group_records = []
        for i, record in enumerate(group_records):
            if i > 0:
                prev_record = valid_group_records[-1]
                days_since = (record.date_given - prev_record.date_given).days
                if days_since < group.min_valid_interval_days:
                    record.invalid_flag = True
                    record.notes = f"Dose given < {group.min_valid_interval_days} days after previous group vaccine. " + (record.notes or "")
                    record.save()
                    continue
            valid_group_records.append(record)
            
        prior_doses = len(valid_group_records)
        last_dose_date = valid_group_records[-1].date_given if valid_group_records else None
        days_since_last = (self.evaluation_date - last_dose_date).days if last_dose_date else None
        
        # 3. Find matching rule
        rules = group.rules.filter(
            prior_doses=prior_doses,
            min_age_days__lte=self.age_days
        )
        # Apply max_age_days if provided
        valid_rules = [r for r in rules if r.max_age_days is None or self.age_days <= r.max_age_days]
        if not valid_rules:
            # No rule matches at this age. Look ahead for the next future rule
            # (e.g. child is 17mo with 3 doses — the rule kicks in at 18mo)
            future_rules = group.rules.filter(
                prior_doses=prior_doses,
                min_age_days__gt=self.age_days
            ).order_by('min_age_days')
            if future_rules.exists():
                next_rule = future_rules.first()
                next_eligible_date = self.child.dob + timedelta(days=next_rule.min_age_days)
                # Also respect the interval from the last dose
                if last_dose_date:
                    interval_date = last_dose_date + timedelta(days=next_rule.min_interval_days)
                    next_eligible_date = max(next_eligible_date, interval_date)
                res['upcoming'].append((next_rule.vaccine_to_give, next_eligible_date))
            return res
            
        rule = valid_rules[-1] # Take the most specific one (highest min_age_days = narrowest age bracket)
        
        # 4. Schedule based on rule
        vaccine_to_give = rule.vaccine_to_give
        min_interval_days = rule.min_interval_days
        
        if last_dose_date:
            if days_since_last >= min_interval_days:
                res['due_today'].append(vaccine_to_give)
                res['missing_doses'].append(vaccine_to_give)
            else:
                next_date = last_dose_date + timedelta(days=min_interval_days)
                res['upcoming'].append((vaccine_to_give, next_date))
        else:
            # First dose (or intervals don't apply)
            if self.age_days >= rule.min_age_days:
                res['due_today'].append(vaccine_to_give)
                res['missing_doses'].append(vaccine_to_give)
            else:
                next_date = self.child.dob + timedelta(days=rule.min_age_days)
                res['upcoming'].append((vaccine_to_give, next_date))
                
        return res
