def _stem(word: str) -> str:
    """Conservative English word-form folding so 'running', 'runs' and 'ran' meet 'run' in lexical recall.

    Stems only drop suffixes (apart from a few irregular forms), so a stem is usually a prefix of every form
    and stored text can still be found with prefix queries.
    """
    if word in _IRREGULAR_FORMS:
        return _IRREGULAR_FORMS[word]
    if len(word) < 4 or not word.isalpha():
        return word
    if len(word) >= 5 and word.endswith(("ies", "ied")):
        return word[:-3] + "y"
    for suffix in ("ing", "ed"):
        if not word.endswith(suffix):
            continue
        base = word[:-len(suffix)]
        if not word.endswith("eed") and len(base) >= 3 and re.search("[aeiouy]", base):
            if len(base) >= 4 and base[-1] == base[-2] and base[-1] not in "aeiouylsz":
                base = base[:-1]
            word = base
            break
    else:
        if word.endswith(("sses", "shes", "ches", "xes", "zes")):
            word = word[:-2]
        elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
            word = word[:-1]
    return word[:-1] if len(word) >= 4 and word.endswith("e") else word

def _terms(text: str) -> tuple[set[str], set[str], set[str]]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("’", "'")
    if "'" in normalized:
        normalized = re.sub(r"\bwon't\b", "will not", normalized)
        normalized = re.sub(r"\bcan't\b", "can not", normalized)
        normalized = re.sub(r"\bshan't\b", "shall not", normalized)
        normalized = re.sub(r"n't\b", " not", normalized)
        normalized = re.sub(r"'(?:m|re|ve|ll|d|s)\b", " ", normalized)
    words = {_stem(word) for word in re.findall(r"[a-z0-9_]+", normalized) if word not in _IGNORED_TERMS}
    runs = re.findall(r"[\u3400-\u9fff]+", _CJK_FILLERS.sub(" ", normalized))
    singles = {char for run in runs for char in run if char not in "的了是吗呢么在我你他她和有"}
    pairs = {run[index:index + 2] for run in runs for index in range(len(run) - 1)}
    return words, pairs, singles
