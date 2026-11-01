"""Privacy filtering shared by recording and note writes."""
import os
import re

_PRIVATE = re.compile(r"<private>.*?(?:</private>|\Z)", re.IGNORECASE | re.DOTALL)
_SECRETS = [re.compile(pattern, flags) for pattern, flags in (
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.DOTALL),
    (r"\b(?:sk|pk|rk)-(?:ant-|proj-|live-|test-)?[A-Za-z0-9_\-]{20,}", 0),
    (r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}", 0),
    (r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}", 0),
    (r"\bglpat-[A-Za-z0-9_\-]{20,}|\bhf_[A-Za-z0-9]{30,}|\bnpm_[A-Za-z0-9]{36}\b", 0),
    (r"\bAKIA[0-9A-Z]{16}\b", 0),
    (r"\bxox[abposr]-[A-Za-z0-9\-]{10,}", 0),
    (r"\bAIza[0-9A-Za-z_\-]{35}\b", 0),
    (r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", 0),
    (r"(?i)\b(?:bearer)\s+[A-Za-z0-9._\-]{20,}", 0),
    (r"(?i)\b((?:api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]\s*)(\"[^\"]{6,}\"|'[^']{6,}'|\S{6,})", 0),
    (r"(?i)\b((?:aws_secret_access_key|client_secret|access_token|refresh_token|auth_token|secret_key|private_key)"
     r"\s*[:=]\s*)(\"[^\"]{6,}\"|'[^']{6,}'|\S{6,})", 0),
    # The password in a connection URL: postgresql://user:password@host
    (r"(?i)(\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:)([^\s@/]{3,})(?=@)", 0),
    # Said in words: "my password is ...", 「密码是……」
    (r"(?i)(\b(?:password|passcode|passphrase|pin code)\s+(?:is|was)\s+)(\S{4,})", 0),
    (r"((?:密码|口令|支付密码)\s*(?:是|为|：|:)\s*)(\S{4,})", 0),
)]
_DIGITS = re.compile(r"(?<!\d)(?<!\d\.)(?:\d[ \-]?){12,18}\d(?!\d|\.\d)")
_CN_ID = re.compile(r"(?<![0-9A-Za-z])\d{17}[\dXx](?![0-9A-Za-z])")
_SSN = re.compile(r"(?<![\d-])\d{3}-\d{2}-\d{4}(?![\d-])")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<![\w+.])\+?\(?\d[\d \-()]{7,20}\d(?!\w|\.\d)")
_DATE = re.compile(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}-\d{4}")
_BLOCK_TAG = re.compile(r"<(\s*/?\s*)(membrain[\w-]*)", re.IGNORECASE)
SECRET_MARK = "[secret removed]"
PRIVATE_MARK = "[private]"
NUMBER_MARK = "[personal number removed]"
CONTACT_MARK = "[contact removed]"


def _luhn(digits: str) -> bool:
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit) * (2 if index % 2 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


def _cn_id(number: str) -> bool:
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    check = "10X98765432"[sum(int(digit) * weight for digit, weight in zip(number, weights)) % 11]
    return number[-1].upper() == check


def _numbers(text: str) -> str:
    """Remove card and identity numbers. Checksums keep ordinary long numbers (order ids, timestamps) intact."""
    text = _CN_ID.sub(lambda match: NUMBER_MARK if _cn_id(match.group()) else match.group(), text)
    text = _DIGITS.sub(lambda match: NUMBER_MARK if 13 <= len(digits := re.sub(r"\D", "", match.group())) <= 19
                       and _luhn(digits) else match.group(), text)
    return _SSN.sub(NUMBER_MARK, text)


def neutralize(text: str) -> str:
    """Defuse memBrain's own block tags inside stored text, so a remembered message cannot close a memory block
    and pose as instructions outside it (``</membrain-memory>`` becomes ``‹/membrain-memory>``)."""
    return _BLOCK_TAG.sub(lambda match: "\u2039" + match.group(1) + match.group(2), text)


def scrub(text: str) -> str:
    """Remove text the user marked private, values that look like credentials, and card and identity numbers.

    Email addresses and phone numbers are kept unless ``MEMBRAIN_REDACT_CONTACTS=1``: memory is often asked to
    keep them ("my sister's email is ...").
    """
    text = _PRIVATE.sub(PRIVATE_MARK, text)
    for pattern in _SECRETS:
        text = pattern.sub(lambda match: (match.group(1) + SECRET_MARK) if pattern.groups else SECRET_MARK, text)
    text = _numbers(text)
    if os.environ.get("MEMBRAIN_REDACT_CONTACTS", "").lower() in ("1", "true", "yes"):
        text = _PHONE.sub(lambda match: CONTACT_MARK if 10 <= len(re.sub(r"\D", "", match.group())) <= 15
                          and not _DATE.search(match.group()) else match.group(), _EMAIL.sub(CONTACT_MARK, text))
    return text
