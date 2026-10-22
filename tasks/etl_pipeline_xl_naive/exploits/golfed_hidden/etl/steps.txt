from etl.errors import E,R,S
from etl.expr import px,ea
from etl.fields import F,T,rf
class St:
 def __init__(s,o,v,p,w):s.o,s.v,s.p,s.w=o,v,p,w
 __getitem__=lambda s,k:s.v[k]
 def at(s,*a):
  p=s.p
  for x in a:p+='[%d]'%x if isinstance(x,int)else'.'+x
  return p
J=lambda v:{'op':v.o.name,**{k:J(v.v[k])for k in sorted(v.v)}}if isinstance(v,St)else[J(x)for x in v]if isinstance(v,list)else{k:J(x)for k,x in v.items()}if isinstance(v,dict)else v
def sp(w,p):
 isinstance(w,dict)or R(S('step must be an object',p))
 n=T('op').r(w,p).lower();n in OPS or R(E('UNKNOWN_OP',"ETL_ERROR: unsupported op '%s'"%n,p+'.op'));o=OPS[n]
 return St(o,o.nz(w,p),p,w)
class Cx:
 def run(s,ss,rows):
  for t in ss:rows=t.o.run(t,rows,s)
  return rows
 def ev(s,t,x,r,*a):p=t.at(*a);return ea(px(x,p),r,p)
OPS={}
class Op:
 f=()
 def __init_subclass__(c):OPS[c.name]=c()
 nz=lambda s,w,p:rf(s.f,w,p)
class SL(F):
 def n(s,v,p):isinstance(v,list)or s.e('be an array',p);return[sp(x,'%s[%d]'%(p,i))for i,x in enumerate(v)]
