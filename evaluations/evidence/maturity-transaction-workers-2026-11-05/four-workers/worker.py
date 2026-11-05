import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

SERVICE = None


def initialize(directory, barrier):
    from membrain.config import configured_service
    from membrain.local_profile import load_profile
    from multiprocessing.util import Finalize

    global SERVICE
    manager = configured_service(load_profile(Path(directory)).settings())
    SERVICE = manager.__enter__()
    assert SERVICE.recall_runner is None
    Finalize(None, manager.__exit__, args=(None, None, None), exitpriority=10)
    barrier.wait()


def ready():
    return os.getpid()


def respond(principal, request):
    return SERVICE.respond(principal, request)


if __name__ == '__main__':
    from dataclasses import replace
    import uvicorn
    from membrain.api import create_app
    from membrain.local_profile import load_profile
    from membrain.service import MemoryService

    settings = load_profile(Path(sys.argv[1])).settings()
    if sys.argv[3] == 'process':
        original = MemoryService.respond
        context = multiprocessing.get_context('spawn')
        with ProcessPoolExecutor(max_workers=4, mp_context=context, initializer=initialize,
                                 initargs=(sys.argv[1], context.Barrier(4, timeout=20))) as pool:
            futures = [pool.submit(ready) for _ in range(4)]
            for future in futures:
                future.result(timeout=30)

            def dispatch(self, principal, request):
                if request.get('action') == 'recall':
                    return pool.submit(respond, principal, request).result(timeout=30)
                return original(self, principal, request)

            MemoryService.respond = dispatch
            uvicorn.run(create_app(replace(settings, recall_processes=0)), host='127.0.0.1',
                        port=int(sys.argv[2]), log_level='error')
    else:
        uvicorn.run(create_app(settings), host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
