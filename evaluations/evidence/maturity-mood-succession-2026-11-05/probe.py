import hashlib
import importlib.util
import json
import statistics
import time
from pathlib import Path
from unittest.mock import patch
from membrain import mood

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('membrain._baseline_mood',ROOT/'baseline_mood.py')
baseline=importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
report={'scope':'Pure affect trigger construction, no DB/HTTP/LLM; parity and scaling, not R5.','rows':[]}
for count in (50,250,501):
 for kind in ('distinct','repeated'):
  records=[{'id':f'a{i}','note_id':f'n{i}','topic':f'Topic {i if kind=="distinct" else i%7}',
            'sequence':i+1,'basis':'reported' if i%3 else 'inferred','sensitive':i%11==0,
            'valence':(i%5)-2,'intensity':i%4,'label':f'feeling{i}',
            'recorded_at':f'2027-03-14T09:{i%60:02d}:00Z','note_text':f'Synthetic event {i}.'}
           for i in range(count)]
  with patch('membrain.affect._records',return_value=list(reversed(records))),patch('membrain.affect.latest_marker',return_value=None):
   expected=baseline._affect_triggers(None,None,None,None)
   actual=mood._affect_triggers(None,None,None,None)
   assert actual==expected
   samples={'baseline':[],'candidate':[]}
   for turn in range(12):
    for label,fun in ([('baseline',baseline._affect_triggers),('candidate',mood._affect_triggers)] if turn%2==0 else [('candidate',mood._affect_triggers),('baseline',baseline._affect_triggers)]):
     begin=time.thread_time_ns(); result=fun(None,None,None,None)
     samples[label].append((time.thread_time_ns()-begin)/1e6)
     assert result==expected
   report['rows'].append({'count':count,'topics':kind,'trigger_count':len(actual),'equal':True,'median_cpu_ms':{k:statistics.median(v) for k,v in samples.items()},'samples_cpu_ms':samples})
report['source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(mood.__file__), ROOT/'baseline_mood.py',Path(__file__))}
(ROOT/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
for row in report['rows']: print({k:v for k,v in row.items() if k!='samples_cpu_ms'})
