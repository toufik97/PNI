from typing import List

from vaccines.models import PolicyVersion, Series, Vaccine, VaccineGroup


class PolicyLoader:
    """Centralizes policy query loading for engine orchestration."""

    def get_active_policy_version(self):
        return PolicyVersion.get_active()

    def get_all_vaccines(self):
        return Vaccine.objects.all()

    def get_active_series(self) -> List[Series]:
        return list(
            Series.objects.filter(active=True).prefetch_related(
                'series_products__product__vaccine',
                'rules__product__vaccine',
                'dependency_rules__anchor_series',
            )
        )

    def get_vaccine_groups(self):
        return VaccineGroup.objects.prefetch_related('vaccines', 'rules').all()
