from .helpers import DomainError


def require_recording(brain, expected_revision=None):
    if brain["recording_paused"]:
        raise DomainError("recording_paused", "Recording is paused for this brain.")
    if expected_revision is not None and expected_revision != brain["recording_revision"]:
        raise DomainError("recording_stale", "Recording policy changed after this input was captured.")
