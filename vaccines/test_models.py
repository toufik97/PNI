from django.db import models


class TestScenario(models.Model):
    CATEGORY_CHOICES = [
        ('routine', 'Routine Schedule'),
        ('catchup', 'Catch-up / Late Start'),
        ('validation', 'Dose Validation'),
        ('dependency', 'Cross-Series Dependency'),
        ('edge_case', 'Edge Case'),
        ('regression', 'Bug Regression'),
    ]
    STATUS_CHOICES = [
        ('untested', 'Not Run Yet'),
        ('pass', 'Pass'),
        ('fail', 'Fail'),
    ]

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='routine')
    age_days = models.PositiveIntegerField(help_text="Age of the virtual patient in days")

    # Vaccination history: [{"vax": "Penta", "days_ago": 60, "administered_elsewhere": false}]
    history = models.JSONField(default=list, blank=True)

    # Expected engine outcomes (all optional — only populated fields are checked)
    expected_due = models.JSONField(default=list, blank=True, help_text="List of vaccine names expected as DUE")
    expected_upcoming = models.JSONField(default=list, blank=True, help_text="List of vaccine names expected as UPCOMING")
    expected_missing = models.JSONField(default=list, blank=True, help_text="List of vaccine names expected as MISSING")
    expected_blocked = models.JSONField(default=list, blank=True, help_text="List of vaccine names expected as BLOCKED")
    expected_invalid = models.JSONField(
        default=list, blank=True,
        help_text='List of invalid dose specs: [{"vax": "Penta", "index": 1, "reason": "short_interval"}]'
    )

    # Run state
    last_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='untested')
    last_result = models.JSONField(null=True, blank=True, help_text="Structured diff from last run")
    last_run_at = models.DateTimeField(null=True, blank=True)

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        icon = {'pass': '✅', 'fail': '❌', 'untested': '⏳'}.get(self.last_status, '?')
        return f"{icon} {self.name}"
