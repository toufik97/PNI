from django.urls import reverse

from vaccines.models import GlobalConstraintRule, PolicyVersion
from .base import BaseVaccinationTestCase


class TestGlobalConstraintSettingsUI(BaseVaccinationTestCase):
    def test_constraints_tab_scopes_to_active_policy_version(self):
        future_version = PolicyVersion.objects.create(name='Series Policy v2', code='series-policy-v2', is_active=False)
        GlobalConstraintRule.objects.create(
            name='Active Live Spacing',
            code='active-live-spacing',
            constraint_type=GlobalConstraintRule.CONSTRAINT_LIVE_LIVE_SPACING,
            min_spacing_days=28,
            policy_version=self.dtp_series.policy_version,
        )
        GlobalConstraintRule.objects.create(
            name='Future Live Spacing',
            code='future-live-spacing',
            constraint_type=GlobalConstraintRule.CONSTRAINT_LIVE_LIVE_SPACING,
            min_spacing_days=35,
            policy_version=future_version,
        )

        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'constraints'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Active Live Spacing')
        self.assertNotContains(response, 'Future Live Spacing')
    def test_constraints_tab_lists_rules(self):
        GlobalConstraintRule.objects.create(
            name='Live Spacing',
            code='live-spacing',
            constraint_type=GlobalConstraintRule.CONSTRAINT_LIVE_LIVE_SPACING,
            min_spacing_days=28,
        )

        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'constraints'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Global Constraints')
        self.assertContains(response, 'Live Spacing')
        self.assertContains(response, '28d')

    def test_global_constraint_create_persists_rule(self):
        response = self.client.post(reverse('vaccines:global_constraint_create'), {
            'name': 'Expanded Live Spacing',
            'code': 'expanded-live-spacing',
            'constraint_type': GlobalConstraintRule.CONSTRAINT_LIVE_LIVE_SPACING,
            'min_spacing_days': '35',
            'policy_version': str(self.dtp_series.policy_version.pk),
            'active': 'on',
            'notes': 'Pilot constraint',
        })

        self.assertEqual(response.status_code, 302)
        rule = GlobalConstraintRule.objects.get(code='expanded-live-spacing')
        self.assertEqual(rule.min_spacing_days, 35)
        self.assertEqual(rule.policy_version, self.dtp_series.policy_version)
