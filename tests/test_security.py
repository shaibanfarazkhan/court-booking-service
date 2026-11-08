from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification() -> None:
    """Verify that hash_password generates verifiable hashes."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword999!", hashed) is False


def test_password_exceeding_72_bytes_rejected_by_hasher() -> None:
    """Verify that passwords exceeding 72 bytes are rejected by hash_password."""
    long_password = "A" * 71 + "1a"  # 73 characters / 73 bytes
    with pytest.raises(ValueError, match="password cannot be longer than 72 bytes"):
        hash_password(long_password)


def test_verify_password_exceeding_72_bytes_returns_false() -> None:
    """Verify that verify_password with >72 byte password returns False."""
    hashed = hash_password("ValidPassword123!")
    assert verify_password("A" * 73, hashed) is False


def test_create_and_decode_access_token() -> None:
    """Verify access token creation and payload decoding."""
    payload_data = {
        "sub": "b2c019d0-0f2b-4d43-9831-29158c56fa2b",
        "email": "player@courtbooking.com",
        "role": "MEMBER",
    }
    token = create_access_token(data=payload_data)
    decoded = decode_token(token)

    assert decoded["sub"] == payload_data["sub"]
    assert decoded["email"] == payload_data["email"]
    assert decoded["role"] == payload_data["role"]
    assert decoded["type"] == "access"
    assert "exp" in decoded


def test_create_and_decode_refresh_token() -> None:
    """Verify refresh token creation and payload decoding."""
    payload_data = {"sub": "b2c019d0-0f2b-4d43-9831-29158c56fa2b"}
    token = create_refresh_token(data=payload_data)
    decoded = decode_token(token)

    assert decoded["sub"] == payload_data["sub"]
    assert decoded["type"] == "refresh"
    assert "exp" in decoded


def test_decode_expired_token_raises_error() -> None:
    """Verify that decoding a token with past expiration raises an error."""
    payload_data = {"sub": "user-123"}
    # Token expired 10 minutes ago
    expired_token = create_access_token(
        data=payload_data,
        expires_delta=timedelta(minutes=-10),
    )

    with pytest.raises((ValueError, Exception)):
        decode_token(expired_token)


def test_decode_tampered_token_raises_error() -> None:
    """Verify that modifying token payload breaks cryptographic signature."""
    token = create_access_token(data={"sub": "user-123"})
    parts = token.split(".")
    tampered_token = f"{parts[0]}.eyJhZG1pbiI6dHJ1ZX0.{parts[2]}"

    with pytest.raises((ValueError, Exception)):
        decode_token(tampered_token)
