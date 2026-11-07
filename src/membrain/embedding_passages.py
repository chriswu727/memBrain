from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPassage:
    ids: tuple[int, ...]
    start: int
    end: int


def inference_batches(sequences, *, max_batch_size=32):
    batch, width = [], 0
    for sequence in sequences:
        next_width = max(width, len(sequence))
        count = len(batch) + 1
        if batch and (count > min(32, max_batch_size) or count * next_width > 4096
                      or count * next_width ** 2 > 1048576):
            yield batch
            batch, width = [], 0
        batch.append(sequence)
        width = max(width, len(sequence))
    if batch:
        yield batch


def token_passages(tokenizer, text, prefix, *, max_tokens=512, max_characters=400, overlap_characters=80):
    if not text or max_tokens < 3 or not 0 <= overlap_characters < max_characters:
        raise ValueError("Passages require text and bounded overlap and token limits.")
    windows = []
    begin = 0
    while begin < len(text):
        end = min(begin + max_characters, len(text))
        encoding = tokenizer.encode(prefix + text[begin:end])
        while len(encoding.ids) > max_tokens:
            if end == begin + 1:
                raise ValueError("A source character cannot fit within the token limit.")
            end = begin + max(1, (end - begin) // 2)
            encoding = tokenizer.encode(prefix + text[begin:end])
        windows.append(TokenPassage(tuple(encoding.ids), begin, end))
        if end == len(text):
            break
        begin = end - min(overlap_characters, (end - begin) // 4)
    return tuple(windows)
