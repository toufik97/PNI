from django.db.models import Q

from vaccines.models import PolicyVersion, Series, Vaccine


class PolicyLoader:
    """Centralizes policy query loading for engine orchestration."""

    _active_version_cache = None
    _active_series_cache = None
    _vaccines_cache = None

    def get_active_policy_version(self):
        if PolicyLoader._active_version_cache is None:
            PolicyLoader._active_version_cache = PolicyVersion.get_active()
        return PolicyLoader._active_version_cache

    def get_all_vaccines(self):
        if PolicyLoader._vaccines_cache is None:
            PolicyLoader._vaccines_cache = list(Vaccine.objects.all())
        return PolicyLoader._vaccines_cache

    def get_active_series(self):
        if PolicyLoader._active_series_cache is not None:
            return PolicyLoader._active_series_cache

        active_version = self.get_active_policy_version()
        queryset = Series.objects.filter(active=True)
        if active_version is not None:
            queryset = queryset.filter(Q(policy_version=active_version) | Q(policy_version__isnull=True))

        PolicyLoader._active_series_cache = list(
            queryset.prefetch_related(
                'series_products__product__vaccine',
                'rules__product__vaccine',
                'dependency_rules__anchor_series',
                'transition_rules__from_product__vaccine',
                'transition_rules__to_product__vaccine',
            )
        )
        return PolicyLoader._active_series_cache

