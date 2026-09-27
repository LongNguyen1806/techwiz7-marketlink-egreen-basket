from django.db import migrations

from catalog.icons import CATEGORY_ICONS, LEGACY_ICON_ALIASES


def keep_only_produce_icons(apps, schema_editor):
    """Move every category onto an icon that still exists.

    The set was trimmed to what a farm grows: pictures of prepared food - pizza, beer, ice
    cream - are gone. A category left wearing one of those would fail validation the next time
    anybody edited it, for a value the admin never chose.

    Rows are fixed in id order so the result is the same on every database. An alias is used
    where one fits and the picture is still free; otherwise the category is handed the first
    unused name.
    """
    Category = apps.get_model("catalog", "Category")
    rows = list(Category.objects.order_by("id").values_list("id", "icon"))
    taken = {icon for _, icon in rows if icon in CATEGORY_ICONS}
    spare = iter(CATEGORY_ICONS)

    def next_free() -> str:
        for name in spare:
            if name not in taken:
                return name
        raise RuntimeError(
            f"There are more produce categories than icons ({len(CATEGORY_ICONS)} available). "
            "Add names to catalog/icons.py and the matching pictures to "
            "frontend/src/utils/categoryIcon.js, then run this migration again."
        )

    for pk, icon in rows:
        if icon in CATEGORY_ICONS:
            continue
        wanted = LEGACY_ICON_ALIASES.get((icon or "").strip().lower())
        if wanted is None or wanted in taken:
            wanted = next_free()
        taken.add(wanted)
        Category.objects.filter(pk=pk).update(icon=wanted)


def noop(apps, schema_editor):
    """Nothing to undo: the pictures that were dropped are not coming back."""


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_product_review_status"),
    ]

    operations = [
        migrations.RunPython(keep_only_produce_icons, noop),
    ]
