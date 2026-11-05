import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from membrain import cognition


def compute(args, kwargs):
    return cognition.recall(*args, **kwargs)


if __name__ == '__main__':
    import uvicorn

    from membrain.api import create_app
    from membrain.local_profile import load_profile

    pool = None
    if sys.argv[3] == 'process':
        pool = ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn'))

        def offload(*args, **kwargs):
            return pool.submit(compute, args, kwargs).result(timeout=30)

        cognition.recall = offload
    try:
        uvicorn.run(create_app(load_profile(Path(sys.argv[1])).settings()), host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
