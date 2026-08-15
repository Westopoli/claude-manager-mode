# spec: specs/x.md::Acceptance criteria::AC-1
from src.index import build_index


def _ops(n):
    return len(build_index(list(range(n))))


def test_build_index_is_linear_ish():
    assert _ops(4000) / _ops(2000) < 3.0
