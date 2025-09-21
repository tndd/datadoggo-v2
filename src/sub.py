def sub_fn(s: str):
    return s + 'world'


# Imports for testing (only used when running tests)
from hypothesis import given
from hypothesis.strategies import text as st_text

# test
@given(st_text())
def test_sub_fn(s: str):
    # 後ろにworldが追加されるか (Verify that 'world' is always appended to the input string)
    result = sub_fn(s)
    assert result == s + 'world', f"Expected '{s + 'world'}' but got '{result}'"
