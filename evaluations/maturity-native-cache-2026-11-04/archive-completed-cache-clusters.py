import hashlib,json,os,re,shutil,socket,tarfile
from pathlib import Path
root=Path(__file__).parent
names=('installed-supplier-diagnostic','installed-supplier-dump-check','wheel-installed-check','acl-cold-install-check')
folders=[];files={};directories=set();ports=set()
def closed(port):
 with socket.socket() as connection:
  connection.settimeout(.2);return connection.connect_ex(('127.0.0.1',port))!=0
for name in names:
 folder=root/name/'profile/postgres'; report=json.loads((root/name/'result.json').read_text())
 assert report['ports_closed'] and not (folder/'postmaster.pid').exists()
 assert folder.stat().st_uid==os.getuid()
 port=int(re.findall(r'^\s*port\s*=\s*(\d+)',(folder/'postgresql.conf').read_text(),re.M)[-1]);assert closed(port);ports.add(port)
 for path in (folder,*folder.rglob('*')):
  assert not path.is_symlink() and path.stat().st_uid==os.getuid()
  name=path.relative_to(root).as_posix()
  if path.is_file():
   assert path.stat().st_nlink==1
   with path.open('rb') as stream:files[name]=hashlib.file_digest(stream,'sha256').hexdigest()
  else:assert path.is_dir();directories.add(name)
 folders.append(folder)
archive=root/'completed-cache-clusters.tar.gz'
descriptor=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(descriptor,'wb') as output:
 with tarfile.open(fileobj=output,mode='w:gz') as saved:
  for folder in folders:saved.add(folder,arcname=folder.relative_to(root).as_posix())
 output.flush();os.fsync(output.fileno())
verified={};saved_directories=set()
with tarfile.open(archive,'r|gz') as saved:
 for member in saved:
  if member.isfile():
   assert member.name not in verified
   with saved.extractfile(member) as stream:verified[member.name]=hashlib.file_digest(stream,'sha256').hexdigest()
  else:assert member.isdir();saved_directories.add(member.name)
assert verified==files and saved_directories==directories
assert all(closed(port) for port in ports)
for folder in folders:
 assert not (folder/'postmaster.pid').exists()
 for path in folder.rglob('*'):
  if path.is_file():
   with path.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==files[path.relative_to(root).as_posix()]
for folder in folders:shutil.rmtree(folder)
with archive.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
result={'owned_completed_clusters':len(folders),'regular_files_verified':len(files),'directories_verified':len(directories),'archive_bytes':archive.stat().st_size,'archive_sha256':checksum,'private_mode':oct(archive.stat().st_mode&0o777),'ports_closed':True,'only_database_data_removed':True,'all_profiles_registries_logs_scripts_results_binaries_and_packages_preserved':True,'contains_failed_client_version_probe':True,'production_backup_or_rollback_claimed':False}
(root/'completed-cache-clusters-archive.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
