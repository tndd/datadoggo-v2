def sub_fn(s: str):
    return s + 'world'


# Imports for testing (only used when running tests)
def test_sub_fn():
    # 後ろにworldが追加されるか (Verify that 'world' is always appended to the input string)
    result = sub_fn('hello ')
    assert result == 'hello world'
