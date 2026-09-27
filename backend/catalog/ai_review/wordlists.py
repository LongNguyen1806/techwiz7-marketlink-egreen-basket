"""Word lists for the rule layer, and the text normalisation they are matched against.

Vietnamese needs care: stripping the tone marks turns several produce words into swear words
("bưởi" pomelo -> "buoi", "sung" fig -> "sung" gun, "lớn" big -> "lon"). So each list has two
halves:

* ``*_ASCII``: terms that stay unambiguous once tone marks are gone. They are matched on the
  stripped text, which also catches sellers who type without marks or with leetspeak.
* ``*_EXACT``: terms that are only offensive or prohibited *with* their marks. They are matched
  on the lower-cased text with marks kept, so "bưởi da xanh" never trips a swear-word check.

Short terms (four characters or fewer) are matched as whole words only, so "ass" does not fire
inside "grass" or "assam", and "dm" does not fire inside a longer word.
"""

import re
import unicodedata

# ---------------------------------------------------------------------------- normalisation

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
_SEPARATORS = re.compile(r"[\s._\-*+~^'\"`|/\\]+")
_REPEATS = re.compile(r"(.)\1{2,}")


def strip_marks(text: str) -> str:
    """Lower-case and drop Vietnamese tone marks (đ -> d)."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d").replace("Đ", "d"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def ascii_words(text: str) -> list[str]:
    """Stripped, leetspeak-decoded words: "Đ.M" -> ["d", "m"], "sh1t" -> ["shit"]."""
    cleaned = _REPEATS.sub(r"\1\1", strip_marks(text).translate(_LEET))
    return [word for word in re.split(r"[^a-z0-9]+", cleaned) if word]


def ascii_compact(text: str) -> str:
    """The stripped text with every separator removed, for spaced-out spellings ("f u c k")."""
    return "".join(ascii_words(text))


def marked_words(text: str) -> list[str]:
    """Lower-cased words with tone marks kept (NFC), for the exact lists."""
    normalised = unicodedata.normalize("NFC", text.lower())
    return [word for word in re.split(r"[^\w]+", normalised) if word]


# ---------------------------------------------------------------------------- lists

# Offensive language. English and Vietnamese, including common teencode abbreviations.
PROFANITY_ASCII = {
    # English
    "fuck", "fucking", "fucker", "motherfucker", "shit", "bullshit", "bitch", "cunt", "asshole",
    "bastard", "dick", "pussy", "whore", "slut", "nigger", "faggot", "retard", "ass", "wtf",
    # Vietnamese without marks that cannot be mistaken for a produce word
    "dit me", "dit con me", "du ma", "du me", "dcm", "dmm", "dkm", "vcl", "vkl", "clgt", "cmm",
    "dm", "vl", "occho", "oc cho", "thang cho", "con di", "cave",
}
PROFANITY_EXACT = {
    "địt", "đụ", "lồn", "cặc", "buồi", "đéo", "đĩ", "đm", "đcm", "đmm",
}

# Things a farmers' market must not sell, in English and Vietnamese.
PROHIBITED_ASCII = {
    # vehicles and electronics
    "motorbike", "motorcycle", "scooter", "car", "iphone", "samsung", "smartphone", "laptop",
    "tablet", "television", "headphone", "honda", "yamaha", "xe may", "xe dap dien", "dien thoai",
    "may tinh", "tivi", "tai nghe", "laptop cu",
    # weapons, drugs and gambling
    "gun", "pistol", "rifle", "ammo", "ammunition", "cannabis", "marijuana", "cocaine", "heroin",
    "meth", "kratom", "ma tuy", "can sa", "thuoc lac", "ke da", "dan duoc", "ca do", "lo de",
}
PROHIBITED_EXACT = {"súng", "đạn", "cần sa", "ma túy", "ma tuý"}

# Allowed at some markets but worth an admin's eye.
RESTRICTED_ASCII = {
    "vodka", "whisky", "whiskey", "cigarette", "cigar", "vape", "tobacco", "pesticide",
    "thuoc la", "thuoc tru sau", "thuoc diet co", "ruou manh",
}
RESTRICTED_EXACT = {"rượu", "thuốc lá"}

# Moving the sale off the platform.
CONTACT_WORDS = {"zalo", "facebook", "fb", "telegram", "whatsapp", "viber", "messenger", "inbox", "ib", "sdt", "hotline"}

CONTACT_PATTERNS = (
    ("phone number", re.compile(r"(?:\+?\d[\s.\-()]?){9,}")),
    ("email address", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("web link", re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+\.(?:com|vn|net|org|shop|store|me)\b", re.IGNORECASE)),
)


def _with_letter_runs(words: list[str]) -> list[str]:
    """Add runs of single letters as one word: "Đ.M" -> ["d", "m", "dm"]."""
    merged, run = list(words), []
    for word in [*words, ""]:
        if len(word) == 1:
            run.append(word)
            continue
        if len(run) >= 2:
            merged.append("".join(run))
        run = []
    return merged


def _contains(text: str, ascii_terms: set[str], exact_terms: set[str]) -> list[str]:
    words = _with_letter_runs(ascii_words(text))
    joined = " ".join(ascii_words(text))
    compact = ascii_compact(text)
    hits = []
    for term in ascii_terms:
        if " " in term:
            # Multi-word terms: as a phrase, or run together ("ditme", "d i t m e").
            if f" {term} " in f" {joined} " or (len(term) > 5 and term.replace(" ", "") in compact):
                hits.append(term)
        elif len(term) <= 4:
            if term in words:
                hits.append(term)
        elif term in words or (len(term) >= 6 and term in compact):
            hits.append(term)
    marked = set(marked_words(text))
    marked_joined = " ".join(marked_words(text))
    for term in exact_terms:
        if (" " in term and term in marked_joined) or term in marked:
            hits.append(term)
    return sorted(set(hits))


def find_profanity(text: str) -> list[str]:
    return _contains(text, PROFANITY_ASCII, PROFANITY_EXACT)


def find_prohibited(text: str) -> list[str]:
    return _contains(text, PROHIBITED_ASCII, PROHIBITED_EXACT)


def find_restricted(text: str) -> list[str]:
    return _contains(text, RESTRICTED_ASCII, RESTRICTED_EXACT)


def find_contact(text: str) -> list[str]:
    kinds = [label for label, pattern in CONTACT_PATTERNS if pattern.search(text)]
    if CONTACT_WORDS & set(ascii_words(text)):
        kinds.append("messaging app")
    return kinds
