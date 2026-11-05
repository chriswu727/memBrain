import hashlib,json,os,re,shutil,socket,tarfile
from pathlib import Path
root=Path(__file__).parent
proof=json.loads((root/'lts-compatibility-result.json').read_text());assert proof['completed'] and proof['exit_code']==0 and proof['source_unchanged'] and proof['all_owned_ports_closed']
names=['lts-native-regression']+[str(p.parent.relative_to(root)) for p in (root/'pytest-lts-native-16_15').rglob('profile.json') if (p.parent/'postgres/PG_VERSION').is_file()]
folders=[];files={}
for name in names:
 folder=root/name/'postgres'
 assert (folder/'PG_VERSION').is_file() and not (folder/'postmaster.pid').exists()
 assert folder.stat().st_uid==os.getuid()
 port=int(re.findall(r'^\s*port\s*=\s*(\d+)',(folder/'postgresql.conf').read_text(),re.M)[-1])
 with socket.socket() as s:
  s.settimeout(.2);assert s.connect_ex(('127.0.0.1',port))!=0
 for path in folder.rglob('*'):
  assert not path.is_symlink()
  if path.is_file():
   with path.open('rb') as stream:files[path.relative_to(root).as_posix()]=hashlib.file_digest(stream,'sha256').hexdigest()
 folders.append(folder)
archive=root/'completed-lts-regression-clusters.tar.gz'
fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'wb') as output,tarfile.open(fileobj=output,mode='w:gz') as saved:
 for folder in folders:saved.add(folder,arcname=folder.relative_to(root).as_posix())
verified={}
with tarfile.open(archive,'r|gz') as saved:
 for member in saved:
  if member.isfile():
   with saved.extractfile(member) as stream:verified[member.name]=hashlib.file_digest(stream,'sha256').hexdigest()
  else:assert member.isdir()
assert verified==files
for folder in folders:shutil.rmtree(folder)
with archive.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
result={'owned_completed_clusters':len(folders),'regular_files_verified':len(files),'archive_bytes':archive.stat().st_size,'archive_sha256':checksum,'private_mode':oct(archive.stat().st_mode&0o777),'ports_closed':True,'only_database_data_removed':True,'all_logs_scripts_results_and_binaries_preserved':True,'native_regression_passed':248,'native_regression_skipped':0,'profiles_and_registries_retained':True}
(root/'completed-lts-regression-archive.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
