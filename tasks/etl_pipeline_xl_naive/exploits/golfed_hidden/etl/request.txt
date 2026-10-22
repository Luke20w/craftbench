from etl.errors import Z
from etl.steps import Cx,SL,J
import etl.ops
def process(q,run=False):
 isinstance(q,dict)or Z('request must be an object','')
 l=q.get('pipeline');isinstance(l,dict)or Z("'pipeline' must be an object",'pipeline')
 t=l.get('steps');isinstance(t,list)or Z("'steps' must be an array",'pipeline.steps')
 d=q.get('dataset');isinstance(d,list)or Z("'dataset' must be an array",'dataset')
 for i,r in enumerate(d):isinstance(r,dict)or Z('dataset rows must be objects','dataset[%d]'%i)
 s=SL('steps').n(t,'pipeline.steps')
 if not run:return{'status':'ok','normalized':{'steps':J(s)}}
 o=Cx().run(s,[dict(r)for r in d]);return{'status':'ok','data':o,'metrics':{'rows_in':len(d),'rows_out':len(o)}}
