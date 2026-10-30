"""选择接口的严格写入边界。"""

import pytest
from pydantic import ValidationError


def test_detach_requires_exact_positive_integer_and_no_extra_body():
    from app.agents.management.templates.selection_schemas import DetachTemplateRequest

    assert DetachTemplateRequest(expected_revision=1).expected_revision == 1
    for payload in (
        {},
        {"expected_revision": True},
        {"expected_revision": "1"},
        {"expected_revision": 0},
        {"expected_revision": 1, "publish": True},
    ):
        with pytest.raises(ValidationError):
            DetachTemplateRequest.model_validate(payload)
