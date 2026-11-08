import hashlib,json,subprocess,zipfile
from pathlib import Path,PurePosixPath
from collections import Counter
root=Path('/private/tmp/membrain-recording-fence-native-audit');root.mkdir(exist_ok=True)
meta=json.loads(subprocess.check_output(['gh','api','repos/chriswu727/memBrain/actions/runs/42459291814/artifacts']))
assert len(meta['artifacts'])==5
(root/'artifact-metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
receipts=[]
for item in meta['artifacts']:
    assert not item['expired']
    assert item['workflow_run']['head_sha']=='72d960c3338eecb1a31620b8f212442a4c2ad7d8'
    archive=root/'download.zip'
    with archive.open('wb') as out:
        subprocess.run(['gh','api',f"repos/chriswu727/memBrain/actions/artifacts/{item['id']}/zip"],stdout=out,check=True)
    receipt={'artifact_id':item['id'],'name':item['name'],'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'retained':[]}
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            name=PurePosixPath(member.filename)
            assert not name.is_absolute() and '..' not in name.parts
            if name.suffix!='.json':continue
            assert member.file_size<2_000_000
            content=bundle.read(member);json.loads(content)
            destination=root/'artifacts'/item['name']/str(name)
            destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
            receipt['retained'].append({'path':str(destination.relative_to(root)),'sha256':hashlib.sha256(content).hexdigest()})
    archive.unlink();receipts.append(receipt)
(root/'artifact-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
summary=[];duplicates=0
for p in sorted((root/'artifacts').rglob('*.json')):
    data=json.loads(p.read_text())
    if not isinstance(data,dict) or 'completed' not in data:continue
    if p.name=='qualification.json' and p.parent.name=='native-artifacts':
        canonical=list(p.parent.parent.glob('native-check-*/qualification.json'))
        assert len(canonical)==1 and p.read_bytes()==canonical[0].read_bytes()
        duplicates+=1;continue
    if 'worker-result' in p.name:continue
    assert '42459291814' in str(p.relative_to(root/'artifacts'))
    ports={}
    def visit(value,prefix=''):
        if isinstance(value,dict):
            for key,item in value.items():
                name=prefix+key
                if 'port' in key and 'closed' in key and isinstance(item,bool):ports[name]=item
                visit(item,name+'.')
        elif isinstance(value,list):
            for index,item in enumerate(value):visit(item,prefix+str(index)+'.')
    visit(data)
    assert data['completed'] is True and data.get('model_calls')==0 and all(ports.values()),p
    summary.append({'path':str(p.relative_to(root/'artifacts')),'completed':True,'model_calls':0,'ports':ports})
result={'run_id':42459291814,'source_commit':'72d960c3338eecb1a31620b8f212442a4c2ad7d8','count':len(summary),'by_platform':dict(Counter(x['path'].split('/')[0] for x in summary)),'duplicate_qualification_copies_excluded':duplicates,'all_completed':True,'all_model_calls_zero':True,'all_recorded_port_closures_passed':True,'summaries':summary}
assert len(summary)==47 and duplicates==5
(root/'native-summary-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='summaries'}))
