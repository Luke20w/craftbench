import json
from itertools import takewhile,dropwhile
from etl.expr import N,Y,NR
from etl.fields import T,Lb,B,X,Cn,I,Sc,Ob,CL
from etl.steps import Op
from etl.ops.common import XE
class Dst(Op):
 name='distinct';f=CL(q=0),
 def run(s,t,rows,c):
  z,o=set(),[]
  for r in rows:k=json.dumps([r.get(a)for a in t['columns']])if'columns'in t.v else json.dumps(r,sort_keys=True);k in z or(z.add(k),o.append(r))
  return o
TO=(N,0),(lambda v:isinstance(v,str),1),(lambda v:isinstance(v,bool),2)
class Srt(Op):
 name='sort';f=T('by'),B('desc',q=0,d=False)
 def run(s,t,rows,c):b=t['by'];return sorted([r for r in rows if r.get(b)is not None],key=lambda r:s.k(t,r[b]),reverse=t['desc'])+[r for r in rows if r.get(b)is None]
 def k(s,t,v):
  for f,n in TO:
   if f(v):return n,v
  XE(t,'cannot sort by a %s value'%type(v).__name__,'by')
class Off(Op):name='offset';f=Cn('n'),;run=lambda s,t,rows,c:rows[t['n']:]
class Tail(Op):name='tail';f=Cn('n'),;run=lambda s,t,rows,c:rows[max(0,len(rows)-t['n']):]if t['n']else[]
class Ast(Op):
 name='assert';f=X('where'),Lb('message',q=0,d='assertion failed')
 def run(s,t,rows,c):
  for r in rows:Y(c.ev(t,t['where'],r,'where'))or XE(t,t['message'],'where')
  return rows
class SE(Op):name='sample_every';f=Cn('n',mn=1),;run=lambda s,t,rows,c:rows[::t['n']]
class TW(Op):name='take_while';f=X('where'),;run=lambda s,t,rows,c:[*takewhile(lambda r:Y(c.ev(t,t['where'],r,'where')),rows)]
class SW(Op):name='skip_while';f=X('where'),;run=lambda s,t,rows,c:[*dropwhile(lambda r:Y(c.ev(t,t['where'],r,'where')),rows)]
class App(Op):name='append';f=Ob('rows'),;run=lambda s,t,rows,c:rows+[dict(x)for x in t['rows']]
class Req(Op):
 name='require';f=CL(ne=1),
 def run(s,t,rows,c):
  for r in rows:
   for j,a in enumerate(t['columns']):r.get(a)is None and XE(t,"column '%s' is required"%a,'columns',j)
  return rows
class RN(Op):
 name='row_number';f=T('as'),I('start',q=0,d=1)
 def run(s,t,rows,c):
  for i,r in enumerate(rows):r[t['as']]=t['start']+i
  return rows
class Rk(Op):
 name='rank';f=T('by'),T('as'),B('desc',q=0,d=False)
 def run(s,t,rows,c):
  d=[]
  for r in rows:
   v=r.get(t['by'])
   if v is not None:N(v)or XE(t,'rank requires numbers','by');v in d or d.append(v)
  d.sort(reverse=t['desc'])
  for r in rows:v=r.get(t['by']);r[t['as']]=None if v is None else d.index(v)+1
  return rows
class CS(Op):
 name='cumsum';f=T('column'),T('as')
 def run(s,t,rows,c):
  n=0
  for r in rows:
   v=r.get(t['column'])
   if v is not None and not N(v):XE(t,'cumsum requires numbers','column')
   n=NR(n+(v or 0));r[t['as']]=n
  return rows
class Lag(Op):
 name='lag';f=T('column'),T('as'),Cn('n',q=0,d=1),Sc('default',q=0)
 def run(s,t,rows,c):
  v=[r.get(t['column'])for r in rows];n=t['n']
  for i,r in enumerate(rows):r[t['as']]=v[i-n]if i>=n else t.v.get('default')
  return rows
