"""Interrupted model review must not discard locally validated drafts."""
from dataclasses import replace

import pytest

from re_agent.backend.stub import StubBackend
from re_agent.config.schema import ReAgentConfig
from re_agent.core.models import FunctionTarget, ParityStatus, ValidationVerdict, Verdict
from re_agent.core.session import Session
from re_agent.orchestrator.single import reverse_single
from tests.test_agents.test_loop import MockLLM


@pytest.mark.parametrize("error", [RuntimeError("Model request timed out"), OSError("Connection lost")])
def test_interrupted_review_preserves_validated_draft(tmp_path, monkeypatch, error):
    config = ReAgentConfig()
    config.project_profile.source_root = str(tmp_path / "src")
    (tmp_path / "src").mkdir()
    config.output.report_dir = str(tmp_path / "reports")
    config.output.log_dir = str(tmp_path / "logs")
    code = "int f() { return 7; }"
    calls = []
    validation = ValidationVerdict(verdict=Verdict.PASS, summary="Build and tests passed",
                                  checks=[{"kind": "test", "verdict": "PASS", "detail": "42 cases"}])

    def preflight(result, *args):
        calls.append(result.code)
        return replace(result, validation_verdict=validation, parity_status=ParityStatus.GREEN)

    class InterruptedChecker(MockLLM):
        def send(self, messages, **kwargs):
            raise error

    monkeypatch.setattr("re_agent.orchestrator.single.validate_result", preflight)
    session = Session(tmp_path / "session.json")
    result = reverse_single(FunctionTarget("100", "", "f"), config, StubBackend(),
                            MockLLM([f"```cpp\n{code}\n```"]), session=session,
                            checker_llm=InterruptedChecker([]))
    assert not result.success
    assert result.code == code
    assert result.error == str(error)
    assert result.rounds_used == 1
    assert result.run_id
    assert result.validation_verdict == validation
    assert result.checker_verdict.verdict == Verdict.UNKNOWN
    assert calls == [code]  # No repeated validation or automatic model retry.
    assert next((tmp_path / "reports/code").glob("*.cpp")).read_text() == code
    saved = Session(tmp_path / "session.json").get_all_functions()[0]
    assert saved["success"] is False
    assert saved["code"] == code
    assert saved["validation_verdict"] == "PASS"
