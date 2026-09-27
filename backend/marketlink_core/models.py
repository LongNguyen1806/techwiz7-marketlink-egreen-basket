import uuid
from pathlib import Path

from django.db import models
from django.utils.deconstruct import deconstructible


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CreatedAtModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class HistoryRequestMeta(models.Model):
    request_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


# Defence in depth (NFR-01): only image extensions are kept; anything else is stored without one,
# so a crafted name such as "x.html" can never be served with an executable content type.
SAFE_UPLOAD_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})


@deconstructible
class UUIDUploadTo:
    def __init__(self, folder: str) -> None:
        self.folder = folder

    def __call__(self, instance, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext not in SAFE_UPLOAD_EXTENSIONS:
            ext = ""
        return f"{self.folder}/{uuid.uuid4().hex}{ext}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, UUIDUploadTo) and self.folder == other.folder
