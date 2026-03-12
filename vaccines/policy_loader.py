from django.db.models import Q

from vaccines.models import PolicyVersion, Series, Vaccine, VaccineGroup


class PolicyLoader:
    """Centralizes policy query loading for engine orchestration."""

    def get_active_policy_version(self):
        return PolicyVersion.get_active()

    def get_all_vaccines(self):
        return Vaccine.objects.all()

    def get_active_series(self):
        active_version = self.get_active_policy_version()
        queryset = Series.objects.filter(active=True)
        if active_version is not None:
            queryset = queryset.filter(Q(policy_version=active_version) | Q(policy_version__isnull=True))

        return list(
            queryset.prefetch_related(
                'series_products__product__vaccine',
                'rules__product__vaccine',
                'dependency_rules__anchor_series',
                'transition_rules__from_product__vaccine',
                'transition_rules__to_product__vaccine',
            )
        )

    def get_vaccine_groups(self):
        return VaccineGroup.objects.prefetch_related('vaccines', 'rules').all()
