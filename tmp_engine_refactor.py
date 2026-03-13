import re

with open('c:/Users/admiralTOUFIK/PNI/vaccines/engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove imports
content = re.sub(r'CatchupRule, ', '', content)
content = re.sub(r'ScheduleRule, ', '', content)
content = re.sub(r'VaccineGroup', '', content)

# Remove unused consts
content = re.sub(r'    SOURCE_SCHEDULE_RULE = \'schedule_rule\'\n', '', content)
content = re.sub(r'    SOURCE_CATCHUP_RULE = \'catchup_rule\'\n', '', content)
content = re.sub(r'    SOURCE_GROUP_RULE = \'group_rule\'\n', '', content)

# Replace evaluate() method
evaluate_regex = r'    def evaluate\(self\) -> Dict\[str, Any\]:[\s\S]*?        return \{\n.*?\n        \}\n'
clean_evaluate = '''    def evaluate(self) -> Dict[str, Any]:
        history_by_vaccine = self._group_history()
        active_series = self.policy_loader.get_active_series()
        self._validate_history(history_by_vaccine, active_series)

        due_today = []
        due_but_unavailable = []
        blocked = []
        missing_doses = []
        upcoming_details = []

        for series in active_series:
            self.series_history_cache[series.id] = self._validate_series_history(series, history_by_vaccine)

        for series in active_series:
            series_eval = self._recommend_series(series)
            due_today.extend(series_eval['due_today'])
            due_but_unavailable.extend(series_eval['due_but_unavailable'])
            blocked.extend(series_eval['blocked'])
            missing_doses.extend(series_eval['missing_doses'])
            upcoming_details.extend(series_eval['upcoming'])

        due_today, deferred_upcoming = self.global_constraints.defer_recommendations(
            self.records,
            due_today,
            self.evaluation_date,
        )
        upcoming_details.extend(deferred_upcoming)

        due_today = self._normalize_due_items(due_today)
        due_but_unavailable = self._normalize_due_items(due_but_unavailable)
        missing_doses = self._normalize_due_items(missing_doses)
        blocked = self._normalize_due_items(blocked)
        upcoming_details = self._normalize_due_items(upcoming_details)
        upcoming = [self._upcoming_tuple(item) for item in upcoming_details]
        next_appointment = min([item['target_date'] for item in upcoming_details], default=None)

        return {
            'policy_version': self.policy_version_code,
            'due_today': due_today,
            'due_but_unavailable': due_but_unavailable,
            'blocked': blocked,
            'missing_doses': missing_doses,
            'next_appointment': next_appointment,
            'upcoming': upcoming,
            'upcoming_details': upcoming_details,
            'invalid_history': self.invalid_history,
        }
'''

content = re.sub(evaluate_regex, clean_evaluate, content, flags=re.DOTALL)

# Delete rule keys
content = re.sub(r'    def _schedule_rule_key[\s\S]*?return f\"catchup:\{rule\.vaccine_id\}:\{rule\.prior_doses\}:\{rule\.min_age_days\}:\{rule\.max_age_days\}\"\n\n', '', content)
content = re.sub(r'    def _group_rule_key[\s\S]*?return f\"group:\{group\.id\}:dose:\{dose_number\}:interval\"\n\n', '', content)

# PVC
pvc_regex = r'    def _policy_version_code\(self, series: Optional\[Series\] = None.*?\n        return self\.policy_version_code\n'
new_pvc = '''    def _policy_version_code(self, series: Optional[Series] = None) -> str:
        if series and series.policy_version_id:
            return series.policy_version.code
        return self.policy_version_code
'''
content = re.sub(pvc_regex, new_pvc, content, flags=re.DOTALL)

# Clean up _build_decision_item arguments
content = content.replace('        group: Optional[VaccineGroup] = None,\n', '')
content = content.replace('        group: Optional[, Vaccine] = None,\n', '')
content = content.replace('            \'group_code\': str(group.id) if group else None,\n', '')
content = content.replace('            \'group_name\': group.name if group else None,\n', '')

# _flag_invalid arguments
content = content.replace('        group: Optional[VaccineGroup] = None,\n', '')
content = content.replace('            \'group_code\': str(group.id) if group else None,\n', '')
content = content.replace('            \'group_name\': group.name if group else None,\n', '')

# Replace _validate_history and trailing methods
valid_hist = '''    def _validate_history(
        self,
        history_by_vaccine: Dict[str, List[VaccinationRecord]],
        active_series: List[Series],
    ):
        self.global_constraints.validate_history(self.records, self.SOURCE_GLOBAL_CONSTRAINT)

    def _active_series_vaccine_ids(self, active_series: List[Series]) -> set[int]:
        return {
            link.product.vaccine_id
            for series in active_series
            for link in series.series_products.all()
        }
'''
content = re.sub(r'    def _validate_history\([\s\S]*?    def _active_series_vaccine_ids', valid_hist + '    def _active_series_vaccine_ids_backup', content)
content = content.replace('    def _active_series_vaccine_ids_backup', '    def _active_series_vaccine_ids')

# Drop _series_owned_group_ids and _evaluate_vaccine_group
content = re.sub(r'    def _series_owned_group_ids\([\s\S]*?    def _validate_series_history', '    def _validate_series_history', content)
content = re.sub(r'    def _evaluate_vaccine_group[\s\S]*', '', content)

with open('c:/Users/admiralTOUFIK/PNI/vaccines/engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
