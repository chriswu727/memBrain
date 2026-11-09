"""Host pipes use UTF-8 independently of the Windows console's active encoding."""
import json
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("kind", ["hook", "tool"])
@pytest.mark.parametrize("encoding", ["ascii", "gbk"])
def test_plugin_json_pipe_preserves_unicode(tmp_path, kind, encoding):
    code = """
import io
import sys
from pathlib import Path
from membrain import plugin
text = 'Chinese \\u4f60\\u597d and emoji \\U0001f327'
directory = Path(sys.argv[1])
if sys.argv[2] == 'hook':
    plugin.HANDLERS['session-start'] = ('SessionStart', lambda *args: text)
    plugin.run_hook('session-start', directory, io.BytesIO(b'{}'))
else:
    plugin.host_recording.pause = lambda *args, **kwargs: {'context': text}
    plugin.run_tool('pause', directory, io.BytesIO(b'{}'))
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), kind],
                            env={**os.environ, "PYTHONIOENCODING": encoding},
                            capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout.decode("utf-8"))
    text = value["context"] if kind == "tool" else value["hookSpecificOutput"]["additionalContext"]
    assert text == "Chinese 你好 and emoji 🌧"
