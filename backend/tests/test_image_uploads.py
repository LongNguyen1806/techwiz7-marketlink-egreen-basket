"""F-a / AD-d: uploaded images are checked for size and pixel count, then re-encoded."""

import io
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from catalog.services.farmer_product import validate_image_upload
from marketlink_core.exceptions import BusinessValidationError
from markets.models import Market

GPS_TAG = 0x8825
ORIENTATION_TAG = 0x0112
ROTATE_90_CW = 6


def _encode(image: Image.Image, image_format: str, **save_args) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, **save_args)
    return buffer.getvalue()


def _upload(content: bytes, name: str = "photo.jpg", content_type: str = "image/jpeg") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type=content_type)


def _png(size) -> bytes:
    # 1-bit black canvas: a huge picture that compresses to a few kilobytes.
    return _encode(Image.new("1", size), "PNG")


class TestPixelLimits:
    def test_canvas_over_the_limit_is_rejected(self):
        with pytest.raises(BusinessValidationError) as error:
            validate_image_upload(_upload(_png((7000, 7000)), "big.png", "image/png"))

        assert "image" in error.value.errors

    def test_decompression_bomb_is_a_validation_error_not_a_crash(self):
        # Above Pillow's own hard limit (~179 megapixels) Image.open raises DecompressionBombError.
        with pytest.raises(BusinessValidationError):
            validate_image_upload(_upload(_png((14000, 14000)), "bomb.png", "image/png"))

    def test_normal_photo_passes(self):
        cleaned = validate_image_upload(_upload(_encode(Image.new("RGB", (1200, 900), "green"), "JPEG")))

        assert cleaned.name == "image.jpg"


class TestReencoding:
    def test_exif_including_gps_is_removed(self):
        image = Image.new("RGB", (40, 20), "red")
        exif = image.getexif()
        exif[0x010F] = "PhoneMaker"
        exif.get_ifd(GPS_TAG)[2] = (10.0, 45.0, 0.0)
        content = _encode(image, "JPEG", exif=exif.tobytes())
        assert Image.open(io.BytesIO(content)).getexif()  # the fixture really carries EXIF

        cleaned = validate_image_upload(_upload(content))

        assert not Image.open(io.BytesIO(cleaned.read())).getexif()

    def test_rotation_flag_is_applied_before_exif_is_dropped(self):
        image = Image.new("RGB", (40, 20), "red")
        exif = image.getexif()
        exif[ORIENTATION_TAG] = ROTATE_90_CW
        content = _encode(image, "JPEG", exif=exif.tobytes())

        cleaned = validate_image_upload(_upload(content))

        assert Image.open(io.BytesIO(cleaned.read())).size == (20, 40)

    def test_bytes_appended_after_the_picture_are_dropped(self):
        payload = b"<script>alert(1)</script>"
        content = _encode(Image.new("RGB", (30, 30), "blue"), "PNG") + payload

        cleaned = validate_image_upload(_upload(content, "photo.png", "image/png"))

        assert payload not in cleaned.read()

    @pytest.mark.parametrize(
        ("image_format", "mode", "extension", "content_type"),
        [
            ("JPEG", "RGB", ".jpg", "image/jpeg"),
            ("PNG", "RGBA", ".png", "image/png"),
            ("WEBP", "RGBA", ".webp", "image/webp"),
        ],
    )
    def test_format_and_transparency_are_kept(self, image_format, mode, extension, content_type):
        content = _encode(Image.new(mode, (30, 20), (0, 128, 0, 100)[: len(mode)]), image_format)

        cleaned = validate_image_upload(_upload(content, f"x{extension}", content_type))

        stored = Image.open(io.BytesIO(cleaned.read()))
        assert (cleaned.name, cleaned.content_type) == (f"image{extension}", content_type)
        assert (stored.format, stored.size, stored.mode) == (image_format, (30, 20), mode)

    def test_upload_can_be_read_again_after_checking(self):
        # FA-03 re-reads the file when a deadlock retry saves it a second time.
        cleaned = validate_image_upload(_upload(_encode(Image.new("RGB", (10, 10)), "JPEG")))
        first = cleaned.read()
        cleaned.seek(0)

        assert cleaned.read() == first


def _market_payload(**overrides):
    body = {
        "name": "Riverside Market",
        "address": "88 Riverside Road",
        "latitude": "10.800000",
        "longitude": "106.700000",
        "operating_days": [1, 6],
        "open_time": "07:00",
        "close_time": "13:00",
    }
    body.update(overrides)
    return body


@pytest.mark.django_db
class TestMarketImages:
    def test_market_image_over_2mb_is_rejected(self, admin_client):
        noise = Image.frombytes("RGB", (1200, 1200), os.urandom(1200 * 1200 * 3))
        content = _encode(noise, "PNG")
        assert len(content) > 2 * 1024 * 1024

        response = admin_client.post(
            reverse("admin-market-list"),
            _market_payload(image=_upload(content, "market.png", "image/png")),
            format="multipart",
        )

        assert response.status_code == 400
        assert "image" in response.data["errors"]
        assert not Market.objects.exists()

    def test_market_image_must_be_a_real_image(self, admin_client):
        response = admin_client.post(
            reverse("admin-market-list"),
            _market_payload(image=_upload(b"<html></html>", "market.png", "image/png")),
            format="multipart",
        )

        assert response.status_code == 400
        assert "image" in response.data["errors"]

    def test_valid_market_image_is_stored_with_its_real_format(self, admin_client):
        content = _encode(Image.new("RGB", (60, 40), "orange"), "PNG")

        response = admin_client.post(
            reverse("admin-market-list"),
            _market_payload(image=_upload(content, "Holiday.JPG", "image/jpeg")),
            format="multipart",
        )

        assert response.status_code == 201, response.data
        market = Market.objects.get()
        try:
            assert market.image.name.startswith("markets/")
            assert market.image.name.endswith(".png")
            assert "Holiday" not in market.image.name
        finally:
            market.image.delete(save=False)
