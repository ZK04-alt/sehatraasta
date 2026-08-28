from enum import Enum


class PresenceState(Enum):
    PRESENT = "present"
    MISSING = "missing"
    PENDING = "pending"
    NOT_APPLICABLE = "not applicable"


class ReferralStatus(Enum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready for review"
    ARCHIVED = "archived"


class Language(Enum):
    ENGLISH = 1
    URDU = 2
    PASHTO = 3
