import sys

import pytest

from re_agent.backend.stub import StubBackend
from re_agent.config.schema import ReAgentConfig
from re_agent.core.models import FunctionTarget, Verdict
from re_agent.core.session import Session
from re_agent.monitor.server import Monitor
from re_agent.orchestrator.single import reverse_single
from tests.test_agents.test_loop import MockLLM


@pytest.mark.parametrize(('exit_code', 'configured', 'expected'), [
    (77, 77, 'unvalidated'), (1, 77, 'failed'), (77, None, 'failed')])
def test_missing_coverage_is_unaccepted_without_repair_loop(tmp_path, exit_code, configured, expected):
    config = ReAgentConfig()
    (tmp_path/'src').mkdir()
    config.project_profile.source_root = str(tmp_path/'src')
    config.output.report_dir = str(tmp_path/'reports')
    config.output.log_dir = str(tmp_path/'logs')
    # A short body can produce an advisory YELLOW finding. It must not turn
    # unavailable tests into a failed review or trigger pointless regeneration.
    config.parity.enabled = True
    config.validation.test_commands = [[sys.executable, '-c', f'import sys; sys.exit({exit_code})', '{candidate_file}']]
    config.validation.require_tests = True
    config.validation.trust_configured_commands = True
    config.validation.unavailable_exit_code = configured
    config.orchestrator.max_review_rounds = 2
    model = MockLLM(['```cpp\nint f() { return 7; }\n```'])
    checker = MockLLM(['{"verdict":"PASS","summary":"Matches evidence"}'])
    session = Session(tmp_path/'session.json')
    result = reverse_single(FunctionTarget('100', '', 'f'), config, StubBackend(), model,
                            session=session, checker_llm=checker)
    assert result.outcome == expected
    assert not result.success
    if expected == 'unvalidated':
        assert result.validation_verdict.verdict == Verdict.UNKNOWN
        assert model._idx == checker._idx == 1
    snapshot = Monitor(tmp_path, tmp_path/'state', ['session.json']).snapshot()
    assert snapshot['passed'] == 0
    assert snapshot['unvalidated'] == (expected == 'unvalidated')
    assert snapshot['failed'] == (expected == 'failed')
    assert session.get_summary()['failed'] == (expected == 'failed')
    assert session.get_class_summary('')['unvalidated'] == (expected == 'unvalidated')
