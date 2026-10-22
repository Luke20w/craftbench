import json
from etl.expr import N
from etl.fields import T,Lb,C,X,Sc,Ls,Mp,CL
from etl.steps import Op
from etl.ops.common import cvs,cv,XE,tt
class Drop(Op):
 name='drop';f=CL(),
 def run(s,t,rows,c):k=cvs(t,rows);return[{a:v for a,v in r.items()if a not in k}for r in rows]
class Fill(Op):
 name='fill';f=T('column'),X('value')
 def run(s,t,rows,c):
  for r in rows:
   if r.get(t['column'])is None:r[t['column']]=c.ev(t,t['value'],r,'value')
  return rows
class Cast(Op):
 name='cast';f=T('column'),C('to',('int','float','string','bool'))
 def run(s,t,rows,c):
  for r in rows:
   v=cv(t,r)
   if v is not None:
    try:r[t['column']]=s.to(t['to'],v)
    except(TypeError,ValueError):XE(t,'cannot cast %s to %s'%(json.dumps(v),t['to']),'column')
  return rows
 def to(s,k,v):
  if k=='string':return tt(v)
  if k=='bool':
   if isinstance(v,bool):return v
   if isinstance(v,str)and v.strip().lower()in('true','false'):return v.strip().lower()=='true'
   if N(v):return v!=0
   raise ValueError
  if isinstance(v,bool):raise TypeError
  return(int if k=='int'else float)(v)
class Coal(Op):
 name='coalesce';f=T('as'),Ls('exprs',X('exprs entries'),ne=1)
 def run(s,t,rows,c):
  for r in rows:r[t['as']]=next((v for k,x in enumerate(t['exprs'])if(v:=c.ev(t,x,r,'exprs',k))is not None),None)
  return rows
class Expl(Op):
 name='explode';f=T('column'),
 def run(s,t,rows,c):
  o=[]
  for r in rows:v=cv(t,r);o+=[dict(r,**{t['column']:x})for x in v]if isinstance(v,list)else[r]
  return o
class Look(Op):
 name='lookup';f=T('column'),T('as'),Mp('table',Sc('table values')),Sc('default',q=0)
 def run(s,t,rows,c):
  for r in rows:v=cv(t,r);k=v if isinstance(v,str)else json.dumps(v);r[t['as']]=t['table'][k]if k in t['table']else t.v.get('default')
  return rows
class Set(Op):
 name='set';f=T('column'),Sc('value')
 def run(s,t,rows,c):
  for r in rows:r[t['column']]=t['value']
  return rows
class Ens(Op):
 name='ensure';f=CL(ne=1),Sc('value',q=0,d=None)
 def run(s,t,rows,c):
  for r in rows:
   for k in t['columns']:r.setdefault(k,t['value'])
  return rows
class Reord(Op):
 name='reorder';f=CL(ne=1),
 def run(s,t,rows,c):k=cvs(t,rows);return[dict([(a,r[a])for a in k]+[(a,v)for a,v in r.items()if a not in k])for r in rows]
class Pre(Op):
 name='prefix';f=Lb('prefix',ne=1),CL(q=0)
 def run(s,t,rows,c):
  for i,r in enumerate(rows):g=t.v.get('columns',r);rows[i]={(t['prefix']+a if a in g else a):v for a,v in r.items()}
  return rows
class Nest(Op):
 name='nest';f=CL(ne=1),T('as')
 def run(s,t,rows,c):k=cvs(t,rows);return[{**{a:v for a,v in r.items()if a not in k},t['as']:{a:r[a]for a in k}}for r in rows]
class Unn(Op):
 name='unnest';f=T('column'),Lb('prefix',q=0,d='')
 def run(s,t,rows,c):
  o=[]
  for r in rows:
   v=cv(t,r)
   if v is not None and not isinstance(v,dict):XE(t,'unnest requires an object','column')
   o+=[{**{k:x for k,x in r.items()if k!=t['column']},**{t['prefix']+k:x for k,x in(v or{}).items()}}]
  return o
