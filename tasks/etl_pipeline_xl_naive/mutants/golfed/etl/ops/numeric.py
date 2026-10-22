import json,math
from etl.expr import N,NR
from etl.fields import T,C,Cn,Nm,Ls
from etl.steps import Op
from etl.ops.common import cv,XE,nv
class Rnd(Op):
 name='round';f=T('column'),Cn('digits',q=0,d=0)
 def run(s,t,rows,c):
  for r in rows:
   v=nv(t,r)
   if v is not None:r[t['column']]=NR(round(v,t['digits']))
  return rows
class Clip(Op):
 name='clip';f=T('column'),Nm('min',q=0),Nm('max',q=0)
 def run(s,t,rows,c):
  for r in rows:
   v=nv(t,r)
   if v is None:continue
   if'min'in t.v and v<t['min']:v=t['min']
   if'max'in t.v and v>t['max']:v=t['max']
   r[t['column']]=v
  return rows
class Scl(Op):
 name='scale';f=T('column'),Nm('factor'),Nm('offset',q=0,d=0)
 def run(s,t,rows,c):
  for r in rows:
   v=nv(t,r)
   if v is not None:r[t['column']]=NR(v*t['factor']+t['offset'])
  return rows
class Bkt(Op):
 name='bucket';f=T('column'),T('as'),Ls('edges',Nm('edges entries'),ne=1)
 def run(s,t,rows,c):
  for r in rows:v=nv(t,r);r[t['as']]=None if v is None else sum(1 for e in t['edges']if v>=e)
  return rows
class Mth(Op):
 name='math';f=T('column'),C('fn',('abs','floor','ceil','sqrt','neg'))
 def run(s,t,rows,c):
  f=t['fn']
  for r in rows:
   v=cv(t,r)
   if v is None:continue
   if not N(v)or f=='sqrt'and v<0:XE(t,'cannot apply %s to %s'%(f,json.dumps(v)),'column')
   r[t['column']]=abs(v)if f=='abs'else math.floor(v)if f=='floor'else math.ceil(v)if f=='ceil'else NR(math.sqrt(v)if f=='sqrt'else-v)
  return rows
class Btw(Op):
 name='between';f=T('column'),Nm('low'),Nm('high'),T('as')
 def run(s,t,rows,c):
  for r in rows:
   v=r.get(t['column'])
   if v is not None and not N(v):XE(t,'between requires a number','column')
   r[t['as']]=v is not None and t['low']<=v<=t['high']
  return rows
