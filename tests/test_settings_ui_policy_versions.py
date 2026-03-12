from django.urls import reverse

from vaccines.models import PolicyVersion, Series
from .base import BaseVaccinationTestCase


class TestPolicyVersionSettingsUI(BaseVaccinationTestCase):
    def test_versions_tab_lists_active_policy_version(self):
        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'versions'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Policy Versions')
        self.assertContains(response, 'Series Policy v1')
        self.assertContains(response, 'Active')

    def test_policy_version_create_persists_version(self):
        response = self.client.post(reverse('vaccines:policy_version_create'), {
            'name': 'Series Policy v2',
            'code': 'series-policy-v2',
            'description': 'Next rollout',
            'effective_date': '2026-03-12',
            'is_active': 'on',
            'notes': 'Draft approved',
        })

        self.assertEqual(response.status_code, 302)
        version = PolicyVersion.objects.get(code='series-policy-v2')
        self.assertTrue(version.is_active)
        self.assertFalse(PolicyVersion.objects.get(code='series-policy-v1').is_active)

    def test_series_create_can_assign_specific_policy_version(self):
        version = PolicyVersion.objects.create(name='Series Policy v2', code='series-policy-v2', is_active=False)

        response = self.client.post(reverse('vaccines:series_create'), {
            'name': 'Pneumo',
            'code': 'pneumo',
            'description': 'Pneumococcal series',
            'active': 'on',
            'policy_version': str(version.pk),
            'mixing_policy': Series.MIXING_FLEXIBLE,
            'min_valid_interval_days': '15',
            'legacy_group': '',
            'products-TOTAL_FORMS': '1',
            'products-INITIAL_FORMS': '0',
            'products-MIN_NUM_FORMS': '0',
            'products-MAX_NUM_FORMS': '1000',
            'products-0-product': str(self.product_map['Penta'].pk),
            'products-0-priority': '0',
            'rules-TOTAL_FORMS': '1',
            'rules-INITIAL_FORMS': '0',
            'rules-MIN_NUM_FORMS': '0',
            'rules-MAX_NUM_FORMS': '1000',
            'rules-0-slot_number': '1',
            'rules-0-prior_valid_doses': '0',
            'rules-0-product': str(self.product_map['Penta'].pk),
            'rules-0-min_age_days': '60',
            'rules-0-recommended_age_days': '60',
            'rules-0-overdue_age_days': '75',
            'rules-0-max_age_days': '',
            'rules-0-min_interval_days': '0',
            'rules-0-dose_amount': '0.5ml',
            'rules-0-notes': 'Starter slot',
            'transitions-TOTAL_FORMS': '0',
            'transitions-INITIAL_FORMS': '0',
            'transitions-MIN_NUM_FORMS': '0',
            'transitions-MAX_NUM_FORMS': '1000',
        })

        self.assertEqual(response.status_code, 302)
        series = Series.objects.get(code='pneumo')
        self.assertEqual(series.policy_version, version)
