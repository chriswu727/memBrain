import hashlib,json,os,re,shutil,socket,tarfile
from pathlib import Path
root=Path(__file__).parent
names=('vector-portable-check','vector-planner-check','vector-planner-check-v2')
folders=[];files={}
for name in names:
 folder=root/name/'data'
 report=json.loads((root/name/'qualification.json').read_text())
 assert report['port_closed'] and not (folder/'postmaster.pid').exists()
 assert folder.stat().st_uid==os.getuid()
 port=int(re.findall(r'^\s*port\s*=\s*(\d+)',(folder/'postgresql.conf').read_text(),re.M)[-1])
 with socket.socket() as s:
  s.settimeout(.2);assert s.connect_ex(('127.0.0.1',port))!=0
 for path in folder.rglob('*'):
  assert not path.is_symlink()
  if path.is_file():
   with path.open('rb') as stream:files[path.relative_to(root).as_posix()]=hashlib.file_digest(stream,'sha256').hexdigest()
 folders.append(folder)
archive=root/'completed-vector-probe-clusters.tar.gz'
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
result={'owned_completed_clusters':len(folders),'regular_files_verified':len(files),'archive_bytes':archive.stat().st_size,'archive_sha256':checksum,'private_mode':oct(archive.stat().st_mode&0o777),'ports_closed':True,'only_database_data_removed':True,'all_logs_scripts_results_and_binaries_preserved':True,'contains_failed_planner_attempt':True}
(root/'completed-vector-probe-archive.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
