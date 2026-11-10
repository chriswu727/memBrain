import argparse
import io
import json
from contextlib import contextmanager
from unittest.mock import Mock

import httpx
import pytest

from membrain import desktop_chat, desktop_cli
from membrain.local_profile import ensure_profile, load_profile
from membrain.runtime import DeliveryRequest, RuntimeBlocked, TurnResult


def arguments(*values):
    parser = argparse.ArgumentParser()
    desktop_cli.add_commands(parser.add_subparsers())
    return parser.parse_args(["desktop", *values])


def test_configuration_is_separate_and_never_prints_secrets(tmp_path, monkeypatch, capsys):
    from membrain.chat_config import load_chat_configuration

    profile = ensure_profile(tmp_path / "profile")
    before = (profile.directory / "profile.json").read_bytes()
    monkeypatch.setenv("CHAT_TEST_KEY", "test-secret-chat-credential")
    desktop_cli.dispatch(arguments(
        "configure-chat", "--directory", str(profile.directory),
        "--base-url", "https://models.example/v1", "--model", "chat-model",
        "--api-key-env", "CHAT_TEST_KEY", "--non-interactive",
    ))
    result = capsys.readouterr()
    assert json.loads(result.out) == {"chat": "configured", "cognition": "not_configured",
                                      "service_restart_required": False}
    assert "test-secret-chat-credential" not in result.out + result.err
    assert (profile.directory / "profile.json").read_bytes() == before
    saved = load_chat_configuration(profile.directory)
    assert saved.model == "chat-model"
    assert saved.thinking is None
    assert load_profile(profile.directory).brain_id == profile.brain_id


def test_configure_interactively_uses_hidden_key_input(tmp_path, monkeypatch, capsys):
    from membrain.chat_config import load_chat_configuration

    monkeypatch.setattr(desktop_chat.sys, "stdin", Mock(isatty=lambda: True))
    answers = iter(["https://models.example/v1", "configured-model"])
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    hidden = Mock(return_value="hidden-provider-key")
    monkeypatch.setattr(desktop_chat.getpass, "getpass", hidden)
    args = arguments("configure-chat", "--directory", str(tmp_path / "new-profile"))
    desktop_cli.dispatch(args)
    hidden.assert_called_once()
    output = capsys.readouterr()
    assert "hidden-provider-key" not in output.out + output.err
    assert load_chat_configuration(args.directory).api_key == "hidden-provider-key"


@pytest.mark.parametrize("flags", [
    ["--non-interactive"], ["--model", "missing-endpoint"],
    ["--use-cognition", "--model", "conflict"],
    ["--base-url", "https://models.example", "--model", "model", "--api-key-env", "MISSING_CHAT_KEY"],
])
def test_invalid_configuration_does_not_create_profile(tmp_path, monkeypatch, flags):
    monkeypatch.delenv("MISSING_CHAT_KEY", raising=False)
    args = arguments("configure-chat", "--directory", str(tmp_path / "new-profile"), *flags)
    with pytest.raises(ValueError):
        desktop_chat.configure(args)
    assert not args.directory.exists()


@pytest.fixture
def fake_session(tmp_path, monkeypatch):
    from membrain import agent_session

    profile = ensure_profile(tmp_path / "profile")
    session = Mock(pending=None)
    session.respond.return_value = TurnResult("turn-test", "completed", "response")
    session.resume.return_value = TurnResult("turn-test", "completed", "response", replayed=True)

    @contextmanager
    def connect(*args, **kwargs):
        session.connection = (args, kwargs)
        yield session

    factory = Mock(side_effect=connect)
    monkeypatch.setattr(agent_session, "open_agent", factory)
    session.factory = factory
    session.profile = profile
    return session


def test_one_shot_preserves_message_identity_and_terminal_delivery(fake_session, capsys):
    args = arguments("chat", "--directory", str(fake_session.profile.directory),
                     "--conversation", "room", "--branch", "branch", "--message", "Hello",
                     "--message-id", "event-17", "--orientation", "on_demand")
    desktop_chat.run(args)
    fake_session.respond.assert_called_once_with("Hello", message_id="event-17")
    bound = fake_session.connection[1]
    assert (bound["conversation_id"], bound["branch_id"]) == ("room", "branch")
    assert bound["policy"].orientation_policy == "on_demand"
    assert capsys.readouterr().out == ""
    receipt = bound["deliver"](DeliveryRequest("turn", "delivery", "Actual response"))
    assert receipt.state == "delivered"
    assert capsys.readouterr().out == "Actual response\n"


