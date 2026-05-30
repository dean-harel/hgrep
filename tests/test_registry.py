from hgrep.registry import default_adapters


def test_default_adapters_are_claude_and_pi():
    names = [a.name for a in default_adapters()]
    assert names == ["claude-code", "pi"]
