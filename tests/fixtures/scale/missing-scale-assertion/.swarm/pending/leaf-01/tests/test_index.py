# spec: specs/x.md::Acceptance criteria::AC-1
from src.index import build_index


def test_build_index_is_fast_enough():
    assert len(build_index(list(range(4000)))) < 5000
