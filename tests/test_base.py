from hgrep.harness.base import MAX_CONTENT_CHARS, Adapter


def test_max_content_chars_is_bounded():
    assert MAX_CONTENT_CHARS == 200_000


def test_adapter_protocol_is_runtime_checkable():
    class Dummy:
        name = "dummy"

        def is_available(self):
            return True

        def iter_sessions(self):
            return iter([])

        def parse(self, path):
            return None

        def resume_command(self, record):
            return ""

    assert isinstance(Dummy(), Adapter)
