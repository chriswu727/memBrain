import ast
import hashlib
import json
import random
import socket
import statistics
import time
from pathlib import Path
from membrain import cognition, embedded_database, host, lexical_candidates
from membrain.helpers import Principal
from membrain.local_profile import load_profile
from membrain.service import MemoryService
from membrain.storage import Database

root=Path(__file__).parent;repo=Path('/Users/yichen/tmp/membrain-review-20261029')
profile=load_profile(Path('/Users/yichen/tmp/membrain-attribution-d4f-20261104/failed-corpus-copy'))
report={'purpose':'fixed ABBA pure lexical CPU probe with exact token/weight/score equivalence; not HTTP, SQL or R5 acceptance','model_calls':0,'completed':False,'arms':[]}
original_terms,original_stem=cognition._terms,cognition._stem
source=(repo/'src/membrain/cognition.py').read_text();tree=ast.parse(source)
definition={node.name:ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef)}
fast_stem=definition['_stem'].replace('        base = word[:-len(suffix)]\n        if word.endswith(suffix) and not word.endswith("eed") and len(base) >= 3 and re.search("[aeiouy]", base):','        if not word.endswith(suffix):\n            continue\n        base = word[:-len(suffix)]\n        if not word.endswith("eed") and len(base) >= 3 and re.search("[aeiouy]", base):')
fast_terms=definition['_terms'];start=fast_terms.index('    normalized = re.sub(');end=fast_terms.index('    words = ',start)
fast_terms=fast_terms[:start]+"    if \"'\" in normalized:\n"+''.join('    '+line+'\n' for line in fast_terms[start:end].splitlines())+fast_terms[end:]
namespace=dict(cognition.__dict__);exec(compile(fast_stem+'\n'+fast_terms,'<lexical-prototype>','exec'),namespace)
prototype_terms,prototype_stem=namespace['_terms'],namespace['_stem']
scorer_source=(repo/'src/membrain/lexical_candidates.py').read_text()
prototype_scorer_source=scorer_source.replace('for present, part in zip(document, terms, strict=True):\n                        present.update(part)','for present, part, query_part in zip(document, terms, self.query_terms, strict=True):\n                        present.update(part & query_part)')
prototype_scorer_source=prototype_scorer_source.replace('Counter(term for document in documents for term in document[index])','Counter(term for document in documents for term in self.query_terms[index] if term in document[index])')
scorer_namespace={'__package__':'membrain'};exec(compile(prototype_scorer_source,'<lexical-scorer-prototype>','exec'),scorer_namespace)
PrototypeScorer=scorer_namespace['LexicalScorer']
(root/'prototype-terms.py').write_text(fast_stem+'\n\n'+fast_terms+'\n')
(root/'prototype-scorer.py').write_text(prototype_scorer_source)
started=False
try:
 embedded_database.start(profile);started=True
 database=Database(profile.database_url)
 principal=Principal(profile.tenant_id,profile.principal_id)
 query='What is the appointment for project0000?'
 with database.transaction(principal) as conn:
  memories=[r['document'] for r in conn.execute('SELECT document FROM memory_assertions WHERE brain_id=%s AND tenant_id=%s AND owner_id=%s AND is_current AND NOT deleted AND document IS NOT NULL ORDER BY id LIMIT 252',(host.user_brain_id('bench-user-0'),profile.tenant_id,profile.principal_id)).fetchall()]
 assert len(memories)==252
 database.close()
 words=['running','agreed','speed','seed','need','hoped','runs','ran','will','not','Project123','’','won\'t','can\'t','shan\'t','isn\'t','I\'m','she\'ll','they\'ve','他说','備考安静','ＡＢＣ','ﬃ','2.5','🧠','cafe\u0301']
 rng=random.Random(10813)
 examples=[m['statement'] for m in memories]+words+[' '.join(rng.choices(words,k=rng.randint(0,20))) for _ in range(5000)]
 assert all(original_stem(word)==prototype_stem(word) for word in words)
 assert all(original_terms(text)==prototype_terms(text) for text in examples)
 expected=lexical_candidates.LexicalScorer.from_memories(query,memories)
 expected_scores=[expected(query,m['statement']) for m in memories]
 for arm,enabled in enumerate((False,True,True,False)):
  cognition._terms=prototype_terms if enabled else original_terms
  cognition._stem=prototype_stem if enabled else original_stem
  scorer_class=PrototypeScorer if enabled else lexical_candidates.LexicalScorer
  timings=[]
  for iteration in range(50):
   began=time.process_time_ns();scorer=scorer_class.from_memories(query,memories)
   scores=[scorer(query,m['statement']) for m in memories]
   timings.append((time.process_time_ns()-began)/1e6)
   assert scorer.weights==expected.weights and scores==expected_scores
  report['arms'].append({'index':arm,'prototype':enabled,'iterations':50,'median_cpu_ms':statistics.median(timings),'weights_and_scores_exact':True})
 report.update(completed=True,token_equivalence_examples=len(examples),memory_count=len(memories),fixture_sha256=hashlib.sha256(json.dumps(memories,sort_keys=True).encode()).hexdigest())
finally:
 cognition._terms,cognition._stem=original_terms,original_stem
 if started:embedded_database.stop(profile)
 report['ports_closed']=True
 for port in (profile.database_port,profile.api_port):
  with socket.socket() as connection:report['ports_closed'] &= connection.connect_ex(('127.0.0.1',port)) != 0
 (root/'lexical-probe.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['completed'] and report['ports_closed']
print(json.dumps(report))