def test_terminal_flush_failure_does_not_acknowledge_delivery(monkeypatch):
    stream = Mock()
    stream.write.return_value = len("answer\n")
    stream.flush.side_effect = BrokenPipeError("private output target")
    monkeypatch.setattr(desktop_chat.sys, "stdout", stream)
    with pytest.raises(RuntimeBlocked, match="delivery_uncertain"):
        desktop_chat._deliver(DeliveryRequest("turn", "delivery", "answer"))
    stream.write.assert_called_once_with("answer\n")


def test_terminal_short_write_does_not_acknowledge_delivery(monkeypatch):
    stream = Mock()
    stream.write.return_value = 2
    monkeypatch.setattr(desktop_chat.sys, "stdout", stream)
    with pytest.raises(RuntimeBlocked, match="delivery_uncertain"):
        desktop_chat._deliver(DeliveryRequest("turn", "delivery", "answer"))
    stream.flush.assert_not_called()


@pytest.mark.parametrize("flags", [
    ["--message", "Hello"], ["--message-id", "event"], [],
    ["--message", "   ", "--message-id", "event"],
    ["--message", "Hello", "--message-id", "invalid id"],
    ["--message", "Hello", "--message-id", "event", "--acknowledge-uncertain"],
    ["--cancel", ""], ["--cancel", "invalid turn"],
])
def test_invalid_chat_mode_never_opens_session(fake_session, monkeypatch, flags):
    monkeypatch.setattr(desktop_chat.sys, "stdin", io.StringIO())
    with pytest.raises(ValueError):
        desktop_chat.run(arguments("chat", *flags))
    fake_session.factory.assert_not_called()


def test_resume_does_not_generate_new_message_or_reprint_completed_answer(fake_session, capsys):
    desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory), "--resume"))
    fake_session.resume.assert_called_once_with()
    fake_session.respond.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ""
    assert "already completed" in output.err


def test_interactive_resume_and_retry_keep_original_identity(fake_session, monkeypatch, capsys):
    fake_session.pending = {"turn_id": "turn-pending", "message_id": "original-message"}
    fake_session.resume.side_effect = RuntimeBlocked("input_not_captured_retry_original_message", "turn-pending")
    answers = iter(["/resume", "/retry Original input", "/quit"])
    monkeypatch.setattr(desktop_chat.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory)))
    fake_session.respond.assert_called_once_with("Original input", message_id="original-message")
    fake_session.resume.assert_called_once_with()
    output = capsys.readouterr()
    assert "turn-pending" in output.err
    assert output.out == ""


def test_incomplete_commands_and_whitespace_do_not_become_model_input(fake_session, monkeypatch):
    answers = iter(["/retry", "/resume ", "/resume invalid", "/retry\ttext", " /quit "])
    monkeypatch.setattr(desktop_chat.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory)))
    fake_session.respond.assert_not_called()
    fake_session.resume.assert_called_once_with()


def test_service_failure_is_redacted_and_one_shot_fails(fake_session, capsys):
    fake_session.respond.side_effect = httpx.ConnectError("https://secret:password@private.example")
    with pytest.raises(SystemExit) as error:
        desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory),
                                   "--message", "Hi", "--message-id", "original"))
    assert error.value.code == 1
    output = capsys.readouterr()
    assert "memory_service_unavailable" in output.err
    assert "password" not in output.err
    assert output.out == ""


@pytest.mark.parametrize("acknowledged", [False, True])
def test_cancellation_is_explicit_and_does_not_generate_or_deliver(fake_session, capsys, acknowledged):
    turn_id = "turn-" + "a" * 40
    fake_session.cancel.return_value = {
        "turn_id": turn_id, "stage": "failed",
        "failure_code": "generation_uncertain" if acknowledged else "cancelled",
    }
    flags = ["--acknowledge-uncertain"] if acknowledged else []
    desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory),
                               "--cancel", turn_id, *flags))
    fake_session.cancel.assert_called_once_with(turn_id=turn_id, acknowledge_uncertain=acknowledged)
    fake_session.respond.assert_not_called()
    fake_session.resume.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ""
    assert ("remains unknown" in output.err) is acknowledged


