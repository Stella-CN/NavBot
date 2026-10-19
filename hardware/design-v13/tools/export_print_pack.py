"""Export the ten V13 printed solids; rigid translation only, no geometry edits."""
from pathlib import Path
import csv,json,hashlib
import FreeCAD as A
import Part,Mesh,MeshPart
O=Path(__file__).resolve().parent.parent
P=O/'NavBot-V13-Print-Pack'
for folder in ['STL','STEP','参考图']: (P/folder).mkdir(parents=True,exist_ok=True)
d=A.openDocument(str(O/'NavBot-V13.FCStd'))
items=list(csv.DictReader((O/'打印件清单.csv').open(encoding='utf-8-sig')))
actual={o.Name for o in d.Objects if 'Role' in o.PropertiesList and o.Role=='printed'}
assert actual=={row['CAD对象'] for row in items}
rows=[]
for row in items:
 name=row['CAD对象'];s=d.getObject(name).Shape.copy()
 assert s.isValid() and len(s.Solids)==1,name
 prototype=MeshPart.meshFromShape(Shape=s,LinearDeflection=.08,AngularDeflection=.15,Relative=False)
 prototype.write(str(O/'prototype-stl'/(name+'.stl')))
 b=s.optimalBoundingBox(False)
 shift=[-(b.XMin+b.XMax)/2,-(b.YMin+b.YMax)/2,-b.ZMin]
 s.translate(A.Vector(*shift))
 stem=row['编号']+'_'+name
 s.exportStep(str(P/'STEP'/(stem+'.step')))
 mesh=MeshPart.meshFromShape(Shape=s,LinearDeflection=.08,AngularDeflection=.15,Relative=False)
 mesh.write(str(P/'STL'/(stem+'.stl')))
 check=Mesh.Mesh(str(P/'STL'/(stem+'.stl')))
 result=dict(number=row['编号'],name=row['名称'],object=name,quantity=1,
  dimensions_mm=[b.XLength,b.YLength,b.ZLength],translation_mm=shift,
  cad_valid=True,solids=1,mesh_closed=check.isSolid(),triangles=check.CountFacets,
  stl='STL/'+stem+'.stl',step='STEP/'+stem+'.step',
  cad_volume_mm3=s.Volume,mesh_volume_mm3=check.Volume)
 assert result['mesh_closed'],(name,'mesh not closed')
 rows.append(result);print(row['编号'],name,'closed',result['triangles'],flush=True)
(P/'导出校核.json').write_text(json.dumps(dict(source='NavBot-V13.FCStd',units='mm',linear_deflection_mm=.08,angular_deflection_radians=.15,parts=rows),ensure_ascii=False,indent=2))
with (P/'零件清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['编号','名称','数量','X尺寸mm','Y尺寸mm','Z尺寸mm','材料','STL文件','STEP文件','闭合网格'])
 for q in rows:w.writerow([q['number'],q['name'],1,*[round(x,2) for x in q['dimensions_mm']],'PETG',q['stl'],q['step'],q['mesh_closed']])
print('EXPORT COMPLETE',flush=True)
