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


class InvestigationOrderStatus(Enum):
    ORDERED = "ordered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CostCategory(Enum):
    TRAVEL = "travel"
    MEDICATION = "medication"
    INVESTIGATION = "investigation"
    IMAGING = "imaging"
    CONSULTATION = "consultation"
    ACCOMMODATION = "accommodation"
    OTHER = "other"


class ReviewCategory(Enum):
    ENCOUNTERS = "encounters"
    MEDICATION_LIST = "medication list"
    INVESTIGATION_ORDERS = "investigation orders"
    DIAGNOSTIC_RESULTS = "diagnostic results"
    IMAGING_REPORTS = "imaging reports"
    INSTRUCTIONS = "instructions"
    ATTACHMENTS = "attachments"
    COSTS = "costs"
