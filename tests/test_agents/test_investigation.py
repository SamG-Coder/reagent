"""Tests for model-requested read-only RE investigations."""
from __future__ import annotations

import pytest

from re_agent.agents.reverser import ReverserAgent
from re_agent.backend.stub import StubBackend
from re_agent.core.models import AsmResult, FunctionTarget
from re_agent.llm.protocol import Message


class _ActionLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.last_messages: list[Message] = []

    def send(self, messages: list[Message], **kwargs: object) -> str:
        self.calls += 1
        self.last_messages = list(messages)
        if self.calls == 1:
            return '{"actions":[{"tool":"decompile","target":"0x200"}]}'
        return "```cpp\nvoid CTest::Foo() { ResolvedCall(); }\n```"

    @property
    def supports_conversations(self) -> bool:
        return False

    def new_conversation(self, system: str) -> str:
        return ""

    def resume(self, conversation_id: str, message: str) -> str:
        return ""


def test_reverser_executes_bounded_read_only_action() -> None:
    llm = _ActionLLM()
    reverser = ReverserAgent(
        llm,
        StubBackend(),
        investigation_enabled=True,
        max_investigations=2,
    )
    code, _ = reverser.reverse(FunctionTarget("0x100", "CTest", "Foo"))
    assert llm.calls == 2
    assert "ResolvedCall" in code
    assert "TOOL decompile(0x200)" in llm.last_messages[-1].content


@pytest.mark.parametrize(("enabled", "budget"), [(False, 8), (True, 0)])
def test_unavailable_investigations_are_not_advertised(enabled, budget):
    llm = _ActionLLM()
    with pytest.raises((ValueError, RuntimeError)):
        ReverserAgent(llm, StubBackend(), investigation_enabled=enabled,
                      max_investigations=budget).reverse(FunctionTarget("100", "", "f"))
    system = llm.last_messages[0].content
    assert '"actions"' not in system
    assert "Additional investigation tools are unavailable" in system
    assert llm.calls == 1


def test_disabled_actions_still_receive_prefetched_assembly():
    class AssemblyBackend(StubBackend):
        def get_asm(self, target):
            return AsmResult(target, '100 MOV EAX,7\n105 RET', 2, 0, False)

    llm = _ActionLLM()
    llm.calls = 1  # Return the fixture's code response, not an action request.
    reverser = ReverserAgent(llm, AssemblyBackend(), investigation_enabled=False)
    reverser.reverse(FunctionTarget('100', '', 'f'))
    assert 'MOV EAX,7' in reverser.last_prompt
    assert '"actions"' not in llm.last_messages[0].content
