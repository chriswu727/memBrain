"""Exact vs HNSW nearest-neighbour time in one brain, with other small brains present (synthetic 384-d vectors)."""
import random
import statistics
import time

import psycopg

DSN = "postgresql://postgres:ci-disposable-admin@127.0.0.1:55432/agent_memory"
DIM, K = 384, 50
rnd = random.Random(7)


def vec():
    return "[" + ",".join(f"{rnd.gauss(0, 1):.4f}" for _ in range(DIM)) + "]"


with psycopg.connect(DSN, autocommit=True) as conn:
    conn.execute("DROP TABLE IF EXISTS vb")
    conn.execute("CREATE TABLE vb (brain int, id int, embedding vector NOT NULL)")
    conn.execute("CREATE INDEX ON vb (brain)")
    with conn.cursor().copy("COPY vb (brain, id, embedding) FROM STDIN") as copy:
        for brain in range(1, 21):
            for i in range(500):
                copy.write_row((brain, i, vec()))
    have = 0
    for target in (10_000, 50_000, 200_000):
        with conn.cursor().copy("COPY vb (brain, id, embedding) FROM STDIN") as copy:
            for i in range(have, target):
                copy.write_row((0, i, vec()))
        have = target
        conn.execute("ANALYZE vb")
        conn.execute("SET max_parallel_workers_per_gather = 0")
        times = []
        for _ in range(5):
            query = vec()
            started = time.perf_counter()
            conn.execute("SELECT id FROM vb WHERE brain = 0 ORDER BY embedding <=> %s::vector LIMIT %s",
                         (query, K)).fetchall()
            times.append((time.perf_counter() - started) * 1000)
        print(f"{target:>7} rows in the brain: exact median {statistics.median(times):.0f} ms", flush=True)
    started = time.perf_counter()
    conn.execute("CREATE INDEX vb_hnsw ON vb USING hnsw ((embedding::vector(384)) vector_cosine_ops)")
    print(f"HNSW build over {have + 10_000} rows: {time.perf_counter() - started:.0f} s", flush=True)
    conn.execute("SET hnsw.ef_search = 200")
    for brain, label in ((0, "large brain"), (5, "small brain")):
        times, counts = [], []
        for _ in range(5):
            query = vec()
            started = time.perf_counter()
            rows = conn.execute("SELECT id FROM vb WHERE brain = %s ORDER BY embedding::vector(384) <=> "
                                "%s::vector(384) LIMIT %s", (brain, query, K)).fetchall()
            times.append((time.perf_counter() - started) * 1000)
            counts.append(len(rows))
        print(f"HNSW {label}: median {statistics.median(times):.0f} ms, rows returned {counts}", flush=True)
    conn.execute("DROP TABLE vb")
