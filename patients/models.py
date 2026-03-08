from django.db import models
from vaccines.models import Vaccine

class Child(models.Model):
    SEX_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    id = models.CharField(max_length=50, primary_key=True, help_text="National ID or Medical Record Number")
    name = models.CharField(max_length=200)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES)
    dob = models.DateField(verbose_name="Date of Birth")
    address = models.TextField(blank=True, null=True)
    parents_name = models.CharField(max_length=200, blank=True, null=True)
    contact_info = models.CharField(max_length=200, blank=True, null=True)
    unknown_status = models.BooleanField(default=False, help_text="Treat as unvaccinated if history is entirely unknown")

    def __str__(self):
        return f"{self.name} ({self.id})"

class VaccinationRecord(models.Model):
    REASON_TOO_EARLY = 'too_early'
    REASON_TOO_LATE = 'too_late'
    REASON_INTERVAL = 'short_interval'
    REASON_WRONG_VACCINE = 'wrong_vaccine'

    INVALID_REASON_CHOICES = [
        (REASON_TOO_EARLY, 'Too Early (min age not met)'),
        (REASON_TOO_LATE, 'Too Late (max age exceeded)'),
        (REASON_INTERVAL, 'Interval Too Short'),
        (REASON_WRONG_VACCINE, 'Wrong Vaccine for Age'),
    ]

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='vaccination_records')
    vaccine = models.ForeignKey(Vaccine, on_delete=models.PROTECT, related_name='administered_records')
    date_given = models.DateField()
    lot_number = models.CharField(max_length=100, blank=True, null=True)
    administer_site = models.CharField(max_length=100, blank=True, null=True)
    invalid_flag = models.BooleanField(default=False, help_text="Flagged if administered incorrectly")
    invalid_reason = models.CharField(
        max_length=50, blank=True, null=True,
        choices=INVALID_REASON_CHOICES,
        help_text="Structured reason code for why this dose is invalid"
    )
    notes = models.TextField(blank=True, null=True, help_text="Human-readable explanation of any issue")

    class Meta:
        ordering = ['-date_given']

    def __str__(self):
        return f"{self.vaccine.name} for {self.child.name} on {self.date_given}"
