from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Vaccine(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Penta, BCG, MMR")
    live = models.BooleanField(default=False, help_text="Is this a live attenuated vaccine?")
    compatible_live_vaccines = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        help_text="Other live vaccines that can be given safely within 28 days (e.g. OPV)"
    )
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class ScheduleRule(models.Model):
    vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='schedule_rules')
    dose_number = models.PositiveIntegerField(help_text="1 for first dose, 2 for second, etc.")
    min_age_days = models.PositiveIntegerField(help_text="Minimum age in days (e.g., 6 weeks = 42 days, 9 months = 270 days)")
    recommended_age_days = models.PositiveIntegerField(help_text="Ideal age in days to receive this dose")
    overdue_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Age in days after which the dose is considered overdue/missing")
    max_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Latest allowed age in days (optional)")
    min_interval_days = models.PositiveIntegerField(default=0, help_text="Min days since previous dose. Use 0 for first dose.")
    dose_amount = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., 0.05ml")

    class Meta:
        unique_together = ('vaccine', 'dose_number')
        ordering = ['vaccine', 'dose_number']

    def __str__(self):
        return f"{self.vaccine.name} - Dose {self.dose_number}"

    def clean(self):
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
    dose_amount = models.CharField(max_length=50, blank=True, null=True, help_text="Override dose amount for this catch-up rule")

    def __str__(self):
        return f"{self.vaccine.name} Catchup: {self.min_age_days}-{self.max_age_days}d, {self.prior_doses} prior doses"


class SubstitutionRule(models.Model):
    target_vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='substituted_by')
    substitute_vaccine = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='substitutes_for')
    condition = models.TextField(help_text="Rules for substitution, e.g., 'If age > 1 year'")

    def __str__(self):
        return f"{self.substitute_vaccine.name} substitutes {self.target_vaccine.name}"


class VaccineGroup(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., DTP Family")
    vaccines = models.ManyToManyField(Vaccine, related_name='groups')
    min_valid_interval_days = models.PositiveIntegerField(
        default=28,
        help_text="Absolute minimum valid interval between ANY two vaccines in this group"
    )

    def __str__(self):
        return self.name


class GroupRule(models.Model):
    group = models.ForeignKey(VaccineGroup, on_delete=models.CASCADE, related_name='rules')
    prior_doses = models.PositiveIntegerField(help_text="Number of valid group doses already received")
    min_age_days = models.PositiveIntegerField(help_text="Minimum age in days for this rule to apply")
    max_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum age in days (optional)")
    vaccine_to_give = models.ForeignKey(Vaccine, on_delete=models.CASCADE, related_name='+')
    min_interval_days = models.PositiveIntegerField(help_text="Minimum days from the last dose in the group")
    dose_amount = models.CharField(max_length=50, blank=True, null=True, help_text="Dose amount for this specific group rule")

    class Meta:
        ordering = ['group', 'prior_doses', 'min_age_days']

    def __str__(self):
        return (
            f"{self.group.name} - {self.prior_doses} doses, "
            f"Age {self.min_age_days}-{self.max_age_days}d -> {self.vaccine_to_give.name}"
        )

    def clean(self):
        if self.max_age_days and self.max_age_days < self.min_age_days:
            raise ValidationError(
                f"Invalid age range: Min age ({self.min_age_days}d) "
                f"is greater than Max age ({self.max_age_days}d)."
            )

        overlapping_rules = GroupRule.objects.filter(
            group=self.group,
            prior_doses=self.prior_doses
        ).exclude(pk=self.pk)

        for rule in overlapping_rules:
            other_max = rule.max_age_days if rule.max_age_days is not None else 99999
            this_max = self.max_age_days if self.max_age_days is not None else 99999

            if self.min_age_days <= other_max and this_max >= rule.min_age_days:
                raise ValidationError(
                    f"Configuration Error: This rule overlaps with an existing rule "
                    f"({rule.vaccine_to_give.name}, Age {rule.min_age_days}-{rule.max_age_days}d) "
                    f"for {self.prior_doses} prior doses."
                )


class Product(models.Model):
    vaccine = models.OneToOneField(Vaccine, on_delete=models.CASCADE, related_name='product_profile')
    code = models.SlugField(max_length=100, unique=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['vaccine__name']

    def __str__(self):
        return self.vaccine.name

    @property
    def name(self):
        return self.vaccine.name

    @property
    def live(self):
        return self.vaccine.live

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.vaccine.name)
        super().save(*args, **kwargs)


class Series(models.Model):
    MIXING_STRICT = 'strict'
    MIXING_AGE_RULE = 'age_rule'
    MIXING_FLEXIBLE = 'flexible'
    MIXING_POLICY_CHOICES = [
        (MIXING_STRICT, 'Strict product continuity'),
        (MIXING_AGE_RULE, 'Age-based product switching'),
        (MIXING_FLEXIBLE, 'Flexible switching'),
    ]

    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)
    min_valid_interval_days = models.PositiveIntegerField(
        default=28,
        help_text="Absolute minimum valid interval between any two doses in this series"
    )
    mixing_policy = models.CharField(
        max_length=20,
        choices=MIXING_POLICY_CHOICES,
        default=MIXING_AGE_RULE,
    )
    legacy_group = models.OneToOneField(
        VaccineGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='series_policy',
    )
    products = models.ManyToManyField(Product, through='SeriesProduct', related_name='series_memberships')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)
        super().save(*args, **kwargs)


class SeriesProduct(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='series_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_series_links')
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('series', 'product')
        ordering = ['series', 'priority', 'product__vaccine__name']

    def __str__(self):
        return f"{self.series.name} -> {self.product.vaccine.name}"


class SeriesRule(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='rules')
    slot_number = models.PositiveIntegerField(help_text="1 for first dose slot, 2 for second, etc.")
    prior_valid_doses = models.PositiveIntegerField(help_text="Number of valid series doses already received")
    min_age_days = models.PositiveIntegerField(help_text="Minimum age in days for this slot rule")
    recommended_age_days = models.PositiveIntegerField(help_text="Target age in days for this slot rule")
    overdue_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Age in days when the slot becomes missing")
    max_age_days = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum age in days (optional)")
    min_interval_days = models.PositiveIntegerField(help_text="Minimum days from the previous valid series dose")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='series_rules')
    dose_amount = models.CharField(max_length=50, blank=True, null=True, help_text="Dose amount for this slot rule")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['series', 'prior_valid_doses', 'min_age_days', 'slot_number']

    def __str__(self):
        return (
            f"{self.series.name} slot {self.slot_number}: {self.prior_valid_doses} prior doses, "
            f"Age {self.min_age_days}-{self.max_age_days}d -> {self.product.vaccine.name}"
        )

    def clean(self):
        if self.slot_number != self.prior_valid_doses + 1:
            raise ValidationError("Slot number must equal prior valid doses + 1.")

        if self.min_age_days > self.recommended_age_days:
            raise ValidationError(
                f"Invalid age logic: Minimum age ({self.min_age_days}d) "
                f"cannot be greater than recommended age ({self.recommended_age_days}d)."
            )

        if self.max_age_days and self.max_age_days < self.min_age_days:
            raise ValidationError(
                f"Invalid age range: Min age ({self.min_age_days}d) "
                f"is greater than Max age ({self.max_age_days}d)."
            )
