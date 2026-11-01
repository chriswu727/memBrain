"""Reasoning-effort levels shared by configuration and the chat provider, without importing either."""
from __future__ import annotations

from typing import Literal, get_args

ReasoningEffort = Literal["minimal", "low", "medium", "high", "xhigh", "max", "ultra"]


def _validate_reasoning_effort(value, thinking):
    if value is None:
        return
    if not isinstance(value, str) or value not in get_args(ReasoningEffort):
        raise ValueError("reasoning_effort must be None or a supported effort level")
    if thinking == "disabled":
        raise ValueError("reasoning_effort cannot be set when thinking is disabled")
