import hashlib,io,json,os,shutil,subprocess,tarfile,zipfile
from pathlib import Path
from membrain import embedded_database

root=Path(__file__).parent
wheel=root/'postgresql_binaries-16.15.0-py3-none-macosx_11_0_arm64.whl'
assert hashlib.sha256(wheel.read_bytes()).hexdigest()=='c73c7eacd71da727085aa3a4ebfa60b862ce8eacb72102df691b620d7a66460b'
target=root/'composed';target.mkdir(exist_ok=False)
with zipfile.ZipFile(wheel) as saved:
 name=next(n for n in saved.namelist() if n.endswith('.tar.gz'))
 data=saved.read(name)
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:archive.extractall(target,filter='data')
prefix=target/'postgresql-16.15.0-aarch64-apple-darwin'
environment={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','LC_ALL':'C','HOME':str(root)}
def config(option):
 result=subprocess.check_output([prefix/'bin/pg_config',option],text=True,env=environment).strip()
 path=Path(result);assert path.resolve().is_relative_to(prefix.resolve()),result
 return path
lib,share=config('--pkglibdir'),config('--sharedir')
legacy=embedded_database._installation();assert legacy is not None
extensions=list(legacy.glob('share/**/extension/vector*'))
libraries=[p for p in legacy.rglob('vector.*') if p.suffix in {'.dylib','.so','.dll'}]
assert len(libraries)==1 and extensions
copied=[]
for source,dest in [(libraries[0],lib/libraries[0].name)]+[(p,share/'extension'/p.name) for p in extensions if p.is_file()]:
 assert not dest.exists();dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
 copied.append({'path':str(dest.relative_to(prefix)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
versions={name:subprocess.check_output([prefix/'bin'/name,'--version'],text=True,env=environment).strip() for name in ('postgres','pg_ctl','initdb','pg_dump','pg_restore','psql','pg_config')}
assert all('16.15' in value for value in versions.values())
deps=subprocess.check_output(['otool','-L',str(lib/libraries[0].name)],text=True,env=environment)
report={'purpose':'isolated same-major public binary supplier with legacy vector resources only; no default integration','postgres_wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'inner_archive_sha256':hashlib.sha256(data).hexdigest(),'prefix':str(prefix),'vector_source':'pgserver 0.1.4 resources only, no legacy server/client executables copied','resource_files':copied,'tools':versions,'vector_dependencies':deps,'supplier_python_imported':False,'completed':True}
(root/'composed-prefix.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='resource_files'}))
