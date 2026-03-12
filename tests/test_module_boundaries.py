from vaccines.engine import VaccinationEngine
from vaccines.history_normalizer import HistoryNormalizer
from vaccines.series_validator import SeriesHistoryValidator
from .base import BaseVaccinationTestCase


class TestModuleBoundaries(BaseVaccinationTestCase):
    def test_history_normalizer_sorts_and_groups_records(self):
        child = self.make_child('Normalizer Child', age_days=200)
        rr_record = self.give_dose(child, self.rr, days_ago=5)
        penta_record = self.give_dose(child, self.penta, days_ago=30)

        history = HistoryNormalizer(child, [rr_record, penta_record])

        self.assertEqual([record.vaccine.name for record in history.records], ['Penta', 'RR'])
        self.assertEqual([record.vaccine.name for record in history.history_by_vaccine[self.penta.id]], ['Penta'])
        self.assertEqual(history.age_at_dose(penta_record), 170)

    def test_series_validator_handles_series_local_validation(self):
        child = self.make_child('Series Validator Child', age_days=60)
        dtc_record = self.give_dose(child, self.dtc, days_ago=0)
        engine = VaccinationEngine(child)
        validator = SeriesHistoryValidator(engine, engine._group_history())

        valid_records = validator.validate(self.dtp_series)

        self.assertEqual(valid_records, [])
        dtc_record.refresh_from_db()
        self.assertTrue(dtc_record.invalid_flag)
        self.assertEqual(dtc_record.invalid_reason, dtc_record.REASON_WRONG_VACCINE)
        self.assertEqual(len(engine.invalid_history), 1)
