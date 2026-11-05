import hashlib,io,json,tarfile,urllib.request,zipfile
from pathlib import Path
root=Path(__file__).parent
report={'purpose':'read-only inspection of published native engine wheel contents, without importing or running supplier code','candidates':[]}
for project,version in [('postgresql-binaries','16.15.0'),('embedded-postgres','18.6.3')]:
 with urllib.request.urlopen(f'https://pypi.org/pypi/{project}/{version}/json',timeout=60) as response:meta=json.load(response)
 candidates=meta['urls'];entry=next(x for x in candidates if 'macosx_11_0_arm64' in x['filename'])
 path=root/entry['filename']
 with urllib.request.urlopen(entry['url'],timeout=60) as response:data=response.read()
 assert hashlib.sha256(data).hexdigest()==entry['digests']['sha256'];path.write_bytes(data)
 row={'project':project,'version':version,'requires_python':meta['info']['requires_python'],'requires_dist':meta['info']['requires_dist'],'project_urls':meta['info']['project_urls'],'all_wheels':[{'filename':x['filename'],'bytes':x['size'],'sha256':x['digests']['sha256']} for x in candidates],'inspected_wheel':entry['filename'],'wheel_sha256':entry['digests']['sha256'],'wheel_hash_matches_pypi':True,'code_executed':False}
 with zipfile.ZipFile(io.BytesIO(data)) as saved:
  names=saved.namelist();row['wheel_members']=len(names)
  row['initializers']={name:saved.read(name).decode() for name in names if name.endswith('__init__.py') and len(saved.read(name))<10000}
  members=list(names)
  for name in names:
   if name.endswith('.tar.gz'):
    with tarfile.open(fileobj=io.BytesIO(saved.read(name)),mode='r:gz') as archive:members.extend(m.name for m in archive)
  row['vector_assets']=[name for name in members if 'vector' in name.lower() and ('extension/' in name or name.endswith(('.so','.dylib','.dll')))]
  row['upgrade_tools']=[name for name in members if name.endswith(('/pg_upgrade','/pg_upgrade.exe'))]
  row['catalog_fix_scripts']=[name for name in members if 'fix-CVE' in name]
  row['headers_present']=any('/include/postgresql/server/' in name for name in members)
  (root/(project+'-members.json')).write_text(json.dumps(members,indent=2)+'\n')
 report['candidates'].append(row)
(root/'wheel-inspection.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'purpose':report['purpose'],'candidates':[{k:c[k] for k in ('project','version','wheel_hash_matches_pypi','code_executed','vector_assets','upgrade_tools','catalog_fix_scripts','headers_present')} for c in report['candidates']]}))
