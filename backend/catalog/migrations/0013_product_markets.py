import django.db.models.deletion
from django.db import migrations, models

APPROVED = "APPROVED"


def link_existing_products(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductMarket = apps.get_model("catalog", "ProductMarket")
    FarmerMarket = apps.get_model("markets", "FarmerMarket")
    OrderItem = apps.get_model("orders", "OrderItem")

    stalls_by_farmer: dict[int, list[tuple[int, int]]] = {}
    for stall_id, farmer_id, market_id in FarmerMarket.objects.filter(status=APPROVED).values_list(
        "id", "farmer_id", "market_id"
    ):
        stalls_by_farmer.setdefault(farmer_id, []).append((stall_id, market_id))

    ordered_markets: dict[int, set[int]] = {}
    for product_id, market_id in (
        OrderItem.objects.filter(product__isnull=False).values_list("product_id", "order__market_id").distinct()
    ):
        ordered_markets.setdefault(product_id, set()).add(market_id)

    links = []
    for product_id, farmer_id in Product.objects.values_list("id", "farmer_id"):
        stalls = stalls_by_farmer.get(farmer_id, [])
        where_sold = ordered_markets.get(product_id, set())
        chosen = [stall_id for stall_id, market_id in stalls if market_id in where_sold]
        if not chosen:
            chosen = [stall_id for stall_id, _market_id in stalls]
        links.extend(ProductMarket(product_id=product_id, farmer_market_id=stall_id) for stall_id in chosen)
    ProductMarket.objects.bulk_create(links, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0012_product_market_exclusion"),
        ("markets", "0005_farmermarket_status"),
        ("orders", "0006_reschedule"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductMarket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "farmer_market",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_links",
                        to="markets.farmermarket",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="market_links",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "db_table": "product_markets",
            },
        ),
        migrations.AddConstraint(
            model_name="productmarket",
            constraint=models.UniqueConstraint(fields=("product", "farmer_market"), name="pm_uniq_product_stall"),
        ),
        migrations.RunPython(link_existing_products, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="ProductMarketExclusion",
        ),
    ]
