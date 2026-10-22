import re
from etl.errors import S,R,Z
from etl.expr import px,N
M=object()
class F:
 def __init__(s,k,x=None,q=1,d=M,**o):s.k,s.x,s.q,s.d=k,x,q,d;s.__dict__.update(o)
 def r(s,w,p):
  p+='.'+s.k
  if s.k in w:return s.n(w[s.k],p)
  if s.q:Z("missing required field '%s'"%s.k,p)
  return s.d
 n=lambda s,v,p:v
 def e(s,m,p):Z("'%s' must %s"%(s.k,m),p)
class T(F):
 def n(s,v,p):isinstance(v,str)or s.e('be a string',p);v=v.strip();return v or s.e('not be empty',p)
class Lb(F):
 ne=0
 def n(s,v,p):isinstance(v,str)or s.e('be a string',p);return v if v or not s.ne else s.e('not be empty',p)
class C(T):
 def n(s,v,p):v=T.n(s,v,p).lower();return v if v in s.x else s.e('be one of '+', '.join(s.x),p)
class B(F):n=lambda s,v,p:v if isinstance(v,bool)else s.e('be a boolean',p)
class X(T):
 lit=();tr=1
 def n(s,v,p):
  if s.tr:v=T.n(s,v,p)
  elif not isinstance(v,str):s.e('be a string',p)
  v in s.lit or px(v,p);return v
class I(F):
 mn=None
 def n(s,v,p):
  if isinstance(v,bool)or not isinstance(v,int):s.e('be an integer',p)
  if s.mn is not None and v<s.mn:s.e('be >= %d'%s.mn,p)
  return v
class Cn(I):mn=0
class Nm(F):n=lambda s,v,p:v if N(v)else s.e('be a number',p)
class Sc(F):n=lambda s,v,p:v if v is None or isinstance(v,(bool,int,float,str))else s.e('be a JSON scalar',p)
class Pt(Lb):
 ne=1
 def n(s,v,p):
  v=Lb.n(s,v,p)
  try:re.compile(v)
  except re.error:s.e('be a valid regular expression',p)
  return v
class Ob(F):
 def n(s,v,p):
  isinstance(v,list)or s.e('be an array',p)
  for i,x in enumerate(v):isinstance(x,dict)or Z("'%s' entries must be objects"%s.k,'%s[%d]'%(p,i))
  return[dict(x)for x in v]
class Ls(F):
 ne=0
 def n(s,v,p):isinstance(v,list)or s.e('be an array',p);v or not s.ne or s.e('be non-empty',p);s.ck(v,p);return[s.x.n(y,'%s[%d]'%(p,i))for i,y in enumerate(v)]
 ck=lambda s,v,p:0
class Mp(F):
 def n(s,v,p):isinstance(v,dict)or s.e('be an object',p);return{k:s.x.n(y,p+'.'+k)for k,y in v.items()}
class Rc(F):
 def n(s,v,p):isinstance(v,dict)or Z('%s must be an object'%s.k,p);return rf(s.x,v,p)
rf=lambda fs,w,p:{f.k:v for f in fs if(v:=f.r(w,p))is not M}
CL=lambda k='columns',**o:Ls(k,Lb('column names'),**o)
