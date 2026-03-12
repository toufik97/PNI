from collections import defaultdict
from typing import Dict, Iterable, List

from patients.models import Child, VaccinationRecord


class HistoryNormalizer:
    def __init__(self, child: Child, records: Iterable[VaccinationRecord]):
        self.child = child
        self.records = sorted(records, key=lambda record: record.date_given)
        self._history_by_vaccine = None
        self._age_cache: Dict[int, int] = {}

    @property
    def history_by_vaccine(self) -> Dict[int, List[VaccinationRecord]]:
        if self._history_by_vaccine is None:
            grouped = defaultdict(list)
            for record in self.records:
                grouped[record.vaccine_id].append(record)
            self._history_by_vaccine = dict(grouped)
        return self._history_by_vaccine

    def age_at_dose(self, record: VaccinationRecord) -> int:
        if record.pk not in self._age_cache:
            self._age_cache[record.pk] = (record.date_given - self.child.dob).days
        return self._age_cache[record.pk]
