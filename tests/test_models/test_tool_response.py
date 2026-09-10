import pytest
from pydantic import BaseModel

from app.application.exceptions import TransactionNotFoundError
from app.infrastructure.agents._core.schemas.tool_response import (
    ToolFailure,
    ToolSuccess,
)


class _DummyData(BaseModel):
    value: int
    name: str = "default"


class TestToolSuccess:
    def test_ok_status(self):
        response = ToolSuccess(data=_DummyData(value=42))
        assert response.status == "ok"

    def test_typed_data(self):
        response = ToolSuccess(data=_DummyData(value=99, name="test"))
        assert response.data.value == 99
        assert response.data.name == "test"

    def test_default_status(self):
        response = ToolSuccess(data=_DummyData(value=1))
        assert response.status == "ok"

    def test_is_base_model(self):
        response = ToolSuccess(data=_DummyData(value=0))
        assert isinstance(response, BaseModel)


class TestToolFailure:
    def test_error_status(self):
        response = ToolFailure(error="fail")
        assert response.status == "error"

    def test_error_message(self):
        response = ToolFailure(error="Something went wrong")
        assert response.error == "Something went wrong"

    def test_default_details(self):
        response = ToolFailure(error="fail")
        assert response.details == {}

    def test_custom_details(self):
        response = ToolFailure(error="fail", details={"code": 500})
        assert response.details == {"code": 500}

    def test_exception_classmethod(self):
        exc = ValueError("invalid value")
        response = ToolFailure.exception(exc)
        assert response.status == "error"
        assert response.code == "unexpected_error"
        assert response.details == {}
        assert "invalid value" not in response.error

    def test_application_error_classmethod(self):
        response = ToolFailure.application_error(TransactionNotFoundError())
        assert response.code == "transaction_not_found"
        assert response.error == TransactionNotFoundError.public_message

    def test_exception_with_non_string_details(self):
        response = ToolFailure(error="err", details={"count": 3, "active": True})
        assert response.details == {"count": 3, "active": True}


class TestToolResponseDiscrimination:
    def test_success_is_not_failure(self):
        success = ToolSuccess(data=_DummyData(value=1))
        assert not isinstance(success, ToolFailure)

    def test_failure_is_not_success(self):
        failure = ToolFailure(error="err")
        assert not isinstance(failure, ToolSuccess)

    def test_success_and_failure_are_distinct(self):
        success = ToolSuccess(data=_DummyData(value=1))
        failure = ToolFailure(error="err")

        ok_results = [
            isinstance(success, ToolSuccess),
            not isinstance(failure, ToolSuccess),
        ]
        assert all(ok_results)

    def test_union_discrimination_via_isinstance(self):
        results: list[ToolSuccess[_DummyData] | ToolFailure] = [
            ToolSuccess(data=_DummyData(value=10)),
            ToolFailure(error="err"),
        ]

        assert isinstance(results[0], ToolSuccess)
        assert isinstance(results[1], ToolFailure)

    def test_pattern_matching_success(self):
        response: ToolSuccess[_DummyData] | ToolFailure = ToolSuccess(
            data=_DummyData(value=7)
        )
        match response:
            case ToolSuccess(data=data):
                assert data.value == 7
            case _:
                pytest.fail("Expected ToolSuccess")

    def test_pattern_matching_failure(self):
        response: ToolSuccess[_DummyData] | ToolFailure = ToolFailure(
            error="fail", details={"reason": "timeout"}
        )
        match response:
            case ToolFailure(error=err, details=det):
                assert err == "fail"
                assert det == {"reason": "timeout"}
            case _:
                pytest.fail("Expected ToolFailure")
