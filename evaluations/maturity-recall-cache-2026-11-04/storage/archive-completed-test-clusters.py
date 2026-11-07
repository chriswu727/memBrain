import hashlib,json,os,shutil,socket,tarfile
from pathlib import Path
from membrain.local_profile import load_profile
root=Path(__file__).parent
for name in ('compatibility-result.json','installed-compatibility-result.json'):
 report=json.loads((root/name).read_text());assert report['completed'] and report['exit_code']==0 and report['all_owned_ports_closed']
profiles=[];roots=set()
for name in ('pytest-native-16_15','pytest-installed-16_15'):
 for path in (root/name).rglob('profile.json'):
  data=path.parent/'postgres'
  if not (data/'PG_VERSION').is_file():continue
  profile=load_profile(path.parent);assert not (data/'postmaster.pid').exists()
  for port in (profile.database_port,profile.api_port):
   with socket.socket() as s:s.settimeout(.2);assert s.connect_ex(('127.0.0.1',port))!=0
  registry=profile.settings().recovery_registry_path
  roots.add(profile.directory)
  if registry:assert Path(registry).is_relative_to(root);roots.add(Path(registry))
  profiles.append(profile.directory)
assert profiles
files={}
for folder in roots:
 for path in folder.rglob('*'):
  assert not path.is_symlink() and (path.is_file() or path.is_dir())
  if path.is_file():
   with path.open('rb') as stream:files[str(path.relative_to(root))]=hashlib.file_digest(stream,'sha256').hexdigest()
archive=root/'completed-native-test-clusters.tar.gz';fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'wb') as output,tarfile.open(fileobj=output,mode='w:gz',compresslevel=6) as saved:
 for folder in sorted(roots):saved.add(folder,arcname=str(folder.relative_to(root)))
verified={}
with tarfile.open(archive,'r|gz') as saved:
 for member in saved:
  if member.isfile():
   with saved.extractfile(member) as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
  elif member.islnk():digest=verified[member.linkname]
  else:assert member.isdir();continue
  assert digest==files[member.name];verified[member.name]=digest
assert verified==files
inventory=root/'completed-test-files.private.json';inventory.write_text(json.dumps(files,indent=2)+'\n');inventory.chmod(0o600)
for directory in profiles:shutil.rmtree(directory/'postgres')
report={'purpose':'archive and verify only completed owned synthetic native test clusters before removing their data directories to make room for fresh qualification','profiles':len(profiles),'regular_files_verified':len(files),'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest(),'ports_closed':True,'only_owned_database_directories_removed':True,'profiles_and_registries_preserved':True,'archives_and_inventory_private':True,'never_commit_archive_or_profiles':True}
(root/'completed-test-cluster-archive.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
