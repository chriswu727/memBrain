import pytest
from test_candidates import Candidates, key
from test_candidates import candidates as candidates

from membrain import source_scripts
from membrain.learning import LearningEngine

pytestmark = pytest.mark.integration


def rows(candidates):
    with candidates.database.transaction(candidates.principal) as conn:
        return conn.execute("SELECT id,revision,document,source_han_majority FROM memory_assertions "
                            "WHERE brain_id=%s ORDER BY id,revision", (candidates.brain_id,)).fetchall()


def test_publication_classifies_original_content_and_idle_backfill_is_bounded_and_private(candidates, monkeypatch):
    texts = ["护照在抽屉", "The receipt from 京都 is on the table", "我的电脑是Apple的", "Москва 汉", "漢A"]
    for text in texts:
        candidates.add(text)
    expected = rows(candidates)
    assert all(row["source_han_majority"] is source_scripts.classify(row["document"]) for row in expected)
    other = Candidates(candidates.database)
    other.add("另一位用户的记忆")
    for owner in (candidates, other):
        with owner.database.transaction(owner.principal) as conn:
            conn.execute("UPDATE memory_assertions SET source_han_majority=NULL WHERE brain_id=%s", (owner.brain_id,))
    monkeypatch.setattr(source_scripts, "BACKFILL_BATCH", 2)
    monkeypatch.setattr(LearningEngine, "work_once", lambda *args: 0)

    with pytest.raises(RuntimeError, match="interrupted"):
        with candidates.database.transaction(candidates.principal) as conn:
            source_scripts.maintain(conn, candidates.params)
            raise RuntimeError("interrupted")
    assert all(row["source_han_majority"] is None for row in rows(candidates))
    for count in (2, 4, 5):
        assert candidates.service.work_once(candidates.principal, candidates.brain_id) == 0
        assert sum(row["source_han_majority"] is not None for row in rows(candidates)) == count
    assert rows(candidates) == expected
    assert all(row["source_han_majority"] is None for row in rows(other))


def test_suppressed_sources_are_not_backfilled(candidates):
    memory = candidates.add("护照在抽屉")
    with candidates.database.transaction(candidates.principal) as conn:
        conn.execute("UPDATE memory_assertions SET source_han_majority=NULL,suppressed=true "
                     "WHERE brain_id=%s AND id=%s AND revision=%s", (candidates.brain_id, *key(memory)))
        source_scripts.maintain(conn, candidates.params)
    assert rows(candidates)[0]["source_han_majority"] is None
