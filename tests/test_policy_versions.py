from vaccines.models import PolicyVersion, Series
from .base import BaseVaccinationTestCase


class TestPolicyVersioning(BaseVaccinationTestCase):
    def test_default_policy_version_exists_and_is_active(self):
        active = PolicyVersion.get_active()

        self.assertIsNotNone(active)
        self.assertEqual(active.code, 'series-policy-v1')
        self.assertTrue(active.is_active)
        self.assertEqual(self.dtp_series.policy_version, active)

    def test_engine_uses_active_policy_version_code(self):
        child = self.make_child('Policy Version Child', age_days=60)

        result = self.evaluate(child)

        self.assertEqual(result['policy_version'], 'series-policy-v1')
        penta_item = next(item for item in result['due_today'] if item['vaccine'].name == 'Penta')
        self.assertEqual(penta_item['policy_version'], 'series-policy-v1')

    def test_series_save_defaults_to_active_policy_version(self):
        series = Series.objects.create(name='Pneumo', mixing_policy=Series.MIXING_FLEXIBLE, min_valid_interval_days=28)

        self.assertEqual(series.policy_version, PolicyVersion.get_active())

    def test_activating_new_policy_version_switches_engine_output(self):
        PolicyVersion.objects.create(name='Series Policy v2', code='series-policy-v2', is_active=True)
        child = self.make_child('Policy Switch Child', age_days=60)

        result = self.evaluate(child)

        self.assertEqual(result['policy_version'], 'series-policy-v2')
