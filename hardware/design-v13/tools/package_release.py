"""Refresh checksums and the print ZIP from the frozen V13 engineering files."""
from pathlib import Path
import hashlib,json,zipfile
O=Path(__file__).resolve().parent.parent;P=O/'NavBot-V13-Print-Pack'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
check=json.loads((P/'基准文件校核.json').read_text())
assert check['sha256']==sha(O/'NavBot-V13.FCStd'),'Run verify_release.py after changing CAD'
assert len(check['parts'])==10 and not check['external_links']
for folder,suffix in [('STL','*.stl'),('STEP','*.step')]:assert len(list((P/folder).glob(suffix)))==10
files=sorted(p for p in P.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt')
(P/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+str(p.relative_to(P))+'\n' for p in files))
with zipfile.ZipFile(O/'NavBot-V13-Print-Pack.zip','w',zipfile.ZIP_DEFLATED,6) as z:
 for p in sorted(P.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(O)))
with zipfile.ZipFile(O/'NavBot-V13-Print-Pack.zip') as z:assert z.testzip() is None
files=sorted(p for p in O.rglob('*') if p.is_file() and p.name not in ['工程SHA256SUMS.txt','.DS_Store'] and '__pycache__' not in p.parts)
(O/'工程SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+str(p.relative_to(O))+'\n' for p in files))
print('Print ZIP and engineering checksums refreshed')
