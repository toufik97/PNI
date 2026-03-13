from django.urls import reverse

from vaccines.models import DependencyRule, Product, Series, SeriesProduct, SeriesRule, Vaccine
from .base import BaseVaccinationTestCase


class TestDependencySettingsUI(BaseVaccinationTestCase):
    def create_series(self, series_name='Pneumo', vaccine_name='Prevenar13'):
        vaccine = Vaccine.objects.create(name=vaccine_name, live=False)
        product = Product.objects.create(vaccine=vaccine, available=True)
        series = Series.objects.create(name=series_name, mixing_policy=Series.MIXING_FLEXIBLE)
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
        pneumo = self.create_series()
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
        pneumo = self.create_series()

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

    def test_dependency_create_rejects_missing_dependent_slot(self):
        pneumo = self.create_series()

        response = self.client.post(reverse('vaccines:dependency_create'), {
            'dependent_series': str(pneumo.pk),
            'dependent_slot_number': '2',
            'anchor_series': str(self.dtp_series.pk),
            'anchor_slot_number': '1',
            'min_offset_days': '15',
            'block_if_anchor_missing': 'on',
            'active': 'on',
            'notes': 'References a slot that does not exist',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dependency rules can only reference dependent slots that exist in the dependent series.')
        self.assertEqual(DependencyRule.objects.filter(dependent_series=pneumo).count(), 0)

    def test_dependency_create_rejects_missing_anchor_slot(self):
        pneumo = self.create_series()

        response = self.client.post(reverse('vaccines:dependency_create'), {
            'dependent_series': str(pneumo.pk),
            'dependent_slot_number': '1',
            'anchor_series': str(self.dtp_series.pk),
            'anchor_slot_number': '9',
            'min_offset_days': '15',
            'block_if_anchor_missing': 'on',
            'active': 'on',
            'notes': 'References an anchor slot that does not exist',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dependency rules can only reference anchor slots that exist in the anchor series.')
        self.assertEqual(DependencyRule.objects.filter(dependent_series=pneumo).count(), 0)

    def test_dependency_create_rejects_direct_blocking_cycle(self):
        pneumo = self.create_series()
        rota = self.create_series(series_name='Rota Support', vaccine_name='Rota Support')
        DependencyRule.objects.create(
            dependent_series=pneumo,
            dependent_slot_number=1,
            anchor_series=rota,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        response = self.client.post(reverse('vaccines:dependency_create'), {
            'dependent_series': str(rota.pk),
            'dependent_slot_number': '1',
            'anchor_series': str(pneumo.pk),
            'anchor_slot_number': '1',
            'min_offset_days': '0',
            'block_if_anchor_missing': 'on',
            'active': 'on',
            'notes': 'Would deadlock with the existing Pneumo rule',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dependency rules cannot create a direct blocking cycle between two series slots.')
        self.assertEqual(DependencyRule.objects.filter(dependent_series=rota, anchor_series=pneumo).count(), 0)

    def test_dependency_create_rejects_transitive_blocking_cycle(self):
        pneumo = self.create_series(series_name='Pneumo Support', vaccine_name='Pneumo Support')
        rota = self.create_series(series_name='Rota Support', vaccine_name='Rota Support')
        measles = self.create_series(series_name='Measles Support', vaccine_name='Measles Support')
        DependencyRule.objects.create(
            dependent_series=pneumo,
            dependent_slot_number=1,
            anchor_series=rota,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )
        DependencyRule.objects.create(
            dependent_series=rota,
            dependent_slot_number=1,
            anchor_series=measles,
            anchor_slot_number=1,
            min_offset_days=0,
            block_if_anchor_missing=True,
            active=True,
        )

        response = self.client.post(reverse('vaccines:dependency_create'), {
            'dependent_series': str(measles.pk),
            'dependent_slot_number': '1',
            'anchor_series': str(pneumo.pk),
            'anchor_slot_number': '1',
            'min_offset_days': '0',
            'block_if_anchor_missing': 'on',
            'active': 'on',
            'notes': 'Would complete a three-series deadlock',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dependency rules cannot create a blocking cycle across multiple series slots.')
        self.assertEqual(DependencyRule.objects.filter(dependent_series=measles, anchor_series=pneumo).count(), 0)
