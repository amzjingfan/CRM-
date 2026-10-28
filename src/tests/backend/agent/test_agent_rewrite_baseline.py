"""重写阶段的默认关闭门禁；旧运行路径保持可用直至切流。"""

import pytest

from app.shared.config.settings import Settings


def test_new_agent_executor_switches_default_off_and_are_independent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_V2_DEBUG_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_V2_FORMAL_ENABLED", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.agent_v2_debug_enabled is False
    assert defaults.agent_v2_formal_enabled is False

    monkeypatch.setenv("AGENT_V2_DEBUG_ENABLED", "true")
    debug_only = Settings(_env_file=None)
    assert debug_only.agent_v2_debug_enabled is True
    assert debug_only.agent_v2_formal_enabled is False
