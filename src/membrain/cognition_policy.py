"""Limits for one background cognition job: sources, proposals, model calls, bytes and time.

Kept apart from ``semantic.py`` so that settings can validate these limits without loading the semantic pipeline.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticPolicy:
    max_sources: int = 32
    max_assertions: int = 32
    max_episodes: int = 16
    max_proposals: int = 24
    max_model_calls: int = 2
    max_input_bytes: int = 196608
    max_request_bytes: int = 98304
    max_response_bytes: int = 32768
    max_output_tokens: int = 8192
    max_wall_time_ms: int = 30000

    def __post_init__(self):
        caps = {"max_sources": 128, "max_assertions": 128, "max_episodes": 64,
                "max_proposals": 72, "max_model_calls": 8, "max_input_bytes": 1048576,
                "max_request_bytes": 524288, "max_response_bytes": 65536,
                "max_output_tokens": 32768, "max_wall_time_ms": 600000}
        for key, cap in caps.items():
            value = getattr(self, key)
            if type(value) is not int or not (0 if key == "max_model_calls" else 1) <= value <= cap:
                raise ValueError(f"Invalid {key}")
