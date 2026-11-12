"""OpenAPI metadata and operation documentation for the public HTTP API."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute

API_DESCRIPTION = """\
Asynchronous REST API for court inventory, availability, bookings, pricing, and
operational reports. The API is versioned under `/api/v1`. Public endpoints
include availability search, pricing calculation, and health checks. Protected
operations use JWT Bearer authentication and member, staff, or administrator
roles. Domain rules are enforced by services; repositories perform persistence
and aggregation with SQLAlchemy and PostgreSQL.

Use the production deployment guide in the repository README to configure the
database, signing secret, migrations, and container stack.
"""

API_TAGS = [
    {"name": "Health", "description": "Application and database health probes."},
    {
        "name": "Authentication",
        "description": "Member registration, login, token refresh, and profile.",
    },
    {
        "name": "Availability",
        "description": "Public searches for bookable court time slots.",
    },
    {
        "name": "Court Management",
        "description": "Venue, court, and recurring availability administration.",
    },
    {
        "name": "Bookings",
        "description": (
            "Booking holds, confirmation, cancellation, and recurring requests."
        ),
    },
    {
        "name": "Booking Policy",
        "description": "Staff-managed global booking limits and duration rules.",
    },
    {"name": "Pricing", "description": "Price quotes and staff-managed pricing rules."},
    {"name": "Reports", "description": "Staff-only utilization and booking reports."},
]

CONTACT = {
    "name": "Court Booking Service maintainers",
    "url": "https://github.com/shaibanfarazkhan/court-booking-service",
}
LICENSE = {"name": "Not specified"}
SERVERS = [
    {"url": "/", "description": "Current deployment"},
    {"url": "http://localhost:8000", "description": "Local development"},
]

ENDPOINT_DESCRIPTIONS = {
    "health_check": (
        "Return a lightweight liveness response without contacting the database."
    ),
    "database_health_check": (
        "Check database connectivity and report healthy or degraded status."
    ),
    "liveness_health_check": (
        "Return the container liveness response without authentication."
    ),
    "create_venue": "Create a venue. Requires the ADMIN role.",
    "list_venues": "List venues with offset pagination. Requires authentication.",
    "get_venue": "Retrieve one venue by its UUID. Requires authentication.",
    "update_venue": "Update venue fields. Requires the ADMIN role.",
    "delete_venue": "Delete a venue. Requires the ADMIN role.",
    "create_court": "Create a court at an existing venue. Requires the ADMIN role.",
    "list_courts": (
        "List courts with optional venue filtering. Requires authentication."
    ),
    "get_court": "Retrieve one court by its UUID. Requires authentication.",
    "update_court": "Update court details. Requires the ADMIN role.",
    "delete_court": "Delete a court. Requires the ADMIN role.",
    "create_availability": (
        "Add a weekly availability window for a court. Requires the ADMIN role."
    ),
    "list_availability": (
        "List recurring availability windows with optional filters. "
        "Requires authentication."
    ),
    "get_availability": (
        "Retrieve one recurring availability window. Requires authentication."
    ),
    "update_availability": (
        "Update a recurring availability window. Requires the ADMIN role."
    ),
    "delete_availability": (
        "Delete a recurring availability window. Requires the ADMIN role."
    ),
}

REQUEST_EXAMPLES: dict[tuple[str, str], dict[str, Any]] = {
    ("POST", "/api/v1/auth/register"): {
        "summary": "Register a member",
        "value": {
            "email": "member@example.com",
            "password": "CourtPlay123",
            "full_name": "Court Member",
            "phone_number": "+15550102030",
        },
    },
    ("POST", "/api/v1/auth/login"): {
        "summary": "Authenticate a member",
        "value": {"email": "member@example.com", "password": "CourtPlay123"},
    },
    ("POST", "/api/v1/auth/refresh"): {
        "summary": "Refresh a token pair",
        "value": {"refresh_token": "<signed-refresh-token>"},
    },
    ("POST", "/api/v1/bookings/holds"): {
        "summary": "Hold an available slot",
        "value": {"time_slot_id": "00000000-0000-4000-8000-000000000001"},
    },
    ("POST", "/api/v1/bookings/recurring"): {
        "summary": "Request weekly bookings",
        "value": {
            "court_id": "00000000-0000-4000-8000-000000000002",
            "start_date": "2026-12-01",
            "end_date": "2026-12-15",
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "recurrence_type": "WEEKLY",
            "timezone": "Asia/Kolkata",
            "idempotency_key": "member-series-20261201",
        },
    },
    ("PUT", "/api/v1/booking-policy"): {
        "summary": "Set global booking limits",
        "value": {
            "daily_limit": 3,
            "weekly_limit": 8,
            "future_booking_limit": 10,
            "min_duration_minutes": 30,
            "max_duration_minutes": 180,
        },
    },
    ("POST", "/api/v1/pricing/rules"): {
        "summary": "Create a weekend surcharge",
        "value": {
            "name": "Weekend court rate",
            "rule_type": "WEEKEND",
            "effect": "SURCHARGE",
            "value_type": "PERCENTAGE",
            "value": "15.00",
            "active": True,
            "weekdays": [5, 6],
        },
    },
    ("POST", "/api/v1/venues"): {
        "summary": "Create a venue",
        "value": {
            "name": "Central Sports Club",
            "address": "100 Court Lane",
            "city": "Hyderabad",
            "state": "Telangana",
            "country": "India",
            "timezone": "Asia/Kolkata",
            "postal_code": "500001",
            "slug": "central-sports-club",
            "opening_time": "06:00:00",
            "closing_time": "22:00:00",
        },
    },
    ("PATCH", "/api/v1/venues/{venue_id}"): {
        "summary": "Update venue details",
        "value": {"description": "Updated club facilities"},
    },
    ("POST", "/api/v1/courts"): {
        "summary": "Create a tennis court",
        "value": {
            "venue_id": "00000000-0000-4000-8000-000000000003",
            "name": "Court 1",
            "sport_type": "Tennis",
            "surface_type": "HARD",
            "indoor": False,
            "base_price_per_hour": "750.00",
        },
    },
    ("PATCH", "/api/v1/courts/{court_id}"): {
        "summary": "Update court details",
        "value": {"base_price_per_hour": "800.00", "active": True},
    },
    ("PUT", "/api/v1/pricing/rules/{rule_id}"): {
        "summary": "Replace a pricing rule",
        "value": {
            "name": "Weekend court rate",
            "rule_type": "WEEKEND",
            "effect": "SURCHARGE",
            "value_type": "PERCENTAGE",
            "value": "15.00",
            "active": True,
            "weekdays": [5, 6],
        },
    },
    ("POST", "/api/v1/availability"): {
        "summary": "Create a weekly availability window",
        "value": {
            "court_id": "00000000-0000-4000-8000-000000000003",
            "weekday": 5,
            "start_time": "08:00:00",
            "end_time": "20:00:00",
            "available": True,
        },
    },
    ("PATCH", "/api/v1/availability/{availability_id}"): {
        "summary": "Update weekly availability",
        "value": {"start_time": "09:00:00", "end_time": "10:00:00"},
    },
}

HTTP_ERROR_DESCRIPTIONS = {
    "401": "Authentication is required or the supplied credentials are invalid.",
    "403": "The authenticated user does not have permission for this operation.",
    "404": "The requested resource was not found.",
    "409": "The request conflicts with the current booking or resource state.",
    "410": "The booking hold has expired.",
    "422": "Request validation failed or a supplied value violates domain rules.",
    "503": "The database service is unavailable.",
}

ENDPOINT_ERROR_CODES = {
    "register": ("409", "422"),
    "login": ("401", "403", "422"),
    "refresh_tokens": ("401", "403", "422"),
    "get_me": ("401",),
    "search_availability": ("422",),
    "get_court_availability": ("422",),
    "create_venue": ("401", "403", "409", "422"),
    "list_venues": ("401", "422"),
    "get_venue": ("401", "404"),
    "update_venue": ("401", "403", "404", "409", "422"),
    "delete_venue": ("401", "403", "404"),
    "create_court": ("401", "403", "404", "409", "422"),
    "list_courts": ("401", "422"),
    "get_court": ("401", "404"),
    "update_court": ("401", "403", "404", "409", "422"),
    "delete_court": ("401", "403", "404"),
    "create_availability": ("401", "403", "404", "409", "422"),
    "list_availability": ("401", "422"),
    "get_availability": ("401", "404"),
    "update_availability": ("401", "403", "404", "409", "422"),
    "delete_availability": ("401", "403", "404"),
    "create_hold": ("401", "403", "404", "409", "422"),
    "confirm_booking": ("401", "403", "404", "409", "410", "422"),
    "create_recurring_bookings": ("401", "403", "404", "409", "422"),
    "cancel_booking": ("401", "403", "404", "409"),
    "list_user_bookings": ("401", "403", "422"),
    "get_booking_policy": ("401", "403", "404"),
    "update_booking_policy": ("401", "403", "422"),
    "calculate_price": ("404", "422"),
    "create_pricing_rule": ("401", "403", "404", "409", "422"),
    "update_pricing_rule": ("401", "403", "404", "409", "422"),
    "delete_pricing_rule": ("401", "403", "404"),
    "list_pricing_rules": ("401", "403", "422"),
    "weekly_utilization_report": ("401", "403", "422"),
    "database_health_check": ("503",),
}


def _error_response(description: str) -> dict[str, Any]:
    """Return the shared error response schema used in documented operations."""
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                    "required": ["detail"],
                }
            }
        },
    }


def build_openapi_schema(application: FastAPI) -> dict[str, Any]:
    """Build a complete OpenAPI document with operation summaries and errors."""
    schema = get_openapi(
        title="Court Booking Service API",
        version="0.1.0",
        description=API_DESCRIPTION,
        routes=application.routes,
        contact=CONTACT,
        license_info=LICENSE,
        servers=SERVERS,
        tags=API_TAGS,
    )

    for route in application.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or ():
            operation = schema.get("paths", {}).get(route.path, {}).get(method.lower())
            if operation is None:
                continue
            summary = route.summary or route.name.replace("_", " ").capitalize()
            description = (
                ENDPOINT_DESCRIPTIONS.get(route.name)
                or route.description
                or f"{summary}. See the request schema and response codes below."
            )
            operation["summary"] = summary
            operation["description"] = description
            operation["tags"] = route.tags or ["General"]

            responses = operation.setdefault("responses", {})
            for code in ENDPOINT_ERROR_CODES.get(route.name, ()):
                responses.setdefault(
                    code, _error_response(HTTP_ERROR_DESCRIPTIONS[code])
                )
            for code, response in responses.items():
                if code == "204":
                    response["description"] = "The resource was deleted successfully."
                elif code == "201":
                    response["description"] = "The resource was created successfully."
                elif code in {"200", "202"}:
                    response["description"] = "The request completed successfully."
                elif code in HTTP_ERROR_DESCRIPTIONS:
                    response["description"] = HTTP_ERROR_DESCRIPTIONS[code]

            example = REQUEST_EXAMPLES.get((method, route.path))
            if example and "requestBody" in operation:
                media = (
                    operation["requestBody"]
                    .setdefault("content", {})
                    .get("application/json")
                )
                if media is not None:
                    media["examples"] = {"example": example}

    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method in {"get", "post", "put", "patch", "delete", "options", "head"}:
                operation.setdefault(
                    "description",
                    f"{operation.get('summary', 'API operation')}. "
                    "See the request schema and response codes below.",
                )

    application.openapi_schema = schema
    return schema
