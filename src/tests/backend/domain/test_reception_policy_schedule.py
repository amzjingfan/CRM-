"""策略有效期在接口边界只接受完整的站点本地配置。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.reception.schemas import PolicyCreate, PolicySchedule


def test_policy_schedule_requires_complete_site_local_date_and_time_ranges() -> None:
    base = {"kind": "welcome", "name": "Welcome", "content": "Hello", "store_ids": [uuid.uuid4()]}
    assert PolicyCreate.model_validate(base | {"schedule": {"mode": "long_term"}}).schedule.mode == "long_term"
    valid = {
        "mode": "fixed_hours",
        "start_date": "2026-10-23",
        "end_date": "2026-10-25",
        "daily_start_time": "09:00",
        "daily_end_time": "18:00",
    }
    assert PolicyCreate.model_validate(base | {"schedule": valid}).schedule == PolicySchedule.model_validate(valid)
    for invalid in (
        {"mode": "date_range", "start_date": "2026-10-25", "end_date": "2026-10-23"},
        {
            "mode": "fixed_hours",
            "start_date": "2026-10-23",
            "end_date": "2026-10-25",
            "daily_start_time": "18:00",
            "daily_end_time": "09:00",
        },
        {"mode": "long_term", "start_date": "2026-10-23"},
        {
            "mode": "fixed_hours",
            "start_date": "2026-10-23",
            "end_date": "2026-10-25",
            "daily_start_time": "09:00+02:00",
            "daily_end_time": "18:00+02:00",
        },
    ):
        with pytest.raises(ValidationError):
            PolicyCreate.model_validate(base | {"schedule": invalid})


def test_policy_list_route_allows_all_permitted_stores() -> None:
    operation = TestClient(app).get("/openapi.json").json()["paths"]["/v1/marketing/reception/policies"]["get"]
    required = {item["name"]: item["required"] for item in operation["parameters"]}
    assert required["kind"] is True
    assert required["store_id"] is False
