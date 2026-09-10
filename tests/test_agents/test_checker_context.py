"""Reviewer receives the same compilation contract as the reverser."""
from re_agent.agents.loop import run_fix_loop
from re_agent.backend.stub import StubBackend
from re_agent.config.schema import ProjectProfile
from re_agent.core.models import FunctionTarget
from tests.test_agents.test_loop import MockLLM


def test_checker_receives_profile_without_overriding_failed_review():
    class RecordingChecker(MockLLM):
        def send(self, messages, **kwargs):
            self.messages = messages
            return super().send(messages, **kwargs)

    checker = RecordingChecker(['{"verdict":"FAIL","summary":"Incorrect arithmetic"}'])
    profile = ProjectProfile(language_standard="C++20", prompt_rules=[
        "The compiler preincludes struct Point { int x; int y; };",
        'The entry point uses extern "C" linkage.',
    ])
    result = run_fix_loop(FunctionTarget("100", "", "f"), StubBackend(),
                          MockLLM(['```cpp\nint f() { return 7; }\n```']), checker,
                          max_rounds=1, project_profile=profile)
    prompt = checker.messages[-1].content
    assert "C++20" in prompt
    assert all(rule in prompt for rule in profile.prompt_rules)
    assert "binary evidence independently" in prompt
    assert not result.success
