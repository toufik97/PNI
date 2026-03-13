from unittest.mock import patch

from django.urls import reverse

from vaccines.models import PolicyVersion, Product, Series, SeriesRule, SeriesTransitionRule, Vaccine
from .base import BaseVaccinationTestCase


class TestSeriesSettingsUI(BaseVaccinationTestCase):
    @patch('vaccines.views._global_constraints_available', return_value=False)
    def test_series_tab_handles_missing_constraints_table(self, _mock_available):
        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'series'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clinical Series')
    def test_series_tab_scopes_to_active_policy_version(self):
        future_version = PolicyVersion.objects.create(name='Series Policy v2', code='series-policy-v2', is_active=False)
        future_series = Series.objects.create(
            name='Future Pneumo',
            code='future-pneumo',
            description='Future rollout',
            active=True,
            policy_version=future_version,
            mixing_policy=Series.MIXING_FLEXIBLE,
            min_valid_interval_days=15,
        )

        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'series'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DTP Family')
        self.assertNotContains(response, future_series.name)
    def test_products_tab_lists_existing_products(self):
        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'products'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Product Catalog')
        self.assertContains(response, 'Penta')

    def test_series_tab_lists_existing_series(self):
        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'series'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clinical Series')
        self.assertContains(response, 'DTP Family')

    def test_product_create_creates_vaccine_and_product(self):
        response = self.client.post(reverse('vaccines:product_create'), {
            'name': 'Primovax',
            'live': '',
            'code': 'primovax',
            'manufacturer': 'Acme Pharma',
            'description': 'Pneumococcal brand',
            'active': 'on',
        })

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(code='primovax')
        self.assertEqual(product.vaccine.name, 'Primovax')
        self.assertEqual(product.manufacturer, 'Acme Pharma')

    def test_series_create_builds_membership_rule_and_transition(self):
        response = self.client.post(reverse('vaccines:series_create'), {
            'name': 'Pneumo',
            'code': 'pneumo',
            'description': 'Pneumococcal series',
            'active': 'on',
            'mixing_policy': Series.MIXING_FLEXIBLE,
            'min_valid_interval_days': '15',
            'legacy_group': '',
            'products-TOTAL_FORMS': '2',
            'products-INITIAL_FORMS': '0',
            'products-MIN_NUM_FORMS': '0',
            'products-MAX_NUM_FORMS': '1000',
            'products-0-product': str(self.product_map['Penta'].pk),
            'products-0-priority': '0',
            'products-1-product': str(self.product_map['DTC'].pk),
            'products-1-priority': '1',
            'rules-TOTAL_FORMS': '2',
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
            'rules-1-slot_number': '2',
            'rules-1-prior_valid_doses': '1',
            'rules-1-product': str(self.product_map['DTC'].pk),
            'rules-1-min_age_days': '90',
            'rules-1-recommended_age_days': '90',
            'rules-1-overdue_age_days': '120',
            'rules-1-max_age_days': '',
            'rules-1-min_interval_days': '28',
            'rules-1-dose_amount': '0.5ml',
            'rules-1-notes': 'DTC slot for switch validation',
            'transitions-TOTAL_FORMS': '1',
            'transitions-INITIAL_FORMS': '0',
            'transitions-MIN_NUM_FORMS': '0',
            'transitions-MAX_NUM_FORMS': '1000',
            'transitions-0-from_product': str(self.product_map['Penta'].pk),
            'transitions-0-to_product': str(self.product_map['DTC'].pk),
            'transitions-0-start_slot_number': '2',
            'transitions-0-end_slot_number': '3',
            'transitions-0-allow_if_unavailable': 'on',
            'transitions-0-active': 'on',
            'transitions-0-notes': 'Allow switch during stock outage',
        })

        self.assertEqual(response.status_code, 302)
        series = Series.objects.get(code='pneumo')
        self.assertEqual(series.series_products.count(), 2)
        self.assertEqual(series.rules.count(), 2)
        self.assertEqual(series.transition_rules.count(), 1)
        rule = SeriesRule.objects.get(series=series, slot_number=1)
        self.assertEqual(rule.product.vaccine.name, 'Penta')
        transition = SeriesTransitionRule.objects.get(series=series)
        self.assertEqual(transition.from_product.vaccine.name, 'Penta')
        self.assertEqual(transition.to_product.vaccine.name, 'DTC')
        self.assertTrue(transition.allow_if_unavailable)

    def test_series_create_ignores_posted_legacy_field(self):
        response = self.client.post(reverse('vaccines:series_create'), {
            'name': 'Pneumo No Legacy',
            'code': 'pneumo-no-legacy',
            'description': 'Pneumococcal series',
            'active': 'on',
            'mixing_policy': Series.MIXING_FLEXIBLE,
            'min_valid_interval_days': '15',
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
        series = Series.objects.get(code='pneumo-no-legacy')
        self.assertTrue(series.active)

    def test_series_edit_updates_transition_rules(self):
        series = Series.objects.create(
            name='Pneumo',
            code='pneumo',
            description='Pneumococcal series',
            mixing_policy=Series.MIXING_FLEXIBLE,
            min_valid_interval_days=15,
        )
        membership = series.series_products.create(product=self.product_map['Penta'], priority=0)
        membership_dtc = series.series_products.create(product=self.product_map['DTC'], priority=1)
        rule = series.rules.create(
            slot_number=1,
            prior_valid_doses=0,
            product=self.product_map['Penta'],
            min_age_days=60,
            recommended_age_days=60,
            overdue_age_days=75,
            min_interval_days=0,
            dose_amount='0.5ml',
        )
        rule_dtc = series.rules.create(
            slot_number=2,
            prior_valid_doses=1,
            product=self.product_map['DTC'],
            min_age_days=90,
            recommended_age_days=90,
            overdue_age_days=120,
            min_interval_days=28,
            dose_amount='0.5ml',
        )
        transition = series.transition_rules.create(
            from_product=self.product_map['Penta'],
            to_product=self.product_map['DTC'],
            start_slot_number=2,
            end_slot_number=3,
            allow_if_unavailable=True,
            active=True,
            notes='Initial switch rule',
        )

        response = self.client.post(reverse('vaccines:series_edit', kwargs={'pk': series.pk}), {
            'name': 'Pneumo',
            'code': 'pneumo',
            'description': 'Updated pneumococcal series',
            'active': 'on',
            'mixing_policy': Series.MIXING_FLEXIBLE,
            'min_valid_interval_days': '21',
            'legacy_group': '',
            'products-TOTAL_FORMS': '3',
            'products-INITIAL_FORMS': '2',
            'products-MIN_NUM_FORMS': '0',
            'products-MAX_NUM_FORMS': '1000',
            'products-0-id': str(membership.pk),
            'products-0-series': str(series.pk),
            'products-0-product': str(self.product_map['Penta'].pk),
            'products-0-priority': '0',
            'products-1-id': str(membership_dtc.pk),
            'products-1-series': str(series.pk),
            'products-1-product': str(self.product_map['DTC'].pk),
            'products-1-priority': '1',
            'products-2-product': str(self.product_map['Td'].pk),
            'products-2-priority': '2',
            'rules-TOTAL_FORMS': '3',
            'rules-INITIAL_FORMS': '2',
            'rules-MIN_NUM_FORMS': '0',
            'rules-MAX_NUM_FORMS': '1000',
            'rules-0-id': str(rule.pk),
            'rules-0-series': str(series.pk),
            'rules-0-slot_number': '1',
            'rules-0-prior_valid_doses': '0',
            'rules-0-product': str(self.product_map['Penta'].pk),
            'rules-0-min_age_days': '60',
            'rules-0-recommended_age_days': '60',
            'rules-0-overdue_age_days': '80',
            'rules-0-max_age_days': '',
            'rules-0-min_interval_days': '0',
            'rules-0-dose_amount': '0.5ml',
            'rules-0-notes': 'Updated starter slot',
            'rules-1-id': str(rule_dtc.pk),
            'rules-1-series': str(series.pk),
            'rules-1-slot_number': '2',
            'rules-1-prior_valid_doses': '1',
            'rules-1-product': str(self.product_map['DTC'].pk),
            'rules-1-min_age_days': '90',
            'rules-1-recommended_age_days': '90',
            'rules-1-overdue_age_days': '130',
            'rules-1-max_age_days': '',
            'rules-1-min_interval_days': '28',
            'rules-1-dose_amount': '0.5ml',
            'rules-1-notes': 'Updated DTC slot',
            'rules-2-slot_number': '4',
            'rules-2-prior_valid_doses': '3',
            'rules-2-product': str(self.product_map['Td'].pk),
            'rules-2-min_age_days': '365',
            'rules-2-recommended_age_days': '365',
            'rules-2-overdue_age_days': '400',
            'rules-2-max_age_days': '',
            'rules-2-min_interval_days': '180',
            'rules-2-dose_amount': '0.5ml',
            'rules-2-notes': 'Td fallback slot',
            'transitions-TOTAL_FORMS': '2',
            'transitions-INITIAL_FORMS': '1',
            'transitions-MIN_NUM_FORMS': '0',
            'transitions-MAX_NUM_FORMS': '1000',
            'transitions-0-id': str(transition.pk),
            'transitions-0-series': str(series.pk),
            'transitions-0-from_product': str(self.product_map['Penta'].pk),
            'transitions-0-to_product': str(self.product_map['DTC'].pk),
            'transitions-0-start_slot_number': '2',
            'transitions-0-end_slot_number': '4',
            'transitions-0-allow_if_unavailable': '',
            'transitions-0-active': 'on',
            'transitions-0-notes': 'Expanded switch window',
            'transitions-1-from_product': '',
            'transitions-1-to_product': str(self.product_map['Td'].pk),
            'transitions-1-start_slot_number': '4',
            'transitions-1-end_slot_number': '',
            'transitions-1-allow_if_unavailable': '',
            'transitions-1-active': 'on',
            'transitions-1-notes': 'Fallback to any product for later slots',
        })

        self.assertEqual(response.status_code, 302)
        series.refresh_from_db()
        transition.refresh_from_db()
        self.assertEqual(series.description, 'Updated pneumococcal series')
        self.assertEqual(series.min_valid_interval_days, 21)
        self.assertEqual(series.transition_rules.count(), 2)
        self.assertEqual(transition.end_slot_number, 4)
        self.assertFalse(transition.allow_if_unavailable)
        self.assertTrue(series.transition_rules.filter(to_product=self.product_map['Td'], from_product__isnull=True).exists())

    def test_series_tab_shows_transition_rule_summary(self):
        self.dtp_series.series_products.get_or_create(product=self.product_map['DTC'], defaults={'priority': 1})
        self.dtp_series.transition_rules.create(
            from_product=self.product_map['Penta'],
            to_product=self.product_map['DTC'],
            start_slot_number=2,
            end_slot_number=3,
            allow_if_unavailable=True,
            active=True,
        )

        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'series'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Transition Rules')
        self.assertContains(response, 'Only if prior product unavailable')
        self.assertContains(response, 'DTC')


    def test_series_create_rejects_overlapping_transition_rules(self):
        response = self.client.post(reverse('vaccines:series_create'), {
            'name': 'Pneumo',
            'code': 'pneumo',
            'description': 'Pneumococcal series',
            'active': 'on',
            'mixing_policy': Series.MIXING_FLEXIBLE,
            'min_valid_interval_days': '15',
            'legacy_group': '',
            'products-TOTAL_FORMS': '2',
            'products-INITIAL_FORMS': '0',
            'products-MIN_NUM_FORMS': '0',
            'products-MAX_NUM_FORMS': '1000',
            'products-0-product': str(self.product_map['Penta'].pk),
            'products-0-priority': '0',
            'products-1-product': str(self.product_map['DTC'].pk),
            'products-1-priority': '1',
            'rules-TOTAL_FORMS': '2',
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
            'rules-1-slot_number': '2',
            'rules-1-prior_valid_doses': '1',
            'rules-1-product': str(self.product_map['DTC'].pk),
            'rules-1-min_age_days': '90',
            'rules-1-recommended_age_days': '90',
            'rules-1-overdue_age_days': '120',
            'rules-1-max_age_days': '',
            'rules-1-min_interval_days': '28',
            'rules-1-dose_amount': '0.5ml',
            'rules-1-notes': 'DTC slot for switch validation',
            'transitions-TOTAL_FORMS': '2',
            'transitions-INITIAL_FORMS': '0',
            'transitions-MIN_NUM_FORMS': '0',
            'transitions-MAX_NUM_FORMS': '1000',
            'transitions-0-from_product': str(self.product_map['Penta'].pk),
            'transitions-0-to_product': str(self.product_map['DTC'].pk),
            'transitions-0-start_slot_number': '2',
            'transitions-0-end_slot_number': '3',
            'transitions-0-allow_if_unavailable': '',
            'transitions-0-active': 'on',
            'transitions-0-notes': 'First switch window',
            'transitions-1-from_product': str(self.product_map['Penta'].pk),
            'transitions-1-to_product': str(self.product_map['DTC'].pk),
            'transitions-1-start_slot_number': '3',
            'transitions-1-end_slot_number': '4',
            'transitions-1-allow_if_unavailable': '',
            'transitions-1-active': 'on',
            'transitions-1-notes': 'Overlapping switch window',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Active transition rules cannot overlap for the same source, destination, and availability condition.')
        self.assertFalse(Series.objects.filter(code='pneumo').exists())

    def test_series_create_rejects_transition_without_destination_slot_rule(self):
        response = self.client.post(reverse('vaccines:series_create'), {
            'name': 'Pneumo Impossible Transition',
            'code': 'pneumo-impossible-transition',
            'description': 'Pneumococcal series',
            'active': 'on',
            'mixing_policy': Series.MIXING_STRICT,
            'min_valid_interval_days': '15',
            'legacy_group': '',
            'products-TOTAL_FORMS': '2',
            'products-INITIAL_FORMS': '0',
            'products-MIN_NUM_FORMS': '0',
            'products-MAX_NUM_FORMS': '1000',
            'products-0-product': str(self.product_map['Penta'].pk),
            'products-0-priority': '0',
            'products-1-product': str(self.product_map['DTC'].pk),
            'products-1-priority': '1',
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
            'rules-0-notes': 'Starter slot only',
            'transitions-TOTAL_FORMS': '1',
            'transitions-INITIAL_FORMS': '0',
            'transitions-MIN_NUM_FORMS': '0',
            'transitions-MAX_NUM_FORMS': '1000',
            'transitions-0-from_product': str(self.product_map['Penta'].pk),
            'transitions-0-to_product': str(self.product_map['DTC'].pk),
            'transitions-0-start_slot_number': '2',
            'transitions-0-end_slot_number': '3',
            'transitions-0-allow_if_unavailable': '',
            'transitions-0-active': 'on',
            'transitions-0-notes': 'No DTC slot exists in this range',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Transition rules must target at least one slot that already allows the destination product.')
        self.assertFalse(Series.objects.filter(code='pneumo-impossible-transition').exists())


