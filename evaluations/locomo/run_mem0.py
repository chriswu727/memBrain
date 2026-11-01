"""LoCoMo with Mem0 open source as the memory, under the same model, judge and embedding model as run_locomo.py.

Follows Mem0's own LoCoMo evaluation (mem0 v0.1.100, evaluation/src/memzero): every session's messages are added
for each speaker in pairs with the session date as a timestamp (the speaker's own messages as user, the other's
as assistant), each question searches the top 10 memories of both speakers, and Mem0's ANSWER_PROMPT answers from
them. Each message carries its session date in the text, exactly as memBrain's arm stores it, and Mem0's optional
nlp and extras (spaCy lemmas, BM25 keyword search) are installed. Differences from that run, which used the hosted Mem0 platform: this is the open-source library with its
default extraction prompts (the platform's custom instructions are not available there), and the answering model,
Mem0's own extraction and update calls, and the judge are all DeepSeek-V4.1-Flash with thinking disabled, as in
run_locomo.py. Embeddings come from the same local multilingual-e5-small model memBrain uses.

Run with a Python environment that has mem0ai installed:
  python run_mem0.py --data locomo10.json --out DIR [--conversations 0,1] [--workers 5]
Resumable: ingestion is marked per conversation and speaker, answers are appended per question.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "src")]

from run_locomo import CATEGORIES, Model, judge, log, questions, sessions  # noqa: E402

# Mem0's ANSWER_PROMPT from evaluation/prompts.py at v0.1.100 (Apache-2.0), verbatim.
ANSWER_PROMPT = """
    You are an intelligent memory assistant tasked with retrieving accurate information from conversation memories.

    # CONTEXT:
    You have access to memories from two speakers in a conversation. These memories contain
    timestamped information that may be relevant to answering the question.

    # INSTRUCTIONS:
    1. Carefully analyze all provided memories from both speakers
    2. Pay special attention to the timestamps to determine the answer
    3. If the question asks about a specific event or fact, look for direct evidence in the memories
    4. If the memories contain contradictory information, prioritize the most recent memory
    5. If there is a question about time references (like "last year", "two months ago", etc.),
       calculate the actual date based on the memory timestamp. For example, if a memory from
       4 May 2022 mentions "went to India last year," then the trip occurred in 2021.
    6. Always convert relative time references to specific dates, months, or years. For example,
       convert "last year" to "2022" or "two months ago" to "March 2023" based on the memory
       timestamp. Ignore the reference while answering the question.
    7. Focus only on the content of the memories from both speakers. Do not confuse character
       names mentioned in memories with the actual users who created those memories.
    8. The answer should be less than 5-6 words.

    # APPROACH (Think step by step):
    1. First, examine all memories that contain information related to the question
    2. Examine the timestamps and content of these memories carefully
    3. Look for explicit mentions of dates, times, locations, or events that answer the question
    4. If the answer requires calculation (e.g., converting relative time references), show your work
    5. Formulate a precise, concise answer based solely on the evidence in the memories
    6. Double-check that your answer directly addresses the question asked
    7. Ensure your final answer is specific and avoids vague time references

    Memories for user {speaker_1_user_id}:

    {speaker_1_memories}

    Memories for user {speaker_2_user_id}:

    {speaker_2_memories}

    Question: {question}

    Answer:
    """
TOP_K = 10
BATCH = 2
_usage_lock = threading.Lock()
EXTRACTION_USAGE: dict[str, int] = defaultdict(int)


class E5Embedder:
    """memBrain's local multilingual-e5-small, with e5's passage/query prefixes by Mem0 operation."""

    def __init__(self, model_directory: Path):
        from membrain.local_embeddings import LocalEmbeddingProvider

        self.provider = LocalEmbeddingProvider(model_directory)
        self.config = type("Config", (), {"embedding_dims": 384})()

    def embed(self, text, memory_action=None):
        purpose = "query" if memory_action == "search" else "document"
        return list(self.provider.embed([text or " "], purpose=purpose).vectors[0])


def memory_for(directory: Path, name: str, model_directory: Path):
    from langchain_core.embeddings import Embeddings
    from mem0 import Memory

    class Placeholder(Embeddings):  # Replaced right after construction.
        def embed_documents(self, texts):
            raise NotImplementedError

        def embed_query(self, text):
            raise NotImplementedError

    directory.mkdir(parents=True, exist_ok=True)
    memory = Memory.from_config({
        "llm": {"provider": "deepseek", "config": {
            "model": "deepseek-flash", "api_key": os.environ["DEEPSEEK_API_KEY"],
            "deepseek_base_url": "https://api.deepseek.com", "temperature": 0, "max_tokens": 2000}},
        "embedder": {"provider": "langchain", "config": {"model": Placeholder(), "embedding_dims": 384}},
        "vector_store": {"provider": "qdrant", "config": {
            "collection_name": name, "path": str(directory / "qdrant"), "embedding_model_dims": 384,
            "on_disk": True}},
        "history_db_path": str(directory / "history.db"),
    })
    memory.embedding_model = E5Embedder(model_directory)
    create = memory.llm.client.chat.completions.create

    def without_thinking(**params):  # As in run_locomo.py; also counts Mem0's own model usage.
        response = create(**params, extra_body={"thinking": {"type": "disabled"}})
        usage = getattr(response, "usage", None)
        if usage is not None:
            with _usage_lock:
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    EXTRACTION_USAGE[key] += int(getattr(usage, key, 0) or 0)
                EXTRACTION_USAGE["calls"] += 1
        return response

    memory.llm.client.chat.completions.create = without_thinking
    return memory


def ingest_speaker(memory, sample: dict, speaker: str, user_id: str, marker: Path) -> None:
    if marker.exists():
        return
    for _, date, turns in sessions(sample):
        messages = []
        for turn in turns:
            text = turn.get("text", "")
            if turn.get("blip_caption"):
                text += f" [shares an image: {turn['blip_caption']}]"
            role = "user" if turn["speaker"] == speaker else "assistant"
            # The session date goes into the text, as memBrain gets it: the open-source library does not pass the
            # timestamp metadata to extraction, so relative dates ("yesterday") would be resolved against today.
            messages.append({"role": role, "content": f"({date}) {turn['speaker']}: {text}"})
        for start in range(0, len(messages), BATCH):
            for attempt in range(3):
                try:
                    memory.add(messages[start:start + BATCH], user_id=user_id, metadata={"timestamp": date})
                    break
                except Exception as error:  # Mem0's own run retries each add as well.
                    log("add failed", user_id, type(error).__name__, str(error)[:120])
                    if attempt == 2:
                        raise
                    time.sleep(3)
    marker.write_text("done")


def search(memory, user_id: str, question: str) -> list[str]:
    found = memory.search(question, filters={"user_id": user_id}, top_k=TOP_K)
    items = found.get("results", found) if isinstance(found, dict) else found
    return [f"{(item.get('metadata') or {}).get('timestamp', '')}: {item['memory']}" for item in items]


def conversation(sample: dict, out: Path, categories, model_directory: Path) -> list[dict]:
    conversation_data = sample["conversation"]
    speakers = conversation_data["speaker_a"], conversation_data["speaker_b"]
    base = out / "mem0" / sample["sample_id"]
    memories = {}
    for speaker in speakers:
        memories[speaker] = memory_for(base / speaker, f"locomo_{sample['sample_id']}_{speaker}".replace("-", "_"),
                                       model_directory)
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda speaker: ingest_speaker(memories[speaker], sample, speaker, speaker,
                                                      base / speaker / "ingested"), speakers))
    log("ingested", sample["sample_id"])
    path = out / "answers-Mem0.jsonl"
    done = {json.loads(line)["id"] for line in path.read_text().splitlines()} if path.exists() else set()
    model = Model("https://api.deepseek.com", "deepseek-flash", cap=10_000)
    rows = []
    for qid, qa in questions(sample, categories):
        if qid in done:
            continue
        started = time.monotonic()
        found = {speaker: search(memories[speaker], speaker, qa["question"]) for speaker in speakers}
        prompt = ANSWER_PROMPT.format(speaker_1_user_id=speakers[0], speaker_2_user_id=speakers[1],
                                      speaker_1_memories=json.dumps(found[speakers[0]], indent=4),
                                      speaker_2_memories=json.dumps(found[speakers[1]], indent=4),
                                      question=qa["question"])
        answer = (model.chat([{"role": "system", "content": prompt}], max_tokens=300).get("content") or "").strip()
        verdict = judge(model, qa["question"], qa["answer"], answer)
        row = {"id": qid, "arm": "Mem0", "category": qa["category"], "question": qa["question"], "gold": qa["answer"],
               "answer": answer, "memories": found, "context_characters": len(prompt), **verdict,
               "seconds": round(time.monotonic() - started, 2)}
        with _usage_lock:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows.append(row)
    with _usage_lock:
        answering = out / "usage-Mem0-answering.json"
        totals = json.loads(answering.read_text()) if answering.exists() else {}
        for key, value in {**model.usage, "calls": model.calls}.items():
            totals[key] = totals.get(key, 0) + value
        answering.write_text(json.dumps(totals, indent=2))
        extraction = out / "usage-Mem0-extraction.json"
        extraction.write_text(json.dumps(dict(EXTRACTION_USAGE), indent=2))
    log("answered", sample["sample_id"], len(rows))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--conversations", default="")
    parser.add_argument("--categories", default="1,2,3,4")
    parser.add_argument("--workers", type=int, default=5, help="Conversations processed at once")
    parser.add_argument("--model-directory", required=True, help="memBrain's installed multilingual-e5-small model")
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text())
    selected = [data[int(index)] for index in args.conversations.split(",")] if args.conversations else data
    categories = {int(value) for value in args.categories.split(",")}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(args.workers) as pool:
        list(pool.map(lambda sample: conversation(sample, out, categories, Path(args.model_directory)), selected))
    rows = [json.loads(line) for line in (out / "answers-Mem0.jsonl").read_text().splitlines()]
    by = defaultdict(list)
    for row in rows:
        by[row["category"]].append(row["correct"])
    print({CATEGORIES[key]: f"{100 * sum(v) / len(v):.1f}% ({len(v)})" for key, v in sorted(by.items())},
          f"overall {100 * sum(r['correct'] for r in rows) / len(rows):.1f}% ({len(rows)})")


if __name__ == "__main__":
    main()
