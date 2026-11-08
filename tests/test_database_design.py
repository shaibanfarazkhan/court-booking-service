from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.models import (
    Booking,
    Court,
    Payment,
    TimeSlot,
    Venue,
)


def test_table_check_constraints() -> None:
    """Verify that all financial and operational check constraints are declared."""
    # Courts check constraint
    court_checks = {
        c.name for c in Court.__table__.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_courts_positive_base_price" in court_checks

    # TimeSlots check constraints
    slot_checks = {
        c.name for c in TimeSlot.__table__.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_time_slots_valid_duration" in slot_checks
    assert "ck_time_slots_positive_price" in slot_checks

    # Bookings check constraints
    booking_checks = {
        c.name for c in Booking.__table__.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_bookings_positive_total_amount" in booking_checks

    # Payments check constraints
    payment_checks = {
        c.name for c in Payment.__table__.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_payments_positive_amount" in payment_checks
    assert "ck_payments_positive_refund_amount" in payment_checks
    assert "ck_payments_refund_lte_amount" in payment_checks

    # Venues check constraint
    venue_checks = {
        c.name for c in Venue.__table__.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_venues_valid_operating_hours" in venue_checks


def test_table_unique_constraints() -> None:
    """Verify unique constraints and natural business keys."""
    # Court uniqueness per venue
    court_uqs = {
        c.name for c in Court.__table__.constraints if isinstance(c, UniqueConstraint)
    }
    assert "uq_courts_venue_id_name" in court_uqs

    # Slot uniqueness per court and start time
    slot_uqs = {
        c.name
        for c in TimeSlot.__table__.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert "uq_time_slots_court_start" in slot_uqs

    # Booking 1:1 on time_slot_id
    time_slot_col = Booking.__table__.columns["time_slot_id"]
    assert time_slot_col.unique is True


def test_foreign_key_deletion_rules() -> None:
    """Verify CASCADE and RESTRICT foreign key deletion semantics."""
    court_fks = [
        c for c in Court.__table__.constraints if isinstance(c, ForeignKeyConstraint)
    ]
    venue_fk = next(
        fk
        for fk in court_fks
        if "venues.id" in [elem.target_fullname for elem in fk.elements]
    )
    assert venue_fk.ondelete == "CASCADE"

    sport_fk = next(
        fk
        for fk in court_fks
        if "sports.id" in [elem.target_fullname for elem in fk.elements]
    )
    assert sport_fk.ondelete == "RESTRICT"

    slot_fks = [
        c for c in TimeSlot.__table__.constraints if isinstance(c, ForeignKeyConstraint)
    ]
    court_slot_fk = next(
        fk
        for fk in slot_fks
        if "courts.id" in [elem.target_fullname for elem in fk.elements]
    )
    assert court_slot_fk.ondelete == "CASCADE"

    booking_fks = [
        c for c in Booking.__table__.constraints if isinstance(c, ForeignKeyConstraint)
    ]
    user_booking_fk = next(
        fk
        for fk in booking_fks
        if "users.id" in [elem.target_fullname for elem in fk.elements]
    )
    assert user_booking_fk.ondelete == "RESTRICT"


def test_table_indexes() -> None:
    """Verify critical composite query indexes."""
    slot_indexes = {idx.name for idx in TimeSlot.__table__.indexes}
    assert "ix_time_slots_court_start_end_status" in slot_indexes

    booking_indexes = {idx.name for idx in Booking.__table__.indexes}
    assert "ix_bookings_user_status" in booking_indexes
    assert "ix_bookings_court_status" in booking_indexes
    assert "ix_bookings_held_active" in booking_indexes

    payment_indexes = {idx.name for idx in Payment.__table__.indexes}
    assert "ix_payments_booking_status" in payment_indexes
    assert "ix_payments_user_created" in payment_indexes
