import json
from pathlib import Path

from membrain import desktop, host
from membrain.adapters.chatbot import ChatMemory, Speaker

directory = Path(__file__).parent / 'cache-check-after-installation'
result = {}
try:
    host.start(directory)
    memory = ChatMemory(directory)
    speaker = Speaker('audit', 'synthetic-person')
    memory.note(speaker, 'Jordan and the user used to hike Mount Tam together.')
    first = memory.context(speaker, 'Any hiking suggestions?', session='cache-audit')
    with host.ready_client(directory, memory.user_id(speaker)) as client:
        client.add_boundary('old relationship', aliases=['Jordan'])
    second = memory.context(speaker, 'Any trail ideas?', session='cache-audit')
    result = {'before_contains_topic': 'Jordan' in first, 'after_contains_topic': 'Jordan' in second,
              'first_context': first, 'second_context': second, 'model_calls': 0}
finally:
    result['stop'] = desktop.stop(directory)
    (Path(__file__).parent / 'cache-after.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('first_context', 'second_context', 'stop')}))
assert result['before_contains_topic'] and not result['after_contains_topic']
