import json
from etl.expr import N,NR
from etl.fields import T,Lb,C,Ls,Rc,CL
from etl.steps import Op
from etl.ops.common import XE
class GC(Op):
 name='group_count';f=CL('by',ne=1),T('as')
 def run(s,t,rows,c):
  g={}
  for r in rows:
   k=json.dumps([r.get(a)for a in t['by']])
   if k not in g:g[k]={a:r.get(a)for a in t['by']};g[k][t['as']]=0
   g[k][t['as']]+=1
  return[*g.values()]
class Sum(Op):
 name='summarize';f=CL('by',q=0,d=[]),Ls('metrics',Rc('metrics entry',(T('as'),C('fn',('sum','min','max','avg','count')),Lb('column',q=0))),ne=1)
 def run(s,t,rows,c):
  g={};o=[]
  for r in rows:g.setdefault(json.dumps([r.get(a)for a in t['by']]),[]).append(r)
  for m in g.values():
   w={a:m[0].get(a)for a in t['by']}
   for j,x in enumerate(t['metrics']):
    f=x['fn'];v=[y for y in([z.get(x['column'])for z in m]if'column'in x else m)if y is not None]
    if f=='count':w[x['as']]=len(v);continue
    any(not N(y)for y in v)and XE(t,f+' requires numbers','metrics',j,'column')
    w[x['as']]=None if not v else NR(sum(v))if f=='sum'else min(v)if f=='min'else max(v)if f=='max'else NR(sum(v)/len(v))
   o+=[w]
  return o
