from django.db import migrations
from django.utils.text import slugify


def _unique_slug(existing, raw_value, fallback):
    base = slugify(raw_value) or fallback
    candidate = base
    index = 2
    while candidate in existing:
        candidate = f"{base}-{index}"
        index += 1
    existing.add(candidate)
    return candidate


def forwards(apps, schema_editor):
    Vaccine = apps.get_model('vaccines', 'Vaccine')
    ScheduleRule = apps.get_model('vaccines', 'ScheduleRule')
    VaccineGroup = apps.get_model('vaccines', 'VaccineGroup')
    GroupRule = apps.get_model('vaccines', 'GroupRule')
    Product = apps.get_model('vaccines', 'Product')
    Series = apps.get_model('vaccines', 'Series')
    SeriesProduct = apps.get_model('vaccines', 'SeriesProduct')
    SeriesRule = apps.get_model('vaccines', 'SeriesRule')

    existing_product_codes = set(Product.objects.values_list('code', flat=True))
    product_by_vaccine_id = {}
    for vaccine in Vaccine.objects.all().order_by('id'):
        product = Product.objects.filter(vaccine_id=vaccine.id).first()
        if product is None:
            product = Product.objects.create(
                vaccine_id=vaccine.id,
                code=_unique_slug(existing_product_codes, vaccine.name, f"product-{vaccine.id}"),
                description=vaccine.description,
            )
        product_by_vaccine_id[vaccine.id] = product

    existing_series_codes = set(Series.objects.values_list('code', flat=True))
    for group in VaccineGroup.objects.all().order_by('id'):
        series = Series.objects.filter(legacy_group_id=group.id).first()
        if series is None:
            series = Series.objects.create(
                name=group.name,
                code=_unique_slug(existing_series_codes, group.name, f"series-{group.id}"),
                min_valid_interval_days=group.min_valid_interval_days,
                mixing_policy='age_rule',
                legacy_group_id=group.id,
            )

        for priority, vaccine_id in enumerate(group.vaccines.values_list('id', flat=True)):
            product = product_by_vaccine_id.get(vaccine_id)
            if product is None:
                continue
            SeriesProduct.objects.get_or_create(
                series_id=series.id,
                product_id=product.id,
                defaults={'priority': priority},
            )

        rules = GroupRule.objects.filter(group_id=group.id).order_by('prior_doses', 'min_age_days', 'id')
        for rule in rules:
            product = product_by_vaccine_id.get(rule.vaccine_to_give_id)
            if product is None:
                continue

            slot_number = rule.prior_doses + 1
            schedule_rule = ScheduleRule.objects.filter(
                vaccine_id=rule.vaccine_to_give_id,
                dose_number=slot_number,
            ).first()
            min_age = max(rule.min_age_days, schedule_rule.min_age_days) if schedule_rule else rule.min_age_days
            recommended_age = max(min_age, schedule_rule.recommended_age_days) if schedule_rule else rule.min_age_days
            overdue_age = (
                schedule_rule.overdue_age_days
                if schedule_rule and schedule_rule.overdue_age_days is not None
                else recommended_age
            )
            dose_amount = rule.dose_amount or (schedule_rule.dose_amount if schedule_rule else None)

            SeriesRule.objects.get_or_create(
                series_id=series.id,
                prior_valid_doses=rule.prior_doses,
                min_age_days=min_age,
                product_id=product.id,
                defaults={
                    'slot_number': slot_number,
                    'recommended_age_days': recommended_age,
                    'overdue_age_days': overdue_age,
                    'max_age_days': rule.max_age_days,
                    'min_interval_days': rule.min_interval_days,
                    'dose_amount': dose_amount,
                },
            )


def backwards(apps, schema_editor):
    # Keep the migrated policy objects in place on rollback to avoid destructive data loss.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('vaccines', '0008_product_series_seriesproduct_series_products_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
