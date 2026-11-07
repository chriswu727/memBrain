import hashlib
import importlib.util
import json
import math
import os
import sys
import time
from pathlib import Path

from membrain import desktop, host
from membrain.adapters import chatbot
from membrain.local_profile import load_profile

root = Path(__file__).parent
spec = importlib.util.spec_from_file_location('membrain.adapters.chatbot_reference', root / 'chatbot-reference.py')
reference = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)
directory = root / 'cache-v2-after-installation'
result = {'fixture': 'one synthetic user, one bounded note, one boundary, recording paused',
          'model_calls': 0, 'phases': [], 'purpose': 'adapter-context diagnostic, not R5 or capacity qualification'}
speaker = chatbot.Speaker('audit', 'synthetic-person')
try:
    host.start(directory)
    user = chatbot.ChatMemory(directory).user_id(speaker)
    host.pause(directory, user_id=user)
    for index, module in enumerate((reference, chatbot, chatbot, reference)):
        memory = module.ChatMemory(directory)
        samples = []
        for turn in range(21):
            start = time.perf_counter()
            context = memory.context(speaker, 'Any trail ideas?', session=f'cost-phase-{index}')
            elapsed = (time.perf_counter() - start) * 1000
            assert 'used to hike Mount Tam together' not in context
            assert 'old relationship (also: Jordan)' in context
            if turn:
                samples.append(elapsed)
        ordered = sorted(samples)
        result['phases'].append({'implementation': 'reference' if module is reference else 'current',
                                 'n': len(samples), 'raw_ms': samples,
                                 'median_ms': round((ordered[9] + ordered[10]) / 2, 2),
                                 'p95_ms': round(ordered[math.ceil(.95 * len(ordered)) - 1], 2)})
finally:
    result['stop'] = desktop.stop(directory)
    (root / 'context-cost.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps([{k: v for k, v in phase.items() if k != 'raw_ms'} for phase in result['phases']]))
