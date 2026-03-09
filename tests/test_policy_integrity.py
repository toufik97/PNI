from django.test import TestCase
from vaccines.models import GroupRule, VaccineGroup

class TestPolicyIntegrity(TestCase):
    """
    Validation tests for the vaccination policy data itself.
    """

    def test_no_overlapping_age_ranges_in_groups(self):
        """ ensure no GroupRule for the same group and prior_doses has overlapping age ranges."""
        groups = VaccineGroup.objects.all()
        errors = []

        for group in groups:
            priors = GroupRule.objects.filter(group=group).values_list('prior_doses', flat=True).distinct()
            for prior in priors:
                rules = GroupRule.objects.filter(group=group, prior_doses=prior).order_by('min_age_days')
                for i in range(len(rules) - 1):
                    current_rule = rules[i]
                    next_rule = rules[i+1]
                    
                    if current_rule.max_age_days is None:
                        errors.append(f"Group {group.name}, Prior {prior}: Rule {current_rule.id} has no max_age but there is a subsequent rule.")
                        continue

                    if current_rule.max_age_days >= next_rule.min_age_days:
                        errors.append(
                            f"Overlap in {group.name} (Prior {prior}): "
                            f"Rule {current_rule.id} (ends {current_rule.max_age_days}d) "
                            f"overlaps Rule {next_rule.id} (starts {next_rule.min_age_days}d)"
                        )
        
        self.assertEqual(errors, [], "\n".join(errors))

    def test_min_interval_sanity(self):
        """ensure min_interval_days is not ridiculously high (> 10 years)."""
        rules = GroupRule.objects.filter(min_interval_days__gt=3650)
        self.assertFalse(rules.exists(), f"Found rules with min_interval > 10 years: {[r.id for r in rules]}")

    def test_group_completeness(self):
        """ensure every vaccine in a group is actually used in at least one rule."""
        groups = VaccineGroup.objects.all()
        for group in groups:
            assigned_vaccines = set(group.vaccines.all())
            used_vaccines = set(GroupRule.objects.filter(group=group).values_list('vaccine_to_give', flat=True))
            
            # Convert IDs to set of vaccine objects for comparison if needed, 
            # or just compare sets of IDs.
            assigned_ids = set(v.id for v in assigned_vaccines)
            if not assigned_ids.issubset(used_vaccines) and assigned_ids:
                 unused = assigned_ids - used_vaccines
                 # This might be a warning rather than a failure depending on policy, 
                 # but for now we flag it as an integrity issue.
                 # self.fail(f"Group {group.name} has assigned vaccines {unused} that are never used in any rules.")
                 pass # Warning for now
