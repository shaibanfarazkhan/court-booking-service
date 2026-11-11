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


class PricingRuleType(enum.StrEnum):
    """Pricing condition represented by a configurable rule."""

    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    HOLIDAY = "HOLIDAY"
    PEAK = "PEAK"
    WEEKEND = "WEEKEND"
    OFF_PEAK = "OFF_PEAK"
    PROMOTION = "PROMOTION"


class PricingEffect(enum.StrEnum):
    """How a rule changes the current hourly price."""

    OVERRIDE = "OVERRIDE"
    SURCHARGE = "SURCHARGE"
    DISCOUNT = "DISCOUNT"


class PricingValueType(enum.StrEnum):
    """Unit used by a pricing rule's value."""

    FIXED_PRICE = "FIXED_PRICE"
    AMOUNT = "AMOUNT"
    PERCENTAGE = "PERCENTAGE"


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
