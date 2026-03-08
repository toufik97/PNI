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

            # Clinical Target Date
            if prior_doses == 0:
                target_date = self.child.dob + timedelta(days=rule.recommended_age_days)
            else:
                last_dose_date = v_history[-1].date_given
                interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
                age_floor_date = self.child.dob + timedelta(days=rule.min_age_days)
                target_date = max(interval_date, age_floor_date)

            # 1. Missing? (Strictly greater than target date)
            if self.evaluation_date > target_date:
                missing_doses.append(vaccine)
            
            # 2. Due Today?
            if self.evaluation_date >= target_date:
                # Still respect max_age if it exists
                if rule.max_age_days and self.age_days > rule.max_age_days:
                    continue 
                due_today.append(vaccine)
            else:
                # 3. Upcoming
                upcoming_doses.append((vaccine, target_date))



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

    def _flag_invalid(self, record: VaccinationRecord, reason_code: str, message: str):
        """Consistently flag a record as invalid with a structured reason and human-readable note."""
        record.invalid_flag = True
        record.invalid_reason = reason_code
        record.notes = message
        record.save()

    def _validate_history(self, history_by_vaccine: Dict[str, List[VaccinationRecord]]):
        """Strictly validates all standard (non-grouped) vaccine records against ScheduleRules."""
        from patients.models import VaccinationRecord as VR
        grouped_vaccine_ids = set()
        for group in VaccineGroup.objects.prefetch_related('vaccines').all():
            for v in group.vaccines.all():
                grouped_vaccine_ids.add(v.id)

        for vaccine_id, records in history_by_vaccine.items():
            valid_records = []
            for record in records:
                if record.invalid_flag:
                    continue  # Already flagged, skip

                age_at_dose = (record.date_given - self.child.dob).days
                dose_num = len(valid_records) + 1
                rule = ScheduleRule.objects.filter(vaccine_id=vaccine_id, dose_number=dose_num).first()

                if rule:
                    # Check: too early (min age)
                    if age_at_dose < rule.min_age_days:
                        age_months = round(age_at_dose / 30.44, 1)
                        min_months = round(rule.min_age_days / 30.44, 1)
                        self._flag_invalid(
                            record, VR.REASON_TOO_EARLY,
                            f"Too early: {record.vaccine.name} dose {dose_num} requires min age "
                            f"{min_months} months. Child was {age_months} months old."
                        )
                        continue

                    # Check: too late (max age)
                    if rule.max_age_days and age_at_dose > rule.max_age_days:
                        age_months = round(age_at_dose / 30.44, 1)
                        max_months = round(rule.max_age_days / 30.44, 1)
                        self._flag_invalid(
                            record, VR.REASON_TOO_LATE,
                            f"Too late: {record.vaccine.name} dose {dose_num} is not valid after "
                            f"{max_months} months. Child was {age_months} months old."
                        )
                        continue

                    # Check: interval too short
                    if valid_records and rule.min_interval_days:
                        days_since = (record.date_given - valid_records[-1].date_given).days
                        if days_since < rule.min_interval_days:
                            self._flag_invalid(
                                record, VR.REASON_INTERVAL,
                                f"Too soon: {record.vaccine.name} dose {dose_num} requires "
                                f"{rule.min_interval_days} days after previous dose. "
                                f"Only {days_since} days elapsed."
                            )
                            continue

                valid_records.append(record)

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
        
        # 2. Strict group validation — interval, max age, wrong vaccine type
        from patients.models import VaccinationRecord as VR
        valid_group_records = []
        for i, record in enumerate(group_records):
            age_at_dose = (record.date_given - self.child.dob).days

            # Check interval between consecutive group doses
            if i > 0 and valid_group_records:
                prev_record = valid_group_records[-1]
                days_since = (record.date_given - prev_record.date_given).days
                if days_since < group.min_valid_interval_days:
                    self._flag_invalid(
                        record, VR.REASON_INTERVAL,
                        f"Too soon: Must wait {group.min_valid_interval_days} days between "
                        f"{group.name} doses. Only {days_since} days elapsed since last dose."
                    )
                    continue

            # Check what vaccine the rule says should have been given at this dose number & age
            expected_rule = group.rules.filter(
                prior_doses=len(valid_group_records),
                min_age_days__lte=age_at_dose
            ).order_by('-min_age_days').first()

            if expected_rule:
                # max_age check: was this dose given after it should have stopped? (Policy layer)
                if expected_rule.max_age_days and age_at_dose > expected_rule.max_age_days:
                    age_months = round(age_at_dose / 30.44, 1)
                    max_months = round(expected_rule.max_age_days / 30.44, 1)
                    self._flag_invalid(
                        record, VR.REASON_TOO_LATE,
                        f"Too late: {record.vaccine.name} is not valid after "
                        f"{max_months} months for dose {len(valid_group_records)+1}. "
                        f"Child was {age_months} months old."
                    )
                    continue

                # Wrong vaccine type check (Policy layer)
                if record.vaccine.id != expected_rule.vaccine_to_give.id:
                    age_months = round(age_at_dose / 30.44, 1)
                    self._flag_invalid(
                        record, VR.REASON_WRONG_VACCINE,
                        f"Wrong vaccine: {record.vaccine.name} was given at {age_months} months, "
                        f"but {expected_rule.vaccine_to_give.name} is required at this age for dose "
                        f"{len(valid_group_records)+1}."
                    )
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
                # Target date is max of age floor and interval
                target_date = self.child.dob + timedelta(days=next_rule.min_age_days)
                if last_dose_date:
                    interval_date = last_dose_date + timedelta(days=next_rule.min_interval_days)
                    target_date = max(target_date, interval_date)
                
                res['upcoming'].append((next_rule.vaccine_to_give, target_date))
            return res

            
        rule = valid_rules[-1] # Take the most specific one (highest min_age_days = narrowest age bracket)
        
        # 4. Schedule based on rule
        vaccine_to_give = rule.vaccine_to_give

        
        # Get recommended age from standard rule for Dose 1
        standard_rule = ScheduleRule.objects.filter(
            vaccine=vaccine_to_give, 
            dose_number=prior_doses + 1
        ).first()
        
        # Clinical Target Date
        if prior_doses == 0 and standard_rule:
            target_date = self.child.dob + timedelta(days=standard_rule.recommended_age_days)
        elif last_dose_date:
            interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
            # Use standard rule min_age_days if available for safety floor
            age_floor = standard_rule.min_age_days if standard_rule else rule.min_age_days
            age_floor_date = self.child.dob + timedelta(days=age_floor)
            target_date = max(interval_date, age_floor_date)
        else:
            # Fallback for catch-up rules with 0 doses
            target_date = self.child.dob + timedelta(days=rule.min_age_days)


        # 1. Missing? (Strictly greater than target)
        if self.evaluation_date > target_date:
            res['missing_doses'].append(vaccine_to_give)

        # 2. Due Today?
        if self.evaluation_date >= target_date:
            res['due_today'].append(vaccine_to_give)
        else:
            # 3. Upcoming
            res['upcoming'].append((vaccine_to_give, target_date))
                
        return res
