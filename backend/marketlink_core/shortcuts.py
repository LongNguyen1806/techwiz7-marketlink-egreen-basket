from django.core.exceptions import ObjectDoesNotExist

from marketlink_core.exceptions import ResourceNotFoundError


def get_or_404(queryset, *, message: str, **lookup):
    try:
        return queryset.get(**lookup)
    except ObjectDoesNotExist:
        raise ResourceNotFoundError(message) from None
