import json
import multiprocessing
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from membrain import host
from membrain.build_identity import BUILD_ID


def run(job):
    operation, directory, turn = job
    root = Path(directory)
    host.ready_client = lambda *args: None
    host.start_in_background = lambda *args: None
    if operation == 'stage':
        host.prompt_context(root, 'shared', f'Question {turn}', turn_id=turn, user_id='synthetic-user')
        return None
    records = host.finish_turn(root, 'shared', f'Answer {turn}', turn_id=turn, user_id='synthetic-user',
                               prompt=f'Question {turn}')
    if records:
        assert [item['text'] for item in records] == [f'Question {turn}', f'Answer {turn}']
        assert records[1]['parent_source_event_keys'] == [f'shared:{turn}:user']
    return len(records)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='membrain-turn-process-') as temporary:
        directory = str(Path(temporary).resolve())
        accepted = 0
        with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as pool:
            for batch in range(16):
                turns = [f'{batch}:{i}' for i in range(24)]
                list(pool.map(run, [('stage', directory, turn) for turn in turns]))
                receipts = list(pool.map(run, [('finish', directory, turn) for turn in reversed(turns) for _ in range(2)]))
                assert sum(receipts) == 48
                accepted += sum(value == 2 for value in receipts)
        records = [json.loads(line) for line in (Path(directory)/'plugin/spool.jsonl').read_text().splitlines()]
        assert len(records) == 768
        assert len({record['source_event_key'] for record in records}) == len(records)
        state = host.session_state(Path(directory), 'shared')
        assert len(state['turns']) == 256 and all(entry.get('done') for entry in state['turns'].values())
        print(json.dumps({'build_id': BUILD_ID, 'processes': 4, 'staged_turns': 384,
                          'finish_callbacks': 768, 'accepted_receipts': accepted,
                          'spooled_records': len(records), 'unique_source_keys': len(records),
                          'retained_finished_markers':len(state['turns']), 'passed':True}, indent=2))
