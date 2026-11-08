import hashlib,json,subprocess,zipfile
from pathlib import Path,PurePosixPath
from collections import Counter
root=Path('/private/tmp/membrain-lexical-native-audit');root.mkdir(exist_ok=True)
head='8421b0bfd5cc0a6ac24a93e968ffee072109f6f5'
selection={42464847388:['native-linux-aarch64','native-linux-x86_64','native-macos-arm64'],42465201213:['native-macos-x86_64'],42465082081:['native-windows-x86_64']}
receipts=[]
for run,names in selection.items():
 meta=json.loads(subprocess.check_output(['gh','api',f'repos/chriswu727/memBrain/actions/runs/{run}/artifacts']))
 (root/f'artifact-metadata-{run}.json').write_text(json.dumps(meta,indent=2)+'\n')
 available={x['name']:x for x in meta['artifacts']}
 for name in names:
  if name not in available:continue
  item=available[name];assert not item['expired'] and item['workflow_run']['head_sha']==head
  saved=root/f'receipt-{item["id"]}.json'
  if saved.exists():receipts.append(json.loads(saved.read_text()));continue
  archive=root/'download.zip'
  with archive.open('wb') as out:subprocess.run(['gh','api',f'repos/chriswu727/memBrain/actions/artifacts/{item["id"]}/zip'],stdout=out,check=True)
  receipt={'run_id':run,'artifact_id':item['id'],'name':name,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'retained':[]}
  with zipfile.ZipFile(archive) as bundle:
   for member in bundle.infolist():
    path=PurePosixPath(member.filename);assert not path.is_absolute() and '..' not in path.parts
    if path.suffix!='.json':continue
    assert member.file_size<2_000_000
    raw=bundle.read(member);data=json.loads(raw);content=raw.replace(b'\r\n',b'\n');assert json.loads(content)==data
    destination=root/'artifacts'/name/str(path);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
    receipt['retained'].append({'path':str(destination.relative_to(root)),'original_sha256':hashlib.sha256(raw).hexdigest(),'stored_sha256':hashlib.sha256(content).hexdigest(),'line_endings_normalized':raw!=content})
  archive.unlink();saved.write_text(json.dumps(receipt,indent=2)+'\n');receipts.append(receipt)
(root/'artifact-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
summary=[];duplicates=0
for p in sorted((root/'artifacts').rglob('*.json')):
 data=json.loads(p.read_text())
 if not isinstance(data,dict) or 'completed' not in data:continue
 if p.name=='qualification.json' and p.parent.name=='native-artifacts':
  canonical=list(p.parent.parent.glob('native-check-*/qualification.json'))
  assert len(canonical)==1 and p.read_bytes()==canonical[0].read_bytes();duplicates+=1;continue
 if 'worker-result' in p.name:continue
 platform=p.relative_to(root/'artifacts').parts[0]
 run=next(run for run,names in selection.items() if platform in names)
 assert str(run) in str(p.relative_to(root/'artifacts')),p
 ports={}
 def visit(v,prefix=''):
  if isinstance(v,dict):
   for k,item in v.items():
    key=prefix+k
    if 'port' in k and 'closed' in k and isinstance(item,bool):ports[key]=item
    visit(item,key+'.')
  elif isinstance(v,list):
   for index,item in enumerate(v):visit(item,prefix+str(index)+'.')
 visit(data)
 assert data['completed'] is True and data.get('model_calls')==0 and all(ports.values()),p
 summary.append({'path':str(p.relative_to(root/'artifacts')),'run_id':run,'completed':True,'model_calls':0,'ports':ports})
result={'source_commit':head,'selected_runs':selection,'count':len(summary),'by_platform':dict(Counter(x['path'].split('/')[0] for x in summary)),'duplicate_qualification_copies_excluded':duplicates,'all_completed':True,'all_model_calls_zero':True,'all_recorded_port_closures_passed':True,'complete_five_platform_qualification':len(summary)==47 and duplicates==5,'summaries':summary}
(root/'native-summary-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='summaries'}))
