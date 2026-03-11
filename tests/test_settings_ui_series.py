from django.urls import reverse

from vaccines.models import Product, Series, SeriesRule
from .base import BaseVaccinationTestCase


class TestSeriesSettingsUI(BaseVaccinationTestCase):
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

    def test_series_create_builds_membership_and_rule(self):
        response = self.client.post(reverse('vaccines:series_create'), {
            'name': 'Pneumo',
            'code': 'pneumo',
            'description': 'Pneumococcal series',
            'active': 'on',
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
        })

        self.assertEqual(response.status_code, 302)
        series = Series.objects.get(code='pneumo')
        self.assertEqual(series.series_products.count(), 1)
        self.assertEqual(series.rules.count(), 1)
        rule = SeriesRule.objects.get(series=series)
        self.assertEqual(rule.product.vaccine.name, 'Penta')
