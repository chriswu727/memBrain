import os

# ONNX Runtime 1.29 and later (the PyPI wheels for Linux and macOS) report each process that loads it to Microsoft
# and keep a device identifier under the user's cache directory, unless this is set before it loads. memBrain
# contacts no one, so it is set here, before any entry point (service, hooks, tool server, CLI) can load it, and
# every process memBrain starts inherits it.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"

__version__ = "0.1.0"
