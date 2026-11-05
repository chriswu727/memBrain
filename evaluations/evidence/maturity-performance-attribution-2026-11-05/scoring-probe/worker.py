import os
import sys
from pathlib import Path

from membrain.lexical_candidates import LexicalScorer


def score(query, texts, origins):
    scorer = LexicalScorer(query, texts, origins=origins)
    return scorer, {text: scorer(query, text) for text in texts}


class CachedScorer(LexicalScorer):
    def __call__(self, query, text):
        if text in self.scores:
            return self.scores[text]
        return super().__call__(query, text)


if __name__ == '__main__':
    os.environ['MEMBRAIN_RECALL_PROCESSES'] = '2'
    import uvicorn
    from membrain.api import create_app
    from membrain.local_profile import load_profile
    from membrain.recall_executor import RecallExecutor

    if sys.argv[3] == 'process':
        original_init = RecallExecutor.__init__
        executor = None

        def initialize(self, *args, **kwargs):
            global executor
            original_init(self, *args, **kwargs)
            executor = self

        def from_memories(cls, query, memories):
            memories = list(memories)
            origins = [{('source', ref['event_id'], ref['event_revision'], ref['source_content_sha256'])
                        for ref in memory['evidence_refs'] if ref['relationship'] == 'supports'}
                       or {('memory', memory['memory_id'], memory['revision'])} for memory in memories]
            texts = [memory['statement'] for memory in memories]
            assert executor._slots.acquire(blocking=False)
            future = None
            try:
                future = executor._executor().submit(score, query, texts, origins)
                future.add_done_callback(lambda _: executor._slots.release())
                scorer, scores = future.result(timeout=10)
            finally:
                if future is None:
                    executor._slots.release()
            result = CachedScorer.__new__(CachedScorer)
            result.__dict__.update(scorer.__dict__)
            result.scores = scores
            return result

        RecallExecutor.__init__ = initialize
        LexicalScorer.from_memories = classmethod(from_memories)
    uvicorn.run(create_app(load_profile(Path(sys.argv[1])).settings()),
                host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
