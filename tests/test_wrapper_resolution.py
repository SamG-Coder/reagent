import pytest

from re_agent.backend.exports import GhidraExportsBackend
from re_agent.core.target_plan import build_plan
from re_agent.utils.address import normalize_address
from re_agent.utils.storage import atomic_json


def packet(root, address, assembly):
    address = normalize_address(address)
    atomic_json(root/f'{address}.json', {'address':address,'name':'f_'+address,
        'decompiled':'int f() { return 1; }','assembly':assembly,'is_thunk':False})


def test_plan_resolves_and_deduplicates_unflagged_wrappers(tmp_path):
    packet(tmp_path,'100',['100 JMP 0x200'])
    packet(tmp_path,'200',['200 JMP 0x300'])
    packet(tmp_path,'300',['300 MOV EAX,1','305 RET'])
    backend = GhidraExportsBackend(str(tmp_path))
    plan = build_plan(backend,['100','200','300'],'a'*64,max_depth=0)
    assert [f.address for f in plan.functions] == ['00000300']


@pytest.mark.parametrize('assembly', [
    ['100 JMP RAX'], ['100 MOV EAX,1','105 JMP 0x200'], ['100 JMP 0x999']])
def test_does_not_guess_indirect_or_missing_destinations(tmp_path, assembly):
    packet(tmp_path,'100',assembly)
    packet(tmp_path,'200',['200 RET'])
    assert GhidraExportsBackend(str(tmp_path)).resolve_function('100') == '00000100'


def test_cycles_fail_without_spending_a_model_call(tmp_path):
    packet(tmp_path,'100',['100 JMP 0x200'])
    packet(tmp_path,'200',['200 JMP 0x100'])
    with pytest.raises(ValueError, match='Cyclic'):
        build_plan(GhidraExportsBackend(str(tmp_path)),['100'],'a'*64)


def test_missing_seed_is_preserved_as_an_evidence_gap(tmp_path):
    plan = build_plan(GhidraExportsBackend(str(tmp_path)), ['100'], 'a'*64)
    assert [f.address for f in plan.functions] == ['00000100']
    assert plan.gaps
