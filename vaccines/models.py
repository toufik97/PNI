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


class PolicyVersion(models.Model):
    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    effective_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False, help_text="Exactly one policy version should be active for scheduling.")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-is_active', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)
        super().save(*args, **kwargs)
        if self.is_active:
            PolicyVersion.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)

    @classmethod
    def get_active(cls):
        active = cls.objects.filter(is_active=True).order_by('-id').first()
        if active:
            return active
        return cls.objects.order_by('-id').first()


class Product(models.Model):
    vaccine = models.OneToOneField(Vaccine, on_delete=models.CASCADE, related_name='product_profile')
    code = models.SlugField(max_length=100, unique=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)
    available = models.BooleanField(default=True, help_text="Whether this product is currently available for scheduling")

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
    policy_version = models.ForeignKey(PolicyVersion, on_delete=models.PROTECT, related_name='series', null=True, blank=True)
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
        if not self.policy_version_id:
            self.policy_version = PolicyVersion.get_active()
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

        if self.series_id and self.product_id:
            linked_products = self.series.series_products.filter(product_id=self.product_id)
            if not linked_products.exists():
                raise ValidationError("Series rules can only reference products linked to the same series.")

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



class SeriesTransitionRule(models.Model):
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='transition_rules')
    from_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='from_transition_rules',
        null=True,
        blank=True,
        help_text='Optional source product. Leave blank to allow transition from any prior product in the series.',
    )
    to_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='to_transition_rules',
        help_text='Product that becomes allowed when this transition rule matches.',
    )
    start_slot_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='First slot number where this transition is allowed. Leave blank to allow from slot 1.',
    )
    end_slot_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Last slot number where this transition is allowed. Leave blank to allow indefinitely.',
    )
    allow_if_unavailable = models.BooleanField(
        default=False,
        help_text='If enabled, the transition is allowed only when the prior product is unavailable.',
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['series', 'start_slot_number', 'to_product__vaccine__name']

    def __str__(self):
        source = self.from_product.vaccine.name if self.from_product_id else 'Any product'
        start_slot = self.start_slot_number or 1
        end_slot = self.end_slot_number or 'any'
        qualifier = ' if unavailable' if self.allow_if_unavailable else ''
        return (
            f"{self.series.name}: {source} -> {self.to_product.vaccine.name} "
            f"(slots {start_slot}-{end_slot}){qualifier}"
        )

    def clean(self):
        if self.from_product_id and self.from_product_id == self.to_product_id:
            raise ValidationError('Transition rules must point to a different destination product.')

        if self.end_slot_number is not None and self.start_slot_number is not None and self.end_slot_number < self.start_slot_number:
            raise ValidationError('End slot must be greater than or equal to the start slot.')

        if self.allow_if_unavailable and not self.from_product_id:
            raise ValidationError('Unavailable-only transitions must specify a source product.')

        linked_product_ids = set(self.series.series_products.values_list('product_id', flat=True)) if self.series_id else set()
        if self.to_product_id and linked_product_ids and self.to_product_id not in linked_product_ids:
            raise ValidationError('Transition rules can only target products linked to the same series.')

        if self.from_product_id and linked_product_ids and self.from_product_id not in linked_product_ids:
            raise ValidationError('Transition rules can only reference source products linked to the same series.')
class DependencyRule(models.Model):
    dependent_series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='dependency_rules')
    dependent_slot_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank to apply to every slot in the dependent series",
    )
    anchor_series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name='anchored_dependency_rules')
    anchor_slot_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank to use the same slot number as the dependent series",
    )
    min_offset_days = models.PositiveIntegerField(default=0, help_text="Minimum days after the anchor slot")
    block_if_anchor_missing = models.BooleanField(
        default=True,
        help_text="If enabled, the dependent slot stays blocked until the anchor slot exists",
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['dependent_series', 'dependent_slot_number', 'anchor_series', 'anchor_slot_number']

    def __str__(self):
        dependent_slot = self.dependent_slot_number or 'all'
        anchor_slot = self.anchor_slot_number or 'matching'
        return (
            f"{self.dependent_series.name} slot {dependent_slot} after "
            f"{self.anchor_series.name} slot {anchor_slot} + {self.min_offset_days}d"
        )

    def clean(self):
        if self.dependent_series_id == self.anchor_series_id and self.min_offset_days == 0:
            raise ValidationError("A dependency rule cannot self-reference the same series without an offset.")

        if self.dependent_series_id and self.anchor_series_id:
            dependent_version_id = self.dependent_series.policy_version_id
            anchor_version_id = self.anchor_series.policy_version_id
            if dependent_version_id and anchor_version_id and dependent_version_id != anchor_version_id:
                raise ValidationError("Dependency rules must reference series from the same policy version.")

            if self.dependent_slot_number and not self.dependent_series.rules.filter(slot_number=self.dependent_slot_number).exists():
                raise ValidationError("Dependency rules can only reference dependent slots that exist in the dependent series.")

            if self.anchor_slot_number and not self.anchor_series.rules.filter(slot_number=self.anchor_slot_number).exists():
                raise ValidationError("Dependency rules can only reference anchor slots that exist in the anchor series.")

            if self.block_if_anchor_missing:
                reciprocal_rules = DependencyRule.objects.filter(
                    dependent_series_id=self.anchor_series_id,
                    anchor_series_id=self.dependent_series_id,
                    block_if_anchor_missing=True,
                    active=True,
                ).exclude(pk=self.pk)
                for reciprocal_rule in reciprocal_rules:
                    dependent_slot_matches = (
                        self.dependent_slot_number is None
                        or reciprocal_rule.anchor_slot_number is None
                        or self.dependent_slot_number == reciprocal_rule.anchor_slot_number
                    )
                    anchor_slot_matches = (
                        self.anchor_slot_number is None
                        or reciprocal_rule.dependent_slot_number is None
                        or self.anchor_slot_number == reciprocal_rule.dependent_slot_number
                    )
                    if dependent_slot_matches and anchor_slot_matches:
                        raise ValidationError(
                            "Dependency rules cannot create a direct blocking cycle between two series slots."
                        )


class GlobalConstraintRule(models.Model):
    CONSTRAINT_LIVE_LIVE_SPACING = 'live_live_spacing'
    CONSTRAINT_TYPE_CHOICES = [
        (CONSTRAINT_LIVE_LIVE_SPACING, 'Live/live spacing'),
    ]

    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=120, unique=True)
    constraint_type = models.CharField(max_length=50, choices=CONSTRAINT_TYPE_CHOICES)
    min_spacing_days = models.PositiveIntegerField(default=28)
    policy_version = models.ForeignKey(
        PolicyVersion,
        on_delete=models.PROTECT,
        related_name='global_constraints',
        null=True,
        blank=True,
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['constraint_type', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)
        if not self.policy_version_id:
            self.policy_version = PolicyVersion.get_active()
        super().save(*args, **kwargs)

    @classmethod
    def get_live_spacing_days(cls, policy_version=None):
        query = cls.objects.filter(
            active=True,
            constraint_type=cls.CONSTRAINT_LIVE_LIVE_SPACING,
        )
        if policy_version is not None:
            query = query.filter(policy_version=policy_version)
        rule = query.order_by('-id').first()
        if rule:
            return rule.min_spacing_days
        return 28
