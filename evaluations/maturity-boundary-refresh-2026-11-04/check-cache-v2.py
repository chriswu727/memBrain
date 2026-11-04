import json
import sys
import importlib.util
import hashlib
from pathlib import Path

from membrain import desktop, host
from membrain.adapters.chatbot import ChatMemory, Speaker

mode = sys.argv[1]
root = Path(__file__).parent
if mode == 'before':
    spec = importlib.util.spec_from_file_location('membrain.adapters.chatbot_reference', root / 'chatbot-reference.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    ChatMemory, Speaker = module.ChatMemory, module.Speaker
directory = root / f'cache-v2-{mode}-installation'
fact = 'Jordan and the user used to hike Mount Tam together.' 
result = {}
try:
    host.start(directory)
    memory = ChatMemory(directory)
    speaker = Speaker('audit', 'synthetic-person')
    memory.note(speaker, fact)
    first = memory.context(speaker, 'Any hiking suggestions?', session='cache-audit')
    with host.ready_client(directory, memory.user_id(speaker)) as client:
        client.add_boundary('old relationship', aliases=['Jordan'])
    second = memory.context(speaker, 'Any trail ideas?', session='cache-audit')
    result = {'before_contains_fact': fact in first, 'after_contains_fact': fact in second,
              'boundary_still_explained': 'old relationship (also: Jordan)' in second,
              'first_context': first, 'second_context': second, 'model_calls': 0}
finally:
    result['stop'] = desktop.stop(directory)
    (root / f'cache-v2-{mode}.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('first_context', 'second_context', 'stop')}))
assert result['before_contains_fact'] and not result['after_contains_fact'] and result['boundary_still_explained']
