"""Per-message recording receipts for host turn completion.

A receipt says what this call observed, when it returns, about keeping each message of one exchange in memory.
``recorded`` means the service's observation receipt confirmed it. ``queued`` means admission to the durable local
journal was confirmed but server storage is unconfirmed: a request whose answer was lost may already be committed,
and another replay worker may drain the journal before the callback returns. It is not a live queue-membership
query. ``excluded`` names the policy that kept it out and that policy's scope. ``failed`` is a definite recording or
admission failure with its reason: ``queue_full`` (journal admission refused), ``queue_write_failed`` (the journal
write failed and was rolled back), ``rejected`` (admitted, then permanently refused and set aside; a failed
checkpoint write can leave the journal copy) or ``message_unavailable``. ``unknown`` means this call cannot tell;
``admission_unconfirmed`` is a journal write that failed and could not be rolled back, so its records may still be
replayed. A callback whose journal write fails raises, so those two reasons appear only in the retained outcome
(``host_outcomes``). A receipt never says whether a chat platform delivered the reply: that is a
separate fact (``DeliveryReceipt`` in the runtime). Receipts carry source references, never text.
"""

VERSION = "host-recording-receipt-v1"
REASONS = {
    "recorded": frozenset(),
    # Why server storage is unconfirmed: no client; this call's bounded replay did not reach the record (or another
    # replay held the journal); or an attempt was interrupted after it may have committed.
    "queued": frozenset({"service_unavailable", "replay_not_observed", "server_outcome_unknown"}),
    "excluded": frozenset({"server_paused", "capture_stale", "local_pause", "pause_requested",
                           "turn_identity_conflict", "erased", "group_recording_disabled", "speaker_unidentified"}),
    "failed": frozenset({"queue_full", "queue_write_failed", "rejected", "message_unavailable"}),
    "unknown": frozenset({"turn_not_staged", "turn_ambiguous", "turn_already_finished", "turn_mismatch",
                          "confirmation_missing", "admission_unconfirmed"}),
}
STATES = tuple(REASONS)
SCOPES = frozenset({"brain", "installation", "user", "conversation", "local", "turn", "adapter"})
# A local control's owner: a conversation pause belongs to the installation's own memory or to one user.
APPLIES_TO = frozenset({"installation", "user"})
EVIDENCE = frozenset({"current_policy", "cached_policy", "unreadable_policy", "write_rejected", "unspecified"})
STORED = ("evidence", "applies_to")


def source(record: dict | None) -> dict | None:
    """The exact reference a note or extraction would cite, or None when this call never knew the message key."""
    if not isinstance(record, dict) or not isinstance(record.get("source_event_key"), str):
        return None
    return {"producer_ref": record.get("producer_ref"), "source_event_key": record["source_event_key"],
            "source_revision": 1}


def message(role: str, reference: dict | None, state: str, reason: str | None = None, **details) -> dict:
    if role not in ("user", "assistant") or state not in REASONS:
        raise ValueError("A recording receipt needs a message role and a known state.")
    if (reason is None) != (state == "recorded") or reason is not None and reason not in REASONS[state]:
        raise ValueError(f"Recording state {state} cannot have reason {reason}.")
    scope = details.get("scope")
    if (state == "excluded") != (scope is not None) or scope is not None and scope not in SCOPES:
        raise ValueError("Excluded messages, and only they, name the scope of the policy that excluded them.")
    if details.get("evidence") not in (None, *EVIDENCE):
        raise ValueError("Unknown recording-policy evidence.")
    if details.get("applies_to") not in (None, *APPLIES_TO) or details.get("applies_to") and state != "excluded":
        raise ValueError("Only an excluded message names the owner of a local control.")
    value = {"role": role, "source": reference, "state": state}
    if reason is not None:
        value["reason"] = reason
    value.update({key: item for key, item in details.items() if item is not None})
    return value


def exclusion(reason: str, scope: str, **details) -> dict:
    """The stored cause of a staged turn's exclusion; validated so a bad cause fails where it is written."""
    message("user", None, "excluded", reason, scope=scope, **details)
    return {"reason": reason, "scope": scope, **{key: item for key, item in details.items() if item is not None}}


def server_evidence(policy: dict) -> str:
    return {"current": "current_policy", "cached": "cached_policy"}.get(policy.get("availability"),
                                                                         "unreadable_policy")


def turn(messages: list[dict]) -> dict:
    counts = {}
    for item in messages:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    return {"version": VERSION, "messages": messages, "states": counts}


def summary(receipt: dict | None) -> str:
    """One line for logs: roles, states and reasons only."""
    if not isinstance(receipt, dict) or not isinstance(receipt.get("messages"), list):
        return "recording receipt unavailable"
    parts = []
    for item in receipt["messages"]:
        reason = f" ({item['reason']}" + (f", {item['scope']}" if item.get("scope") else "") + ")" \
            if item.get("reason") else ""
        parts.append(f"{item['role']} {item['state']}{reason}")
    return "; ".join(parts) or "no messages"


def needs_attention(receipt: dict | None) -> bool:
    """Whether some message was neither confirmed, queued nor deliberately excluded."""
    if not isinstance(receipt, dict) or not isinstance(receipt.get("messages"), list):
        return True
    return any(item.get("state") in ("failed", "unknown") for item in receipt["messages"])
