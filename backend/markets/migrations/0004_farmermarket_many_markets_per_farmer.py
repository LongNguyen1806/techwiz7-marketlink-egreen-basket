from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("markets", "0003_remove_farmermarket_fm_uniq_farmer_market_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="farmermarket",
            constraint=models.UniqueConstraint(fields=("farmer", "market"), name="fm_uniq_farmer_market"),
        ),
        migrations.RemoveConstraint(
            model_name="farmermarket",
            name="fm_uniq_farmer",
        ),
    ]
