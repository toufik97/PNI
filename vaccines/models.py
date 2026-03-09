from django.db import models
from django.core.exceptions import ValidationError

class Vaccine(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Penta, BCG, MMR")
    live = models.BooleanField(default=False, help_text="Is this a live attenuated vaccine?")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class ScheduleRule(models.Model):
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='schedule_rules')
    dose_number = models.PositiveIntegerField(help_text="1 for first dose, 2 for second, etc.")
    min_age_days = models.PositiveIntegerField(help_text="Minimum age in days (e.g., 6 weeks = 42 days, 9 months = 270 days)")
    recommended_age_days = models.PositiveIntegerField(help_text="Ideal age in days to receive this dose")
    max_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Latest allowed age in days (optional)")
    min_interval_days = models.PositiveIntegerField(default=0, help_text="Min days since previous dose. Use 0 for first dose.")

    class Meta:
        unique_together = ('vaccine', 'dose_number')
        ordering = ['vaccine', 'dose_number']

    def __str__(self):
        return f"{self.vaccine.name} - Dose {self.dose_number}"

    def clean(self):
        """Proactive validation for standard schedule rules."""
        if self.min_age_days > self.recommended_age_days:
            raise ValidationError(
                f"Invalid age logic: Minimum age ({self.min_age_days}d) "
                f"cannot be greater than recommended age ({self.recommended_age_days}d)."
            )
        
        if self.max_age_days and self.max_age_days < self.recommended_age_days:
            raise ValidationError(
                f"Invalid age logic: Maximum age ({self.max_age_days}d) "
                f"cannot be less than recommended age ({self.recommended_age_days}d)."
            )

class CatchupRule(models.Model):
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='catchup_rules')
    min_age_days = models.PositiveIntegerField(help_text="Start of age band in days (e.g., 1 year = 365 days)")
    max_age_days = models.PositiveIntegerField(help_text="End of age band in days (e.g., 5 years = 1825 days)")
    prior_doses = models.PositiveIntegerField(help_text="Number of valid doses received so far")
    doses_required = models.PositiveIntegerField(help_text="Total doses needed to complete catch-up")
    min_interval_days = models.PositiveIntegerField(help_text="Minimum days between catch-up doses")

    def __str__(self):
        return f"{self.vaccine.name} Catchup: {self.min_age_days}-{self.max_age_days}d, {self.prior_doses} prior doses"

class SubstitutionRule(models.Model):
    target_vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='substituted_by')
    substitute_vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='substitutes_for')
    condition = models.TextField(help_text="Rules for substitution, e.g., 'If age > 1 year'")

    def __str__(self):
        return f"{self.substitute_vaccine.name} substitutes {self.target_vaccine.name}"

class VaccineGroup(models.Model):
    """
    Groups vaccines that share antigens or belong to a common schedule 
    (e.g., the DTP family: Penta, DTC, Td).
    """
    name = models.CharField(max_length=100, unique=True, help_text="e.g., DTP Family")
    vaccines = models.ManyToManyField(Vaccine, related_name='groups')
    min_valid_interval_days = models.PositiveIntegerField(
        default=28, 
        help_text="Absolute minimum valid interval between ANY two vaccines in this group"
    )

    def __str__(self):
        return self.name

class GroupRule(models.Model):
    """
    Dynamic rules for complex multi-vaccine scenarios.
    Specifies what to give based on age and prior doses received across the entire group.
    """
    group = models.ForeignKey(VaccineGroup, on_delete=models.CASCADE, related_name='rules')
    prior_doses = models.PositiveIntegerField(help_text="Number of valid group doses already received")
    min_age_days = models.PositiveIntegerField(help_text="Minimum age in days for this rule to apply")
    max_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum age in days (optional)")
    vaccine_to_give = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='+')
    min_interval_days = models.PositiveIntegerField(
        help_text="Minimum days from the last dose in the group"
    )

    class Meta:
        ordering = ['group', 'prior_doses', 'min_age_days']

    def __str__(self):
        return f"{self.group.name} - {self.prior_doses} doses, Age {self.min_age_days}-{self.max_age_days}d -> {self.vaccine_to_give.name}"

    def clean(self):
        """Proactive validation for vaccine group rules."""
        # 1. Basic range check
        if self.max_age_days and self.max_age_days < self.min_age_days:
            raise ValidationError(
                f"Invalid age range: Min age ({self.min_age_days}d) "
                f"is greater than Max age ({self.max_age_days}d)."
            )

        # 2. Overlap check within the same group and prior_dose count
        # We check existing rules that are NOT this instance (self.pk)
        overlapping_rules = GroupRule.objects.filter(
            group=self.group,
            prior_doses=self.prior_doses
        ).exclude(pk=self.pk)

        for rule in overlapping_rules:
            # Logic: (StartA <= EndB) and (EndA >= StartB)
            # Handle None as infinity for Max Age
            other_max = rule.max_age_days if rule.max_age_days is not None else 99999
            this_max = self.max_age_days if self.max_age_days is not None else 99999

            if self.min_age_days <= other_max and this_max >= rule.min_age_days:
                raise ValidationError(
                    f"Configuration Error: This rule overlaps with an existing rule "
                    f"({rule.vaccine_to_give.name}, Age {rule.min_age_days}-{rule.max_age_days}d) "
                    f"for {self.prior_doses} prior doses."
                )
