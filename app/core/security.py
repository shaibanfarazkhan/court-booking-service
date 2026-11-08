"""Cryptographic security utilities for password hashing and JWT token handling."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password Hashing Layer
# ---------------------------------------------------------------------------
try:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(password: str) -> str:
        """Hash a plain text password using bcrypt."""
        return str(pwd_context.hash(password))

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its bcrypt hash."""
        return bool(pwd_context.verify(plain_password, hashed_password))

except ImportError:
    # Pure Python PBKDF2-HMAC-SHA256 fallback when passlib/bcrypt is not installed
    def hash_password(password: str) -> str:
        """Hash a plain text password using PBKDF2-HMAC-SHA256 with 100,000 rounds."""
        salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        )
        return f"pbkdf2:sha256:100000${salt}${key.hex()}"

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its PBKDF2 hash."""
        if not hashed_password.startswith("pbkdf2:sha256:"):
            return False
        try:
            parts = hashed_password.split("$")
            if len(parts) != 3:
                return False
            _, salt, expected_hex = parts
            key = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                100_000,
            )
            return hmac.compare_digest(key.hex(), expected_hex)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# JWT Token Generation & Verification Layer
# ---------------------------------------------------------------------------
try:
    import jwt
    from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

    def create_access_token(
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """Generate a signed JWT access token."""
        to_encode = data.copy()
        now = datetime.now(UTC)
        expire = now + (
            expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": int(expire.timestamp()), "type": "access"})
        return str(
            jwt.encode(
                to_encode,
                settings.JWT_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM,
            )
        )

    def create_refresh_token(
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """Generate a signed JWT refresh token."""
        to_encode = data.copy()
        now = datetime.now(UTC)
        expire = now + (
            expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
        return str(
            jwt.encode(
                to_encode,
                settings.JWT_SECRET_KEY,
                algorithm=settings.JWT_ALGORITHM,
            )
        )

    def decode_token(token: str) -> dict[str, Any]:
        """Decode and validate a signed JWT token."""
        return dict(
            jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
        )

except ImportError:
    # Pure Python RFC 7519 HS256 JWT implementation fallback
    class InvalidTokenError(Exception):
        """Invalid JWT Token."""

    class ExpiredSignatureError(InvalidTokenError):
        """Expired JWT Token."""

    def _base64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    def _base64url_decode(data_str: str) -> bytes:
        rem = len(data_str) % 4
        if rem > 0:
            data_str += "=" * (4 - rem)
        return base64.urlsafe_b64decode(data_str)

    def create_access_token(
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """Generate a signed HS256 JWT access token."""
        to_encode = data.copy()
        now = datetime.now(UTC)
        expire = now + (
            expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": int(expire.timestamp()), "type": "access"})

        header = {"alg": "HS256", "typ": "JWT"}
        encoded_header = _base64url_encode(
            json.dumps(header, separators=(",", ":")).encode("utf-8")
        )
        encoded_payload = _base64url_encode(
            json.dumps(to_encode, separators=(",", ":")).encode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_payload}"
        signature = hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        encoded_signature = _base64url_encode(signature)
        return f"{signing_input}.{encoded_signature}"

    def create_refresh_token(
        data: dict[str, Any],
        expires_delta: timedelta | None = None,
    ) -> str:
        """Generate a signed HS256 JWT refresh token."""
        to_encode = data.copy()
        now = datetime.now(UTC)
        expire = now + (
            expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})

        header = {"alg": "HS256", "typ": "JWT"}
        encoded_header = _base64url_encode(
            json.dumps(header, separators=(",", ":")).encode("utf-8")
        )
        encoded_payload = _base64url_encode(
            json.dumps(to_encode, separators=(",", ":")).encode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_payload}"
        signature = hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        encoded_signature = _base64url_encode(signature)
        return f"{signing_input}.{encoded_signature}"

    def decode_token(token: str) -> dict[str, Any]:
        """Decode and validate a signed HS256 JWT token."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise InvalidTokenError("Invalid token segments")
            encoded_header, encoded_payload, encoded_signature = parts
            signing_input = f"{encoded_header}.{encoded_payload}"
            expected_sig = hmac.new(
                settings.JWT_SECRET_KEY.encode("utf-8"),
                signing_input.encode("ascii"),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(
                _base64url_encode(expected_sig), encoded_signature
            ):
                raise InvalidTokenError("Signature verification failed")

            payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))
            now_ts = int(datetime.now(UTC).timestamp())
            exp = payload.get("exp")
            if exp is not None and now_ts > exp:
                raise ExpiredSignatureError("Token has expired")
            return dict(payload)
        except (ExpiredSignatureError, InvalidTokenError):
            raise
        except Exception as e:
            raise InvalidTokenError(f"Could not parse token: {e}") from e
