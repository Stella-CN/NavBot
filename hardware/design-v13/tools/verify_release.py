"""Read-only FreeCAD/mesh validation of the standalone V13 baseline."""
from pathlib import Path
import csv,json,hashlib
import FreeCAD as A,Part,Mesh
O=Path(__file__).resolve().parent.parent;P=O/'NavBot-V13-Print-Pack'
d=A.openDocument(str(O/'NavBot-V13.FCStd'))
external=[]
for o in d.Objects:
 for prop in o.PropertiesList:
  if 'XLink' in o.getTypeIdOfProperty(prop) and getattr(o,prop,None):external.append([o.Name,prop])
assert not external,external
rows=list(csv.DictReader((O/'打印件清单.csv').open(encoding='utf-8-sig')))
printed={o.Name for o in d.Objects if hasattr(o,'Role') and o.Role=='printed'}
assert printed=={r['CAD对象'] for r in rows} and len(rows)==10
checks=[]
for row in rows:
 name=row['CAD对象'];s=d.getObject(name).Shape;b=s.optimalBoundingBox(False)
 assert s.isValid() and len(s.Solids)==1,name
 stem=row['编号']+'_'+name
 proto=Mesh.Mesh(str(O/'prototype-stl'/(name+'.stl')))
 mesh=Mesh.Mesh(str(P/'STL'/(stem+'.stl')))
 step=Part.Shape();step.read(str(P/'STEP'/(stem+'.step')))
 assert proto.isSolid() and mesh.isSolid() and step.isValid(),name
 translated=s.copy();translated.translate(A.Vector(-(b.XMin+b.XMax)/2,-(b.YMin+b.YMax)/2,-b.ZMin))
 step_error=abs(step.Volume-translated.Volume)/translated.Volume
 print(name,'STEP relative volume error',step_error,flush=True)
 # Curved STEP faces can change numerical volume integration after round-trip.
 difference=0.0
 if step_error>=1e-6:
  removed=translated.cut(step);added=step.cut(translated)
  assert removed.isValid() and added.isValid(),name
  difference=abs(removed.Volume)+abs(added.Volume)
  assert difference<.05,(name,'STEP geometric difference',difference)
 assert abs(abs(mesh.Volume)-s.Volume)/s.Volume<.01,name
 assert abs(abs(proto.Volume)-s.Volume)/s.Volume<.01,name
 pb=proto.BoundBox
 assert max(abs(getattr(b,k)-getattr(pb,k)) for k in ['XMin','XMax','YMin','YMax','ZMin','ZMax'])<.15,name
 checks.append(dict(object=name,valid_solid=True,stl_closed=True,step_relative_volume_error=step_error,step_symmetric_difference_mm3=difference))
report=dict(baseline='NavBot-V13.FCStd',sha256=hashlib.sha256((O/'NavBot-V13.FCStd').read_bytes()).hexdigest(),external_links=external,parts=checks,note='文件完整性与导出一致性复核；保留的干涉/拆装报告是冻结设计的既有校核记录。')
(P/'基准文件校核.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('PASS: standalone FCStd; 10 CAD solids / prototype STL / print STL / STEP verified',flush=True)
A.closeDocument(d.Name)
