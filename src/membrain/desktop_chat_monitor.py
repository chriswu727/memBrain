import sys


def _notice(message):
    try:
        print(message, file=sys.stderr)
    except (OSError, UnicodeError, ValueError):
        pass