@pytest.mark.parametrize("contents", [b"x" * 64001, b"\xff"])
def test_invalid_instruction_file_fails_before_opening_session(fake_session, tmp_path, contents):
    path = tmp_path / "instructions.txt"
    path.write_bytes(contents)
    with pytest.raises(ValueError):
        desktop_chat.run(arguments("chat", "--instructions-file", str(path),
                                   "--message", "Hello", "--message-id", "id"))
    fake_session.factory.assert_not_called()


def recording_state(server="on", device="on", conversation="on", **device_fields):
    states = [server, device, conversation]
    recording = "paused" if "paused" in states else "unknown" if "unknown" in states else "on"
    return {"recording": recording,
            "new_message": "unavailable" if server == "unknown" else "record" if recording == "on" else "temporary",
            "controls": {"server": {"scope": "brain", "state": server, "revision": None if server == "unknown" else 3},
                         "device": {"scope": "installation", "state": device, **device_fields},
                         "conversation": {"scope": "conversation_branch", "state": conversation}}}


def test_recording_commands_change_only_the_conversation_choice_and_are_never_sent(fake_session, monkeypatch, capsys):
    fake_session.set_off_record.side_effect = lambda off: recording_state(conversation="paused" if off else "on")
    fake_session.recording_state.return_value = recording_state()
    answers = iter(["/off-record", " /on-record ", "/recording", "/off-record now please", "/on-record: text",
                    "/recording extra", "/off-record:private text", "/off-recorded", "/quit"])
    monkeypatch.setattr(desktop_chat.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory)))
    assert [call.args for call in fake_session.set_off_record.call_args_list] == [(True,), (False,)]
    fake_session.recording_state.assert_called_once_with()
    fake_session.respond.assert_not_called()
    fake_session.resume.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ""
    assert "now off the record" in output.err and "now on the record" in output.err
    assert "were not sent or stored as a message" in output.err
    assert output.err.count("Invalid command arguments; no message was sent.") == 5
    assert "/resume only recovers a pending turn" in output.err


def test_resume_keeps_its_pending_turn_meaning_beside_the_recording_commands(fake_session, monkeypatch):
    fake_session.set_off_record.return_value = recording_state(conversation="paused")
    answers = iter(["/off-record", "/resume", "/quit"])
    monkeypatch.setattr(desktop_chat.sys, "stdin", Mock(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda: next(answers))
    desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory)))
    fake_session.resume.assert_called_once_with()
    fake_session.set_off_record.assert_called_once_with(True)
    fake_session.respond.assert_not_called()


@pytest.mark.parametrize("flag,expected", [("--off-record", True), ("--on-record", False), ("--recording-status", None)])
def test_scripted_recording_controls_print_state_and_send_no_message(fake_session, capsys, flag, expected):
    state = recording_state(server="unknown", conversation="paused" if expected else "on")
    fake_session.set_off_record.return_value = fake_session.recording_state.return_value = state
    desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory), flag))
    if expected is None:
        fake_session.set_off_record.assert_not_called()
    else:
        fake_session.set_off_record.assert_called_once_with(expected)
    fake_session.respond.assert_not_called()
    fake_session.resume.assert_not_called()
    output = capsys.readouterr()
    assert json.loads(output.out) == state
    assert "whole brain (server): unknown" in output.err
    assert "No message can be answered until it responds" in output.err
    assert "are handled as temporary" not in output.err and "Recording is on" not in output.err
    if expected:
        assert "now off the record" in output.err and "Temporary handling still needs the service's reservation" in output.err
    else:
        assert "Whether a new message would be recorded is unconfirmed" in output.err


@pytest.mark.parametrize("flags", [
    ["--off-record", "--on-record"], ["--off-record", "--message", "Hi", "--message-id", "event"],
    ["--recording-status", "--resume"], ["--on-record", "--cancel", "turn-" + "a" * 40],
])
def test_recording_controls_cannot_be_combined_with_another_mode(fake_session, flags):
    with pytest.raises(SystemExit):
        arguments("chat", *flags)
    fake_session.factory.assert_not_called()


