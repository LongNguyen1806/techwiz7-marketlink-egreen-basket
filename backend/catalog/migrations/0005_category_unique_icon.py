from django.db import migrations, models

from catalog.icons import CATEGORY_ICONS, LEGACY_ICON_ALIASES


def give_every_category_its_own_icon(apps, schema_editor):
    """Make the data satisfy the unique index the operation below adds.

    Before this, several categories shared a picture and two names ("pepper", "flame") drew
    the same one. Rows are fixed in id order so the result is the same on every database:
    the earliest category keeps the icon it had, later ones that clash are handed the first
    unused name from the canonical list.
    """
    Category = apps.get_model("catalog", "Category")
    taken: set[str] = set()
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

    for category in Category.objects.order_by("id"):
        wanted = (category.icon or "").strip().lower()
        wanted = LEGACY_ICON_ALIASES.get(wanted, wanted)
        if wanted not in CATEGORY_ICONS or wanted in taken:
            wanted = next_free()
        taken.add(wanted)
        if wanted != category.icon:
            Category.objects.filter(pk=category.pk).update(icon=wanted)


def noop(apps, schema_editor):
    """Nothing to undo: the old duplicates were not worth recording, let alone restoring."""


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_historicalproduct_moderation_action_and_more"),
    ]

    operations = [
        migrations.RunPython(give_every_category_its_own_icon, noop),
        migrations.AlterField(
            model_name="category",
            name="icon",
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
