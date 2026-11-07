import base64
import csv
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

root=Path(__file__).parent
spec=importlib.util.spec_from_file_location('engine_builder','/Users/yichen/tmp/membrain-review-20261029/scripts/build_embedded_postgres.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
checks=[]
with tempfile.TemporaryDirectory(prefix='guards-',dir=root) as directory:
 base=Path(directory)
 def archive(name,link=None):
  output=io.BytesIO()
  with tarfile.open(fileobj=output,mode='w') as saved:
   entry=tarfile.TarInfo(name)
   if link:
    entry.type=tarfile.SYMTYPE;entry.linkname=link
    saved.addfile(entry)
   else:
    entry.size=4;saved.addfile(entry,io.BytesIO(b'test'))
  return output.getvalue()
 for label,data,digest,error in [('checksum',archive('ok'),'0'*64,ValueError),('traversal',archive('../escape'),None,tarfile.OutsideDestinationError),('symlink',archive('link','../escape'),None,tarfile.LinkOutsideDestinationError)]:
  target=base/label;target.mkdir()
  digest=digest or hashlib.sha256(data).hexdigest()
  with patch.object(builder.urllib.request,'urlopen',return_value=io.BytesIO(data)):
   try:builder.extract('https://example.invalid/fixed-test',digest,target/'archive.tar',target/'extract')
   except error:pass
   else:raise AssertionError(label+' was accepted')
  assert not (base/'escape').exists() and not (target/'escape').exists()
  if label=='checksum':assert not (target/'extract').exists()
  checks.append(label)
 occupied=base/'occupied';occupied.mkdir();(occupied/'sentinel').write_text('retain')
 try:builder.build(occupied,base/'output',1)
 except FileExistsError:pass
 else:raise AssertionError('Existing build directory was accepted')
 assert (occupied/'sentinel').read_text()=='retain';checks.append('existing_directory_retained')
 with patch.object(builder.platform,'system',return_value='Linux'):
  try:builder.build(base/'unsupported',base/'output',1)
  except ValueError:pass
  else:raise AssertionError('Unsupported platform was accepted')
 assert not (base/'unsupported').exists();checks.append('unsupported_platform_no_write')
wheel=root/'wheels/membrain_postgres-16.15.0-py3-none-macosx_15_0_arm64.whl'
with zipfile.ZipFile(wheel) as packed:
 info='membrain_postgres-16.15.0.dist-info'
 record=list(csv.reader(io.StringIO(packed.read(info+'/RECORD').decode())))
 names=set()
 for name,digest,size in record:
  assert name not in names;names.add(name)
  if name==info+'/RECORD':assert not digest and not size;continue
  data=packed.read(name)
  assert len(data)==int(size)
  assert digest=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
 assert names==set(packed.namelist())
 checks.append('all_wheel_record_hashes_and_members')
report={'completed':True,'checks':checks,'passed':len(checks),'failed':0,'wheel_record_members':len(names),'no_models':True}
(root/'builder-guards.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
