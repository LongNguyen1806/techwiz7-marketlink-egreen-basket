# Farmer replies (Farmer branch) live in farmer_reply_service.py; re-exported so
# `from reviews.services import REPLY_MAX_LENGTH, reply_to_review` keeps working.
from reviews.services.farmer_reply_service import REPLY_MAX_LENGTH, reply_to_review  # noqa: F401
