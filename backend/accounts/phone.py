import re

_SEPARATORS = re.compile(r"[\s.\-()]")


def normalize_phone(raw: str | None) -> str:
    phone = _SEPARATORS.sub("", raw or "")
    if phone.startswith("+84"):
        phone = "0" + phone[3:]
    elif phone.startswith("84") and len(phone) == 11:
        phone = "0" + phone[2:]
    return phone
