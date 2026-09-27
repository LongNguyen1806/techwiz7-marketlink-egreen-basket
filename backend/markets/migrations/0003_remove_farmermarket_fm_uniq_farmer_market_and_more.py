from django.db import migrations, models


def keep_one_market_per_stall(apps, schema_editor):
    """Drop surplus registrations so the unique index below can be created.

    A stall trades at exactly one market, but nothing enforced that before this migration, so
    an existing database may hold several rows per farmer. The earliest one is kept, being the
    original registration; the rest go, and their pickup slots go with them by cascade.

    Orders point at a pickup slot with SET_NULL and keep their own copy of the stall label and
    the collection window (D-007), so a cancelled slot cannot rewrite an order's history.
    """
    FarmerMarket = apps.get_model("markets", "FarmerMarket")
    seen: set[int] = set()
    surplus: list[int] = []
    for pk, farmer_id in FarmerMarket.objects.order_by("id").values_list("id", "farmer_id"):
        if farmer_id in seen:
            surplus.append(pk)
        else:
            seen.add(farmer_id)
    if surplus:
        FarmerMarket.objects.filter(id__in=surplus).delete()


def noop(apps, schema_editor):
    """Nothing to undo: the deleted rows are gone, and re-inventing them would be a guess."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_historicalcustomerprofile"),
        ("markets", "0002_historicalfarmerclosure_historicalfarmermarket_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="farmermarket",
            name="fm_uniq_farmer_market",
        ),
        migrations.RunPython(keep_one_market_per_stall, noop),
        migrations.AddConstraint(
            model_name="farmermarket",
            constraint=models.UniqueConstraint(fields=("farmer",), name="fm_uniq_farmer"),
        ),
    ]
