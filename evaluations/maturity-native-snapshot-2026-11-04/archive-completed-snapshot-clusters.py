import hashlib,json,os,shutil,socket,stat,tarfile
from pathlib import Path
root=Path(__file__).parent
assert json.loads((root/'local-legacy-check/result.json').read_text())['ports_closed']
assert json.loads((root/'wheel-check/result.json').read_text())['ports_closed']
profile=json.loads((root/'local-legacy-check/profile/profile.json').read_text());ports=[profile['api_port'],profile['database_port']]
def closed(port):
 with socket.socket() as connection:
  connection.settimeout(.2);return connection.connect_ex(('127.0.0.1',port))!=0
assert all(closed(port) for port in ports)
folders=[root/name for name in ('local-legacy-check/profile/postgres','local-legacy-check/profile/snapshot-restored','wheel-check/staged')]
files={};directories=set()
for folder in folders:
 assert folder.stat().st_uid==os.getuid() and not (folder/'postmaster.pid').exists()
 for path in (folder,*folder.rglob('*')):
  assert not path.is_symlink() and path.stat().st_uid==os.getuid()
  name=path.relative_to(root).as_posix();metadata=path.stat()
  if path.is_file():
   assert metadata.st_nlink==1
   with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
   files[name]={'sha256':sha,'bytes':metadata.st_size,'mode':stat.S_IMODE(metadata.st_mode),'uid':metadata.st_uid,'gid':metadata.st_gid}
  else:assert path.is_dir();directories.add(name)
archive=root/'completed-snapshot-clusters.tar.gz';descriptor=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(descriptor,'wb') as output:
 with tarfile.open(fileobj=output,mode='w:gz') as saved:
  for folder in folders:saved.add(folder,arcname=folder.relative_to(root).as_posix())
 output.flush();os.fsync(output.fileno())
verified={};saved_directories=set()
with tarfile.open(archive,'r|gz') as saved:
 for member in saved:
  if member.isfile():
   assert member.name not in verified
   with saved.extractfile(member) as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
   verified[member.name]={'sha256':sha,'bytes':member.size,'mode':member.mode,'uid':member.uid,'gid':member.gid}
  else:assert member.isdir();saved_directories.add(member.name)
assert verified==files and saved_directories==directories
assert all(closed(port) for port in ports)
for folder in folders:
 assert not (folder/'postmaster.pid').exists()
 for path in folder.rglob('*'):
  if path.is_file():
   with path.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==files[path.relative_to(root).as_posix()]['sha256']
for folder in folders:shutil.rmtree(folder)
with archive.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
report={'owned_completed_clusters':len(folders),'regular_files_verified':len(files),'directories_verified':len(directories),'original_regular_bytes':sum(r['bytes'] for r in files.values()),'archive_bytes':archive.stat().st_size,'archive_sha256':sha,'private_mode':oct(archive.stat().st_mode&0o777),'ports_closed':True,'only_generated_pgdata_removed':True,'all_profiles_receipts_logs_packages_models_binaries_and_native_snapshot_zip_preserved':True}
(root/'completed-snapshot-clusters-archive.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
