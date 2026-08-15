# spec: specs/x.md::Acceptance criteria::AC-1
from src.index import build_index


def test_dedupes():
    assert build_index([1, 1, 2]) == [1, 2]
