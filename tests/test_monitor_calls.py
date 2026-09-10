"""Ordinary model requests appear while running and retain their terminal status."""
import json

import pytest

from re_agent.llm.observed import CallBudget, ObservedProvider
from re_agent.llm.protocol import Message
from re_agent.monitor.server import Monitor
from re_agent.utils.storage import atomic_json


@pytest.mark.parametrize('failure', [False, True])
def test_monitor_sees_inflight_call_and_completion(tmp_path, failure):
    logs = tmp_path / 'logs'
    logs.mkdir()
    monitor = Monitor(tmp_path, tmp_path/'state', [], call_glob='logs/call-*.json')

    class Provider:
        def send(self, messages, **kwargs):
            agent = monitor.snapshot()['agents'][0]
            assert agent['status'] == 'running'
            assert '100' in agent['label'] and 'checker' in agent['label']
            assert 'private prompt' not in json.dumps(agent)
            assert 'elapsed' in agent['log']
            if failure:
                raise RuntimeError('request timed out')
            return 'completed response'

    provider = ObservedProvider(Provider(), CallBudget(1), 'checker', logs, target='100')
    if failure:
        with pytest.raises(RuntimeError, match='timed out'):
            provider.send([Message('user', 'private prompt')])
    else:
        assert provider.send([Message('user', 'private prompt')]) == 'completed response'
    agent = monitor.snapshot()['agents'][0]
    assert agent['status'] == ('failed' if failure else 'completed')
    assert ('request timed out' in agent['log']) if failure else agent['text'] == 'completed response'


def test_call_monitor_bounds_history_and_tolerates_broken_files(tmp_path):
    for i in range(140):
        atomic_json(tmp_path/f'call-{i:04}.json', dict(role='reverser',response='x'*70000,call=i))
    monitor = Monitor(tmp_path, tmp_path/'state', [], call_glob='call-*.json')
    agents = monitor.snapshot()['agents']
    assert len(agents) == 128
    assert all(len(agent['text']) == 65536 for agent in agents)
    (tmp_path/'call-broken.json').write_text('{')
    assert len(monitor.snapshot()['agents']) <= 128
    with pytest.raises(ValueError, match='relative'):
        Monitor(tmp_path, tmp_path/'state', [], call_glob='../call-*.json')
