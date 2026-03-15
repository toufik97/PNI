from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Vaccine(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Penta, BCG, MMR")
    live = models.BooleanField(default=False, help_text="Is this a live attenuated vaccine?")
    display_name = models.CharField(max_length=200, blank=True, null=True, help_text="Full human-readable name, e.g. 'Pentavalent (DTP + HBV + Hib)'")
    protects_against = models.TextField(blank=True, null=True, help_text="Comma-separated disease list shown in UI")
    clinical_notes = models.TextField(blank=True, null=True, help_text="Contextual notes like catch-up rules or admin guidance")
    compatible_live_vaccines = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        help_text="Other live vaccines that can be given safely within 28 days (e.g. OPV)"
    )
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.display_name:
            return f"{self.display_name} ({self.name})"
        return self.name


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
        return str(self.vaccine)

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

        candidate_slots = self.series.rules.filter(product_id=self.to_product_id) if self.series_id and self.to_product_id else None
        if candidate_slots is not None:
            if self.start_slot_number is not None:
                candidate_slots = candidate_slots.filter(slot_number__gte=self.start_slot_number)
            if self.end_slot_number is not None:
                candidate_slots = candidate_slots.filter(slot_number__lte=self.end_slot_number)
            if not candidate_slots.exists():
                raise ValidationError('Transition rules must target at least one slot that already allows the destination product.')

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
    dependent_product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependent_dependency_rules',
        help_text="Optional: Apply this rule only when using this specific product",
    )
    anchor_product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='anchor_dependency_rules',
        help_text="Optional: Apply this rule only if the anchor was this specific product",
    )
    min_offset_days = models.PositiveIntegerField(default=0, help_text="Minimum days after the anchor slot")
    block_if_anchor_missing = models.BooleanField(
        default=True,
        help_text="If enabled, the dependent slot stays blocked until the anchor slot exists",
    )
    is_coadmin = models.BooleanField(
        default=False,
        help_text="If enabled, missing anchor generates a co-administration warning instead of a block (block_if_anchor_missing should typically be false)",
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
                # Transitive cycle detection
                if self.is_transitive_cycle(self.dependent_series, self.anchor_series):
                    raise ValidationError(
                        "Dependency rules cannot create a blocking cycle across multiple series slots."
                    )

    def is_transitive_cycle(self, dependent, anchor):
        """Standard DFS to find if there is a path from dependent to anchor."""
        visited = {dependent.id}
        stack = [dependent]
        
        while stack:
            current = stack.pop()
            if current.id == anchor.id:
                return True
            
            # Find all rules where 'current' is the ANCHOR (blocking something else)
            # Actually we want to see if we can reach 'anchor' from 'dependent'
            # But wait, the rule is dependent -> anchor.
            # A cycle is dependent -> anchor -> ... -> dependent.
            # So we check if there's already a path from anchor to dependent.
            
        # Let's use a more robust helper
        return self._has_path(anchor, dependent)

    def _has_path(self, start_series, target_series):
        visited = set()
        stack = [start_series.id]
        
        while stack:
            current_id = stack.pop()
            if current_id == target_series.id:
                return True
            
            if current_id in visited:
                continue
            visited.add(current_id)
            
            # Follow the dependency chain: if current_id depends on something, 
            # we want to follow THAT something.
            # Wait, no. A cycle exists if target is already reachable from start? 
            # If we add B -> A, we check if A -> ... -> B already exists.
            # A -> ... -> B means A depends on something that depends on B.
            # So from current_node, we look for rules where current_node is the DEPENDENT.
            next_ids = DependencyRule.objects.filter(
                dependent_series_id=current_id,
                block_if_anchor_missing=True,
                active=True
            ).values_list('anchor_series_id', flat=True)
            
            for nid in next_ids:
                if nid not in visited:
                    stack.append(nid)
        return False



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
        return 0
