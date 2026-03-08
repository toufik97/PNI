from django.db import models

class Vaccine(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Penta, BCG, MMR")
    live = models.BooleanField(default=False, help_text="Is this a live attenuated vaccine?")
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class ScheduleRule(models.Model):
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='schedule_rules')
    dose_number = models.PositiveIntegerField(help_text="1 for first dose, 2 for second, etc.")
    min_age_days = models.PositiveIntegerField(help_text="Minimum age in days to receive this dose")
    recommended_age_days = models.PositiveIntegerField(help_text="Recommended age in days")
    max_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum age in days (optional)")
    min_interval_days = models.PositiveIntegerField(default=0, help_text="Minimum interval from previous dose in days. 0 for first dose.")

    class Meta:
        unique_together = ('vaccine', 'dose_number')
        ordering = ['vaccine', 'dose_number']

    def __str__(self):
        return f"{self.vaccine.name} - Dose {self.dose_number}"

class CatchupRule(models.Model):
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='catchup_rules')
    min_age_days = models.PositiveIntegerField(help_text="Start of age band for this rule in days")
    max_age_days = models.PositiveIntegerField(help_text="End of age band for this rule in days")
    prior_doses = models.PositiveIntegerField(help_text="Number of doses received so far")
    doses_required = models.PositiveIntegerField(help_text="Total doses required to complete schedule in this catchup scenario")
    min_interval_days = models.PositiveIntegerField(help_text="Minimum interval from previous dose in days")

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
    prior_doses = models.PositiveIntegerField(help_text="Number of valid doses already received from this group")
    min_age_days = models.PositiveIntegerField(help_text="Minimum age in days for this rule to apply (age-bracket selector)")
    max_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum age in days for this rule's age bracket (optional)")
    vaccine_to_give = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='+')
    min_interval_days = models.PositiveIntegerField(
        help_text="Minimum interval from the last dose in the group in days"
    )

    class Meta:
        ordering = ['group', 'prior_doses', 'min_age_days']

    def __str__(self):
        return f"{self.group.name} - {self.prior_doses} doses, Age {self.min_age_days}-{self.max_age_days}d -> {self.vaccine_to_give.name}"
