import main


def test_trace_endpoints_expose_response_models_in_openapi():
    app = main.create_app()

    schema = app.openapi()

    list_schema = (
        schema["paths"]["/research/{research_id}/traces"]
        ["get"]["responses"]["200"]["content"]
        ["application/json"]["schema"]
    )

    detail_schema = (
        schema["paths"]["/research/{research_id}/traces/{trace_id}"]
        ["get"]["responses"]["200"]["content"]
        ["application/json"]["schema"]
    )

    events_schema = (
        schema["paths"]["/research/{research_id}/traces/{trace_id}/events"]
        ["get"]["responses"]["200"]["content"]
        ["application/json"]["schema"]
    )

    assert list_schema["$ref"].endswith("/TraceListResponse")
    assert detail_schema["$ref"].endswith("/TraceDetailResponse")
    assert events_schema["$ref"].endswith("/TraceEventsResponse")


def test_trace_openapi_models_expose_trace_and_event_identity_fields():
    app = main.create_app()

    schema = app.openapi()
    models = schema["components"]["schemas"]

    trace_properties = models["ExecutionTraceResponse"]["properties"]
    event_properties = models["ExecutionEventResponse"]["properties"]

    assert "trace_id" in trace_properties
    assert "task_id" in trace_properties
    assert "status" in trace_properties

    assert "event_id" in event_properties
    assert "trace_id" in event_properties
    assert "task_id" in event_properties
    assert "schema_version" in event_properties
