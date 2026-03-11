from django.urls import reverse

from vaccines.models import DependencyRule, Product, Series, SeriesProduct, SeriesRule, Vaccine
from .base import BaseVaccinationTestCase


class TestDependencySettingsUI(BaseVaccinationTestCase):
    def create_pneumo_series(self):
        vaccine = Vaccine.objects.create(name='Prevenar13', live=False)
        product = Product.objects.create(vaccine=vaccine, available=True)
        series = Series.objects.create(name='Pneumo', mixing_policy=Series.MIXING_FLEXIBLE)
        SeriesProduct.objects.create(series=series, product=product, priority=0)
        SeriesRule.objects.create(
            series=series,
            slot_number=1,
            prior_valid_doses=0,
            min_age_days=60,
            recommended_age_days=60,
            overdue_age_days=90,
            min_interval_days=0,
            product=product,
        )
        return series

    def test_dependencies_tab_lists_rules(self):
        pneumo = self.create_pneumo_series()
        DependencyRule.objects.create(
            dependent_series=pneumo,
            dependent_slot_number=1,
            anchor_series=self.dtp_series,
            anchor_slot_number=1,
            min_offset_days=15,
        )

        response = self.client.get(reverse('vaccines:settings_tab', kwargs={'tab': 'dependencies'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Series Dependencies')
        self.assertContains(response, 'Pneumo')
        self.assertContains(response, '15d')

    def test_dependency_create_persists_rule(self):
        pneumo = self.create_pneumo_series()

        response = self.client.post(reverse('vaccines:dependency_create'), {
            'dependent_series': str(pneumo.pk),
            'dependent_slot_number': '1',
            'anchor_series': str(self.dtp_series.pk),
            'anchor_slot_number': '1',
            'min_offset_days': '15',
            'block_if_anchor_missing': 'on',
            'active': 'on',
            'notes': 'Pneumo after DTP',
        })

        self.assertEqual(response.status_code, 302)
        dependency = DependencyRule.objects.get(dependent_series=pneumo)
        self.assertEqual(dependency.min_offset_days, 15)
        self.assertTrue(dependency.block_if_anchor_missing)