def test_unconfirmed_controls_are_reported_unknown_and_never_as_recording_off(fake_session, capsys):
    from membrain.agent_session import SessionError

    lines = desktop_chat._recording_report(recording_state(server="unknown", device="unknown", conversation="unknown"))
    text = "\n".join(lines)
    assert "No message can be answered" in lines[0] and "could not be read either" in lines[1]
    assert text.count("unknown") == 3 and "paused" not in text and "off the record." not in text
    assert "handled as temporary" not in text
    timed = "\n".join(desktop_chat._recording_report(recording_state(device="paused", until=0)))
    assert "paused until 19" in timed and "are handled as temporary" in timed
    assert "paused until resumed" in "\n".join(desktop_chat._recording_report(recording_state(device="paused", until=None)))
    scoped = "\n".join(desktop_chat._recording_report(recording_state(host_conversations="paused")))
    assert "Recording is on for new messages" in scoped and "(installation): on; a separate local pause" in scoped
    assert "does not apply to this direct conversation" in scoped and "captured" not in scoped
    both = desktop_chat._recording_report(recording_state(server="paused", host_conversations="paused"))
    assert "are handled as temporary" in both[0] and "whole brain (server): paused." in both[1]
    assert "(installation): on; a separate local pause covers the host conversations" in both[2]
    assert "captured" not in "\n".join(both) and "Recording is on" not in "\n".join(both)
    assert "The two local controls apply to new messages" in both[-1]
    assert "pausing the server switch also stops recorded turns in progress" in both[-1]

    fake_session.set_off_record.side_effect = SessionError("session_state_unavailable")
    with pytest.raises(SystemExit) as error:
        desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory), "--off-record"))
    assert error.value.code == 1
    output = capsys.readouterr()
    assert output.out == "" and "session_state_unavailable" in output.err and "now off the record" not in output.err


def test_temporary_result_names_every_cause_and_never_calls_the_turn_recorded(fake_session, capsys):
    from membrain.runtime import TemporaryCause

    causes = (TemporaryCause("server_paused", "brain"), TemporaryCause("local_pause", "installation", 0.0),
              TemporaryCause("off_record", "conversation_branch"),
              TemporaryCause("local_state_unreadable", "installation"))
    fake_session.respond.return_value = TurnResult("turn-test", "completed", "response", ephemeral=True,
                                                   temporary_causes=causes)
    monitor = Mock()
    assert desktop_chat._perform(fake_session.respond, monitor)
    monitor.completed.assert_not_called()
    notice = capsys.readouterr().err
    for expected in ("memory recording is paused for this brain", "chat capture is paused on this device (until 19",
                     "this conversation branch is off the record", "its state is unknown",
                     "not saved or queued for learning"):
        assert expected in notice
    assert "recorded" not in notice.replace("/on-record records new messages again", "")
    legacy = TurnResult("turn-test", "completed", "response", ephemeral=True,
                        temporary_causes=(TemporaryCause("server_paused", "brain"),))
    assert desktop_chat._temporary_notice(legacy) == (
        "Temporary conversation: memBrain recording is paused. This turn was not saved or queued for learning.")
    replayed = TurnResult("turn-test", "completed", None, replayed=True, ephemeral=True)
    assert "reason is not stored" in desktop_chat._temporary_notice(replayed)


@pytest.mark.parametrize("code,advice", [
    ("off_record_reservation_rejected", "Nothing was generated, sent or saved"),
    ("pending_turn_recording_excluded", "was not converted"),
])
def test_blocked_privacy_outcomes_explain_that_nothing_was_recorded(fake_session, capsys, code, advice):
    from membrain.agent_session import SessionError

    turn_id = "turn-" + "b" * 40
    fake_session.pending = {"turn_id": turn_id, "message_id": "original"}
    fake_session.respond.side_effect = (RuntimeBlocked(code, turn_id) if code.startswith("off_record")
                                        else SessionError(code, turn_id))
    with pytest.raises(SystemExit):
        desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory),
                                   "--message", "Hi", "--message-id", "original"))
    output = capsys.readouterr()
    assert output.out == "" and code in output.err and advice in output.err and turn_id in output.err
    assert "Unknown generation or delivery is not retried automatically" not in output.err


def test_unreadable_local_control_with_a_reachable_service_promises_temporary_only_after_reservation(fake_session, capsys):
    for state in (recording_state(device="unknown"), recording_state(conversation="unknown")):
        fake_session.recording_state.return_value = state
        desktop_chat.run(arguments("chat", "--directory", str(fake_session.profile.directory), "--recording-status"))
        output = capsys.readouterr()
        assert json.loads(output.out)["new_message"] == "temporary" and json.loads(output.out)["recording"] == "unknown"
        assert "only after the memory service confirms a temporary reservation" in output.err
        assert "otherwise it stops before generation" in output.err and "whole brain (server): on." in output.err
        assert "No message can be answered" not in output.err and "paused" not in output.err
        assert output.err.count("unknown (") == 1
