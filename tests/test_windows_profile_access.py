import ctypes
from ctypes import wintypes
from types import SimpleNamespace

import pytest

from membrain import local_profile


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


@pytest.mark.parametrize("apply_succeeds", [True, False])
def test_private_windows_acl_names_the_token_user_and_sets_the_owner(tmp_path, monkeypatch, apply_succeeds):
    calls = []

    def convert(sddl, version, output, size):
        calls.append((sddl, version))
        output._obj.value = 1234
        return True

    def apply(path, flags, descriptor):
        calls.append((path, flags, descriptor.value))
        return apply_succeeds

    security = SimpleNamespace(ConvertStringSecurityDescriptorToSecurityDescriptorW=Function(convert),
                               SetFileSecurityW=Function(apply))
    kernel = SimpleNamespace(LocalFree=Function(lambda pointer: calls.append(("free", pointer.value))))
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: security if name == "advapi32" else kernel,
                        raising=False)
    sid = "S-1-5-21-123-456-789-1001"
    monkeypatch.setattr(local_profile, "_windows_user_sid", lambda *args: sid)
    path = tmp_path / "profile.json"
    if apply_succeeds:
        local_profile._restrict_windows_access(path)
    else:
        with pytest.raises(local_profile.LocalProfileError, match="restrict profile access"):
            local_profile._restrict_windows_access(path)
    assert calls == [(f"O:{sid}D:P(A;OICI;FA;;;{sid})", 1),
                     (str(path), 0x80000005, 1234), ("free", 1234)]


@pytest.mark.parametrize("fail_at", [None, "token", "size", "information", "conversion"])
def test_windows_user_sid_uses_token_user_and_releases_native_handles(fail_at):
    calls = []
    expected = "S-1-5-21-123-456-789-1001"

    def open_token(process, access, output):
        assert (process, access) == (1, 0x0008)
        if fail_at == "token":
            return False
        output._obj.value = 2
        return True

    def information(token, kind, buffer, size, needed):
        assert token.value == 2 and kind == 1
        needed._obj.value = 0 if fail_at == "size" else 32
        if buffer is None:
            return False
        if fail_at == "information":
            return False
        ctypes.cast(buffer, ctypes.POINTER(wintypes.LPVOID)).contents.value = 3
        return True

    def convert(sid, output):
        assert sid == 3
        if fail_at == "conversion":
            return False
        output._obj.value = expected
        return True

    security = SimpleNamespace(OpenProcessToken=Function(open_token),
                               GetTokenInformation=Function(information),
                               ConvertSidToStringSidW=Function(convert))
    kernel = SimpleNamespace(GetCurrentProcess=Function(lambda: 1),
                             CloseHandle=Function(lambda handle: calls.append(("close", handle.value))),
                             LocalFree=Function(lambda pointer: calls.append(("free", bool(pointer.value)))))
    if fail_at is None:
        assert local_profile._windows_user_sid(security, kernel) == expected
        assert calls == [("free", True), ("close", 2)]
    else:
        with pytest.raises(local_profile.LocalProfileError, match="identify the current Windows user"):
            local_profile._windows_user_sid(security, kernel)
        assert calls == ([] if fail_at == "token" else [("close", 2)])
