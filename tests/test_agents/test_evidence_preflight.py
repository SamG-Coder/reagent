import json

from re_agent.agents.loop import run_fix_loop
from re_agent.backend.stub import StubBackend
from re_agent.core.models import AnalysisArtifact, AsmResult, FunctionTarget
from tests.test_agents.test_loop import MockLLM


def test_cross_scope_exports_do_not_spend_model_calls():
    class Backend(StubBackend):
        def __init__(self):
            super().__init__()
            self._caps.has_pcode = True

        def get_asm(self, target):
            return AsmResult(target, '100 JMP 200', 1, 0, False)

        def get_pcode(self, target):
            return AnalysisArtifact('pcode', target, json.dumps({'data': [
                {'address': '200', 'opcode': 'RETURN'}]}))

    model = MockLLM(['should not be used'])
    result = run_fix_loop(FunctionTarget('100', '', 'f'), Backend(), model)
    assert model._idx == 0
    assert not result.success
    assert result.rounds_used == 0
    assert result.objective_verdict.evidence_conflict
    assert result.error.startswith('Blocked:')
