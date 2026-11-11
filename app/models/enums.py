import enum


class UserRole(enum.StrEnum):
    """User access control roles."""

    MEMBER = "MEMBER"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class CourtType(enum.StrEnum):
    """Court enclosure configuration."""

    INDOOR = "INDOOR"
    OUTDOOR = "OUTDOOR"


class SurfaceType(enum.StrEnum):
    """Playing court surface material."""

    HARD = "HARD"
    CLAY = "CLAY"
    GRASS = "GRASS"
    SYNTHETIC = "SYNTHETIC"
    WOOD = "WOOD"


class SlotStatus(enum.StrEnum):
    """Time slot availability status."""

    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"


class BookingStatus(enum.StrEnum):
    """Booking reservation lifecycle state."""

    HELD = "HELD"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class RecurrenceType(enum.StrEnum):
    """Supported recurring booking patterns."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class PaymentStatus(enum.StrEnum):
    """Financial transaction settlement status."""

    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentMethod(enum.StrEnum):
    """Supported payment settlement instruments."""

    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    UPI = "UPI"
    STRIPE = "STRIPE"
    WALLET = "WALLET"
