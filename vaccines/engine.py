from datetime import date, timedelta
from typing import Any, Dict, List

from patients.models import Child, VaccinationRecord
from vaccines.models import (
    CatchupRule,
    GroupRule,
    Product,
    ScheduleRule,
    Series,
    SeriesRule,
    SubstitutionRule,
    Vaccine,
    VaccineGroup,
)


class VaccinationEngine:
    def __init__(self, child: Child, evaluation_date: date = None):
        self.child = child
        self.evaluation_date = evaluation_date or date.today()
        self.age_days = (self.evaluation_date - self.child.dob).days
        self.age_months = self.age_days / 30.44
        self.age_years = self.age_days / 365.25
        self.records = list(self.child.vaccination_records.all().order_by('date_given'))
        self.vaccines = Vaccine.objects.all()

    def evaluate(self) -> Dict[str, Any]:
        history_by_vaccine = self._group_history()
        self._validate_history(history_by_vaccine)

        due_today = []
        missing_doses = []
        upcoming_doses = []

        active_series = list(
            Series.objects.filter(active=True).prefetch_related(
                'series_products__product__vaccine',
                'rules__product__vaccine',
            )
        )
        covered_group_ids = set()
        covered_vaccine_names = set()

        for series in active_series:
            series_eval = self._evaluate_series(series, history_by_vaccine)
            if series_eval:
                due_today.extend(series_eval['due_today'])
                missing_doses.extend(series_eval['missing_doses'])
                upcoming_doses.extend(series_eval['upcoming'])

            if series.legacy_group_id:
                covered_group_ids.add(series.legacy_group_id)

            for link in series.series_products.all():
                covered_vaccine_names.add(link.product.vaccine.name)

        groups = VaccineGroup.objects.prefetch_related('vaccines', 'rules').all()
        grouped_vaccine_names = set(covered_vaccine_names)

        for group in groups:
            if group.id in covered_group_ids:
                for vaccine in group.vaccines.all():
                    grouped_vaccine_names.add(vaccine.name)
                continue

            group_eval = self._evaluate_vaccine_group(group, history_by_vaccine)
            if group_eval:
                due_today.extend(group_eval['due_today'])
                missing_doses.extend(group_eval['missing_doses'])
                upcoming_doses.extend(group_eval['upcoming'])
            for vaccine in group.vaccines.all():
                grouped_vaccine_names.add(vaccine.name)

        for vaccine in self.vaccines:
            if vaccine.name in grouped_vaccine_names:
                continue

            v_history = [record for record in history_by_vaccine.get(vaccine.id, []) if not record.invalid_flag]
            prior_doses = len(v_history)

            applicable_catchup = CatchupRule.objects.filter(
                vaccine=vaccine,
                min_age_days__lte=self.age_days,
                max_age_days__gte=self.age_days,
                prior_doses=prior_doses,
            ).first()

            if applicable_catchup:
                if prior_doses < applicable_catchup.doses_required:
                    last_dose_date = v_history[-1].date_given if v_history else None
                    standard_rule = ScheduleRule.objects.filter(
                        vaccine=vaccine,
                        dose_number=prior_doses + 1,
                    ).first()
                    dose_val = applicable_catchup.dose_amount or (standard_rule.dose_amount if standard_rule else None)

                    if last_dose_date:
                        days_since_last = (self.evaluation_date - last_dose_date).days
                        if days_since_last >= applicable_catchup.min_interval_days:
                            due_today.append({
                                'vaccine': vaccine,
                                'dose_amount': dose_val,
                                'dose_number': prior_doses + 1,
                            })
                            missing_doses.append({'vaccine': vaccine, 'dose_number': prior_doses + 1})
                        else:
                            next_due_date = last_dose_date + timedelta(days=applicable_catchup.min_interval_days)
                            upcoming_doses.append((vaccine, next_due_date, prior_doses + 1))
                    else:
                        due_today.append({
                            'vaccine': vaccine,
                            'dose_amount': dose_val,
                            'dose_number': prior_doses + 1,
                        })
                        missing_doses.append({'vaccine': vaccine, 'dose_number': prior_doses + 1})
                continue

            next_dose_num = prior_doses + 1
            rule = ScheduleRule.objects.filter(vaccine=vaccine, dose_number=next_dose_num).first()
            if not rule:
                continue

            if prior_doses == 0:
                target_date = self.child.dob + timedelta(days=rule.recommended_age_days)
            else:
                last_dose_date = v_history[-1].date_given
                interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
                age_floor_date = self.child.dob + timedelta(days=rule.min_age_days)
                target_date = max(interval_date, age_floor_date)

            overdue_child_age = rule.overdue_age_days if rule.overdue_age_days is not None else rule.recommended_age_days
            overdue_date = self.child.dob + timedelta(days=overdue_child_age)
            dose_val = rule.dose_amount

            if self.evaluation_date > overdue_date:
                missing_doses.append({'vaccine': vaccine, 'dose_number': next_dose_num})

            if self.evaluation_date >= target_date:
                if rule.max_age_days and self.age_days > rule.max_age_days:
                    continue
                due_today.append({
                    'vaccine': vaccine,
                    'dose_amount': dose_val,
                    'dose_number': next_dose_num,
                })
            else:
                upcoming_doses.append((vaccine, target_date, next_dose_num))

        recent_live_doses = [
            record for record in self.records
            if record.vaccine.live and not record.invalid_flag and (self.evaluation_date - record.date_given).days < 28
        ]

        if recent_live_doses:
            latest_live_date = max(record.date_given for record in recent_live_doses)
            safe_date = latest_live_date + timedelta(days=28)

            non_deferred_due = []
            for item in due_today:
                vaccine = item['vaccine'] if isinstance(item, dict) else item
                if vaccine.live:
                    is_compatible = True
                    for record in recent_live_doses:
                        gap = (self.evaluation_date - record.date_given).days
                        if gap == 0:
                            if not vaccine.compatible_live_vaccines.filter(id=record.vaccine.id).exists():
                                is_compatible = False
                        else:
                            if not vaccine.compatible_live_vaccines.filter(id=record.vaccine.id).exists():
                                is_compatible = False

                        if not is_compatible:
                            break

                    if not is_compatible:
                        dose_num = item.get('dose_number') if isinstance(item, dict) else None
                        upcoming_doses.append((vaccine, safe_date, dose_num))
                        continue

                non_deferred_due.append(item)
            due_today = non_deferred_due

        final_due = []
        for item in due_today:
            if isinstance(item, dict):
                final_due.append(item)
            else:
                final_due.append({'vaccine': item, 'dose_amount': None, 'dose_number': None})

        next_appointment = min([item[1] for item in upcoming_doses]) if upcoming_doses else None

        return {
            'due_today': final_due,
            'missing_doses': missing_doses,
            'next_appointment': next_appointment,
            'upcoming': upcoming_doses,
        }

    def _group_history(self) -> Dict[str, List[VaccinationRecord]]:
        history = {}
        for record in self.records:
            history.setdefault(record.vaccine.id, []).append(record)
        return history

    def _flag_invalid(self, record: VaccinationRecord, reason_code: str, message: str):
        record.invalid_flag = True
        record.invalid_reason = reason_code
        record.notes = message
        record.save()

    def _validate_history(self, history_by_vaccine: Dict[str, List[VaccinationRecord]]):
        from patients.models import VaccinationRecord as VR

        series_vaccine_ids = set(
            Product.objects.filter(series_memberships__active=True).values_list('vaccine_id', flat=True)
        )
        grouped_vaccine_ids = set(
            VaccineGroup.objects.values_list('vaccines__id', flat=True)
        )
        skip_vaccine_ids = {vaccine_id for vaccine_id in series_vaccine_ids.union(grouped_vaccine_ids) if vaccine_id}

        for vaccine_id, records in history_by_vaccine.items():
            if vaccine_id in skip_vaccine_ids:
                continue

            valid_records = []
            for record in records:
                if record.invalid_flag:
                    continue

                age_at_dose = (record.date_given - self.child.dob).days
                dose_num = len(valid_records) + 1
                rule = ScheduleRule.objects.filter(vaccine_id=vaccine_id, dose_number=dose_num).first()

                if rule:
                    if age_at_dose < rule.min_age_days:
                        age_months = round(age_at_dose / 30.44, 1)
                        min_months = round(rule.min_age_days / 30.44, 1)
                        self._flag_invalid(
                            record,
                            VR.REASON_TOO_EARLY,
                            f"Too early: {record.vaccine.name} dose {dose_num} requires min age "
                            f"{min_months} months. Child was {age_months} months old.",
                        )
                        continue

                    if rule.max_age_days and age_at_dose > rule.max_age_days:
                        age_months = round(age_at_dose / 30.44, 1)
                        max_months = round(rule.max_age_days / 30.44, 1)
                        self._flag_invalid(
                            record,
                            VR.REASON_TOO_LATE,
                            f"Too late: {record.vaccine.name} dose {dose_num} is not valid after "
                            f"{max_months} months. Child was {age_months} months old.",
                        )
                        continue

                    if valid_records and rule.min_interval_days:
                        days_since = (record.date_given - valid_records[-1].date_given).days
                        if days_since < rule.min_interval_days:
                            self._flag_invalid(
                                record,
                                VR.REASON_INTERVAL,
                                f"Too soon: {record.vaccine.name} dose {dose_num} requires "
                                f"{rule.min_interval_days} days after previous dose. "
                                f"Only {days_since} days elapsed.",
                            )
                            continue

                valid_records.append(record)

        valid_live = []
        for record in self.records:
            if not record.vaccine.live or record.invalid_flag:
                continue

            if valid_live:
                previous = valid_live[-1]
                gap = (record.date_given - previous.date_given).days
                if gap < 28:
                    is_compatible = record.vaccine.compatible_live_vaccines.filter(id=previous.vaccine.id).exists()
                    if gap == 0 and is_compatible:
                        pass
                    else:
                        self._flag_invalid(
                            record,
                            VR.REASON_INTERVAL,
                            f"Live vax conflict: {record.vaccine.name} given {gap} days after live "
                            f"{previous.vaccine.name}. Standard protocol requires 28-day gap.",
                        )
                        continue

            valid_live.append(record)

    def _evaluate_series(self, series: Series, history_by_vaccine: Dict[str, List[VaccinationRecord]]) -> Dict[str, Any]:
        from patients.models import VaccinationRecord as VR

        result = {'due_today': [], 'missing_doses': [], 'upcoming': []}
        series_vaccine_ids = {
            link.product.vaccine_id for link in series.series_products.all()
        }
        if not series_vaccine_ids:
            return result

        series_records = []
        for vaccine_id in series_vaccine_ids:
            if vaccine_id in history_by_vaccine:
                series_records.extend([
                    record for record in history_by_vaccine[vaccine_id]
                    if not record.invalid_flag
                ])
        series_records.sort(key=lambda record: record.date_given)

        valid_records = []
        for record in series_records:
            age_at_dose = (record.date_given - self.child.dob).days

            if valid_records:
                previous = valid_records[-1]
                days_since = (record.date_given - previous.date_given).days
                if days_since < series.min_valid_interval_days:
                    self._flag_invalid(
                        record,
                        VR.REASON_INTERVAL,
                        f"Too soon: Must wait {series.min_valid_interval_days} days between "
                        f"{series.name} doses. Only {days_since} days elapsed since last dose.",
                    )
                    continue

            expected_rule = series.rules.filter(
                prior_valid_doses=len(valid_records),
                min_age_days__lte=age_at_dose,
            ).order_by('-min_age_days').first()

            if expected_rule:
                if expected_rule.max_age_days and age_at_dose > expected_rule.max_age_days:
                    age_months = round(age_at_dose / 30.44, 1)
                    max_months = round(expected_rule.max_age_days / 30.44, 1)
                    self._flag_invalid(
                        record,
                        VR.REASON_TOO_LATE,
                        f"Too late: {record.vaccine.name} is not valid after {max_months} months "
                        f"for slot {expected_rule.slot_number}. Child was {age_months} months old.",
                    )
                    continue

                if record.vaccine.id != expected_rule.product.vaccine_id:
                    age_months = round(age_at_dose / 30.44, 1)
                    self._flag_invalid(
                        record,
                        VR.REASON_WRONG_VACCINE,
                        f"Wrong vaccine: {record.vaccine.name} was given at {age_months} months, "
                        f"but {expected_rule.product.vaccine.name} is required for slot "
                        f"{expected_rule.slot_number}.",
                    )
                    continue
            else:
                future_rule = series.rules.filter(
                    prior_valid_doses=len(valid_records),
                    min_age_days__gt=age_at_dose,
                ).order_by('min_age_days').first()
                if future_rule:
                    age_months = round(age_at_dose / 30.44, 1)
                    min_months = round(future_rule.min_age_days / 30.44, 1)
                    self._flag_invalid(
                        record,
                        VR.REASON_TOO_EARLY,
                        f"Too early: {record.vaccine.name} slot {future_rule.slot_number} requires min age "
                        f"{min_months} months. Child was {age_months} months old.",
                    )
                    continue

            valid_records.append(record)

        prior_doses = len(valid_records)
        last_dose_date = valid_records[-1].date_given if valid_records else None

        rules = series.rules.filter(
            prior_valid_doses=prior_doses,
            min_age_days__lte=self.age_days,
        ).select_related('product__vaccine')
        valid_rules = [rule for rule in rules if rule.max_age_days is None or self.age_days <= rule.max_age_days]

        if not valid_rules:
            future_rules = series.rules.filter(
                prior_valid_doses=prior_doses,
                min_age_days__gt=self.age_days,
            ).select_related('product__vaccine').order_by('min_age_days')
            if future_rules.exists():
                next_rule = future_rules.first()
                target_age_days = next_rule.recommended_age_days if prior_doses == 0 else next_rule.min_age_days
                target_date = self.child.dob + timedelta(days=target_age_days)
                if last_dose_date:
                    interval_date = last_dose_date + timedelta(days=next_rule.min_interval_days)
                    age_floor_date = self.child.dob + timedelta(days=next_rule.min_age_days)
                    target_date = max(target_date, interval_date, age_floor_date)
                result['upcoming'].append((next_rule.product.vaccine, target_date, next_rule.slot_number))
            return result

        rule = valid_rules[-1]
        vaccine_to_give = rule.product.vaccine

        if prior_doses == 0:
            target_date = self.child.dob + timedelta(days=rule.recommended_age_days)
        elif last_dose_date:
            interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
            age_floor_date = self.child.dob + timedelta(days=rule.min_age_days)
            target_date = max(interval_date, age_floor_date)
        else:
            target_date = self.child.dob + timedelta(days=rule.min_age_days)

        dose_val = rule.dose_amount
        overdue_age = rule.overdue_age_days if rule.overdue_age_days is not None else rule.recommended_age_days
        overdue_date = self.child.dob + timedelta(days=overdue_age)

        if self.evaluation_date > overdue_date:
            result['missing_doses'].append({
                'vaccine': vaccine_to_give,
                'dose_number': rule.slot_number,
            })

        if self.evaluation_date >= target_date:
            result['due_today'].append({
                'vaccine': vaccine_to_give,
                'dose_amount': dose_val,
                'dose_number': rule.slot_number,
            })
        else:
            result['upcoming'].append((vaccine_to_give, target_date, rule.slot_number))

        return result

    def _evaluate_vaccine_group(self, group: VaccineGroup, history_by_vaccine: Dict[str, List[VaccinationRecord]]) -> Dict[str, Any]:
        result = {'due_today': [], 'missing_doses': [], 'upcoming': []}

        group_records = []
        for vaccine in group.vaccines.all():
            if vaccine.id in history_by_vaccine:
                group_records.extend([
                    record for record in history_by_vaccine[vaccine.id]
                    if not record.invalid_flag
                ])

        group_records.sort(key=lambda record: record.date_given)

        from patients.models import VaccinationRecord as VR

        valid_group_records = []
        for index, record in enumerate(group_records):
            age_at_dose = (record.date_given - self.child.dob).days

            if index > 0 and valid_group_records:
                previous = valid_group_records[-1]
                days_since = (record.date_given - previous.date_given).days
                if days_since < group.min_valid_interval_days:
                    self._flag_invalid(
                        record,
                        VR.REASON_INTERVAL,
                        f"Too soon: Must wait {group.min_valid_interval_days} days between "
                        f"{group.name} doses. Only {days_since} days elapsed since last dose.",
                    )
                    continue

            expected_rule = group.rules.filter(
                prior_doses=len(valid_group_records),
                min_age_days__lte=age_at_dose,
            ).order_by('-min_age_days').first()

            if expected_rule:
                if expected_rule.max_age_days and age_at_dose > expected_rule.max_age_days:
                    age_months = round(age_at_dose / 30.44, 1)
                    max_months = round(expected_rule.max_age_days / 30.44, 1)
                    self._flag_invalid(
                        record,
                        VR.REASON_TOO_LATE,
                        f"Too late: {record.vaccine.name} is not valid after {max_months} months for dose "
                        f"{len(valid_group_records) + 1}. Child was {age_months} months old.",
                    )
                    continue

                if record.vaccine.id != expected_rule.vaccine_to_give.id:
                    age_months = round(age_at_dose / 30.44, 1)
                    self._flag_invalid(
                        record,
                        VR.REASON_WRONG_VACCINE,
                        f"Wrong vaccine: {record.vaccine.name} was given at {age_months} months, but "
                        f"{expected_rule.vaccine_to_give.name} is required at this age for dose "
                        f"{len(valid_group_records) + 1}.",
                    )
                    continue

            valid_group_records.append(record)

        prior_doses = len(valid_group_records)
        last_dose_date = valid_group_records[-1].date_given if valid_group_records else None

        rules = group.rules.filter(
            prior_doses=prior_doses,
            min_age_days__lte=self.age_days,
        )
        valid_rules = [rule for rule in rules if rule.max_age_days is None or self.age_days <= rule.max_age_days]
        if not valid_rules:
            future_rules = group.rules.filter(
                prior_doses=prior_doses,
                min_age_days__gt=self.age_days,
            ).order_by('min_age_days')
            if future_rules.exists():
                next_rule = future_rules.first()
                target_date = self.child.dob + timedelta(days=next_rule.min_age_days)
                if last_dose_date:
                    interval_date = last_dose_date + timedelta(days=next_rule.min_interval_days)
                    target_date = max(target_date, interval_date)

                result['upcoming'].append((next_rule.vaccine_to_give, target_date, prior_doses + 1))
            return result

        rule = valid_rules[-1]
        vaccine_to_give = rule.vaccine_to_give
        standard_rule = ScheduleRule.objects.filter(
            vaccine=vaccine_to_give,
            dose_number=prior_doses + 1,
        ).first()

        if prior_doses == 0 and standard_rule:
            target_date = self.child.dob + timedelta(days=standard_rule.recommended_age_days)
        elif last_dose_date:
            interval_date = last_dose_date + timedelta(days=rule.min_interval_days)
            age_floor = standard_rule.min_age_days if standard_rule else rule.min_age_days
            age_floor_date = self.child.dob + timedelta(days=age_floor)
            target_date = max(interval_date, age_floor_date)
        else:
            target_date = self.child.dob + timedelta(days=rule.min_age_days)

        dose_val = rule.dose_amount or (standard_rule.dose_amount if standard_rule else None)
        overdue_age = rule.max_age_days
        if standard_rule:
            overdue_age = (
                standard_rule.overdue_age_days
                if standard_rule.overdue_age_days is not None else standard_rule.recommended_age_days
            )

        overdue_date = self.child.dob + timedelta(days=overdue_age) if overdue_age is not None else target_date

        if self.evaluation_date > overdue_date:
            result['missing_doses'].append({
                'vaccine': vaccine_to_give,
                'dose_number': prior_doses + 1,
            })

        if self.evaluation_date >= target_date:
            result['due_today'].append({
                'vaccine': vaccine_to_give,
                'dose_amount': dose_val,
                'dose_number': prior_doses + 1,
            })
        else:
            result['upcoming'].append((vaccine_to_give, target_date, prior_doses + 1))

        return result

