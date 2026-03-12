from django.db import migrations, models
import django.db.models.deletion


def create_default_policy_version(apps, schema_editor):
    PolicyVersion = apps.get_model('vaccines', 'PolicyVersion')
    Series = apps.get_model('vaccines', 'Series')

    version, _ = PolicyVersion.objects.get_or_create(
        code='series-policy-v1',
        defaults={
            'name': 'Series Policy v1',
            'description': 'Default migrated policy version for the series-based engine.',
            'is_active': True,
        },
    )
    if not version.is_active:
        version.is_active = True
        version.save(update_fields=['is_active'])

    Series.objects.filter(policy_version__isnull=True).update(policy_version=version)


class Migration(migrations.Migration):

    dependencies = [
        ('vaccines', '0010_product_available_dependencyrule'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolicyVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=100, unique=True)),
                ('name', models.CharField(max_length=120, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('effective_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=False, help_text='Exactly one policy version should be active for scheduling.')),
                ('notes', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-is_active', 'name'],
            },
        ),
        migrations.AddField(
            model_name='series',
            name='policy_version',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='series', to='vaccines.policyversion'),
        ),
        migrations.RunPython(create_default_policy_version, migrations.RunPython.noop),
    ]
