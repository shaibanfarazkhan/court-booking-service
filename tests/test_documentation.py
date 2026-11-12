"""Regression checks for public OpenAPI metadata and operation documentation."""

from app.main import app


def test_openapi_has_project_metadata_and_tags() -> None:
    schema = app.openapi()

    assert schema["info"]["title"] == "Court Booking Service API"
    assert schema["info"]["version"] == "0.1.0"
    assert schema["info"]["description"]
    assert schema["info"]["contact"]["url"].startswith("https://")
    assert schema["info"]["license"]["name"]
    assert schema["servers"]
    assert {tag["name"] for tag in schema["tags"]} >= {
        "Health",
        "Authentication",
        "Bookings",
        "Pricing",
        "Reports",
    }


def test_every_operation_has_summary_description_tags_and_response_descriptions() -> (
    None
):
    schema = app.openapi()

    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
            }:
                continue
            assert operation["summary"]
            assert operation.get("description"), operation.get("operationId")
            assert operation["tags"]
            assert operation["responses"]
            assert all(
                response.get("description")
                for response in operation["responses"].values()
            )


def test_every_json_request_body_has_an_example() -> None:
    schema = app.openapi()

    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
            }:
                continue
            request_body = operation.get("requestBody")
            if request_body:
                json_content = request_body["content"].get("application/json")
                assert json_content
                has_inline_example = bool(
                    json_content.get("examples") or json_content.get("example")
                )
                schema_ref = json_content.get("schema", {}).get("$ref", "")
                model_name = schema_ref.rsplit("/", maxsplit=1)[-1]
                model_schema = schema["components"]["schemas"].get(model_name, {})
                assert has_inline_example or model_schema.get("examples")
