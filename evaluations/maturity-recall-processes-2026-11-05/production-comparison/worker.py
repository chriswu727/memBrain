import os
import sys
from pathlib import Path

if __name__ == '__main__':
    os.environ['MEMBRAIN_RECALL_PROCESSES'] = '0' if sys.argv[3] == 'inline' else '2'
    import uvicorn
    from membrain.api import create_app
    from membrain.local_profile import load_profile
    uvicorn.run(create_app(load_profile(Path(sys.argv[1])).settings()), host='127.0.0.1', port=int(sys.argv[2]), log_level='error')
