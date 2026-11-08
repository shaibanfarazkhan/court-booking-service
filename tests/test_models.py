from app.models import (
    Admin,
    Base,
    Booking,
    Court,
    CourtImage,
    Payment,
    Sport,
    TimeSlot,
    User,
    Venue,
)


def test_registered_metadata_tables() -> None:
    """Ensure all core entities are registered in SQLAlchemy metadata."""
    expected_tables = {
        "users",
        "admins",
        "venues",
        "sports",
        "courts",
        "court_images",
        "time_slots",
        "bookings",
        "payments",
    }
    registered_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(registered_tables)


def test_entity_relationships_declared() -> None:
    """Verify that models expose the expected ORM relationship properties."""
    assert hasattr(User, "admin_profile")
    assert hasattr(User, "bookings")
    assert hasattr(User, "payments")
    assert hasattr(Admin, "user")
    assert hasattr(Venue, "courts")
    assert hasattr(Sport, "courts")
    assert hasattr(Court, "venue")
    assert hasattr(Court, "sport")
    assert hasattr(Court, "images")
    assert hasattr(Court, "time_slots")
    assert hasattr(Court, "bookings")
    assert hasattr(CourtImage, "court")
    assert hasattr(TimeSlot, "court")
    assert hasattr(TimeSlot, "booking")
    assert hasattr(Booking, "user")
    assert hasattr(Booking, "court")
    assert hasattr(Booking, "time_slot")
    assert hasattr(Booking, "payments")
    assert hasattr(Payment, "booking")
    assert hasattr(Payment, "user")

