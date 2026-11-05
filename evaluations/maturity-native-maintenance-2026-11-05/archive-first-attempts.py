import hashlib,json,os,shutil,socket,tarfile
from pathlib import Path
root=Path(__file__).parent;names=('local-check','local-check-v2','local-check-v3','local-check-v4');folders=[];records={};directories=set();ports=set()
def closed(port):
 with socket.socket() as s:s.settimeout(.2);return s.connect_ex(('127.0.0.1',port))!=0
for name in names:
 result=json.loads((root/name/'result.json').read_text());assert result['ports_closed'] and not result['completed']
 profile=json.loads((root/name/'profile/profile.json').read_text());ports.update((profile['api_port'],profile['database_port']))
 folder=root/name/'profile/postgres';assert folder.stat().st_uid==os.getuid() and not (folder/'postmaster.pid').exists()
 for path in (folder,*folder.rglob('*')):
  assert not path.is_symlink() and path.stat().st_uid==os.getuid()
  if path.is_file():
   assert path.stat().st_nlink==1
   with path.open('rb') as f:records[path.relative_to(root).as_posix()]=hashlib.file_digest(f,'sha256').hexdigest()
  else:assert path.is_dir();directories.add(path.relative_to(root).as_posix())
 folders.append(folder)
assert all(closed(p) for p in ports)
archive=root/'first-attempt-clusters.tar.gz';fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'wb') as out:
 with tarfile.open(fileobj=out,mode='w:gz') as tar:
  for folder in folders:tar.add(folder,arcname=folder.relative_to(root).as_posix())
 out.flush();os.fsync(out.fileno())
verified={};saved_dirs=set()
with tarfile.open(archive,'r|gz') as tar:
 for member in tar:
  if member.isfile():
   assert member.name not in verified
   with tar.extractfile(member) as f:verified[member.name]=hashlib.file_digest(f,'sha256').hexdigest()
  else:assert member.isdir();saved_dirs.add(member.name)
assert verified==records and saved_dirs==directories and all(closed(p) for p in ports)
for folder in folders:
 assert not (folder/'postmaster.pid').exists()
 for path in folder.rglob('*'):
  if path.is_file():
   with path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==records[path.relative_to(root).as_posix()]
for folder in folders:shutil.rmtree(folder)
with archive.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
report={'terminal_owned_failed_clusters':len(folders),'regular_files_verified':len(records),'directories_verified':len(directories),'archive_bytes':archive.stat().st_size,'archive_sha256':sha,'mode':oct(archive.stat().st_mode&0o777),'ports_closed':True,'only_owned_generated_pgdata_removed':True,'all_profiles_journals_snapshots_logs_packages_models_and_binaries_preserved':True}
(root/'first-attempt-archive.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
