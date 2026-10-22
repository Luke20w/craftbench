from etl.errors import E,R,Z
from etl.expr import Y
from etl.fields import F,T,Lb,X,Cn,Ls,Mp,Rc,rf,CL
from etl.steps import Op,SL
from etl.ops.common import MC,cvs
class Sel(Op):
 name='select';f=CL(),
 def run(s,t,rows,c):k=cvs(t,rows);return[{x:r[x]for x in k}for r in rows]
class Flt(Op):name='filter';f=X('where'),;run=lambda s,t,rows,c:[r for r in rows if Y(c.ev(t,t['where'],r,'where'))]
class Map(Op):
 name='map';f=T('as'),X('expr')
 def run(s,t,rows,c):
  for r in rows:r[t['as']]=c.ev(t,t['expr'],r,'expr')
  return rows
class Ren(Op):
 name='rename'
 def nz(s,w,p):
  if'mapping'in w:return rf((Mp('mapping',Lb('mapping values')),),w,p)
  if'from'in w or'to'in w:v=rf((T('from'),T('to')),w,p);return{'mapping':{v['from']:v['to']}}
  Z("rename requires 'from' and 'to' or 'mapping'",p)
 def run(s,t,rows,c):
  for a,b in t['mapping'].items():
   p=t.at('from')if'mapping'not in t.w else t.at('mapping',a);o=[]
   for r in rows:a in r or MC(a,p);o+=[{(b if k==a else k):v for k,v in r.items()if k!=b or k==a}]
   rows=o
  return rows
class Lim(Op):name='limit';f=Cn('n'),;run=lambda s,t,rows,c:rows[:t['n']]
class Bs(Ls):
 def ck(s,v,p):
  g=[isinstance(b,dict)and b.get('when')=='otherwise'for b in v]
  if sum(g)>1:R(E('MALFORMED_STEP',"ETL_ERROR: at most one 'otherwise' branch allowed",p))
  if any(g[:-1]):R(E('MALFORMED_STEP',"ETL_ERROR: 'otherwise' branch must be last",p))
class Ms(F):n=lambda s,v,p:v if v=='concat'else Z("only 'concat' merge strategy is supported",p)
class Br(Op):
 name='branch';f=Bs('branches',Rc('branch',(X('when',lit=('otherwise',),tr=0),SL('steps'),Lb('id',q=0))),ne=1),Rc('merge',(Ms('strategy',q=0,d='concat'),),q=0,d={'strategy':'concat'})
 def run(s,t,rows,c):
  B=t['branches'];o=[[]for _ in B]
  for r in rows:
   for j,b in enumerate(B):
    if b['when']=='otherwise'or Y(c.ev(t,b['when'],r,'branches',j,'when')):o[j]+=[r];break
  return[x for b,q in zip(B,o)if q for x in c.run(b['steps'],[dict(r)for r in q])]
