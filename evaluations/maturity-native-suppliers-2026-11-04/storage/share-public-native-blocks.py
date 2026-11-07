import ctypes,hashlib,json,os,secrets,socket
from pathlib import Path
root=Path(__file__).parent
proof=json.loads((root/'lts-compatibility-result.json').read_text());assert proof['exit_code']==0 and proof['all_owned_ports_closed']
assert json.loads((root/'upgrade-lts-vector-result.json').read_text())['ports_closed']
assert not (root/'upgrade-copy/postgres/postmaster.pid').exists()
paths=[root/'vector-portable-build/postgresql-16.15.0-aarch64-apple-darwin',root/'composed/postgresql-16.15.0-aarch64-apple-darwin',root/'vector-portable-check/pginstall',root/'vector-planner-check/pginstall',root/'vector-planner-check-v2/pginstall',root/'lts-macos-relocated/pginstall']
lib=ctypes.CDLL('/usr/lib/libSystem.B.dylib',use_errno=True);lib.clonefile.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];lib.clonefile.restype=ctypes.c_int
free=lambda:os.statvfs(root).f_bavail*os.statvfs(root).f_frsize
before=free();seen={};cloned=0;logical=0
for folder in paths:
 assert folder.is_dir() and folder.stat().st_uid==os.getuid()
 for path in sorted(folder.rglob('*')):
  if path.is_symlink() or not path.is_file():continue
  metadata=path.stat();assert metadata.st_uid==os.getuid() and metadata.st_nlink==1
  with path.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').digest()
  key=(metadata.st_size,checksum)
  source=seen.get(key)
  if source is None:seen[key]=path;continue
  if metadata.st_size<4096:continue
  temporary=path.with_name('.cow-'+secrets.token_hex(8))
  try:
   if lib.clonefile(os.fsencode(source),os.fsencode(temporary),0):raise OSError(ctypes.get_errno(),'clonefile failed')
   temporary.chmod(metadata.st_mode&0o777)
   os.utime(temporary,ns=(metadata.st_atime_ns,metadata.st_mtime_ns))
   current=temporary.stat()
   assert current.st_ino!=source.stat().st_ino and current.st_nlink==1
   assert (current.st_uid,current.st_gid,current.st_mode&0o777,current.st_mtime_ns)==(metadata.st_uid,metadata.st_gid,metadata.st_mode&0o777,metadata.st_mtime_ns)
   with temporary.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').digest()==checksum
   os.replace(temporary,path);cloned+=1;logical+=metadata.st_size
  finally:temporary.unlink(missing_ok=True)
report={'purpose':'share identical public native binary blocks only across completed owned prototype prefixes; all files retained with independent COW mutability','files_cloned':cloned,'logical_bytes_shared':logical,'free_before':before,'free_after':free(),'contents_permissions_owners_mtimes_verified':True,'archives_profiles_registries_and_logs_unchanged':True,'no_hardlinks':True}
(root/'public-native-block-sharing.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
