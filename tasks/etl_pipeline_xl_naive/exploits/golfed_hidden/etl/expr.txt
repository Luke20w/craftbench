import re
from etl.errors import E
T=re.compile('\\s*(?:(?P<b>\\*{2,}|\\^+|%|&{3,}|\\|{3,}|&(?!&)|\\|(?!\\|)|=(?!=))|(?P<n>\\d+\\.\\d*|\\.\\d+|\\d+)|(?P<i>[A-Za-z_][A-Za-z0-9_]*)|(?P<s>"[^"]*"|\'[^\']*\')|(?P<o>>=|<=|==|!=|&&|\\|\\||[-+*/<>()!]))')
K={'and':'&&','or':'||','not':'!'}
L={'true':True,'false':False,'null':None}
def tk(t):
 k=[];p=0
 while p<len(t)and t[p:].strip():
  m=T.match(t,p)
  if not m:raise ValueError('unexpected character %r'%t[p:].lstrip()[0])
  p=m.end();g=m.lastgroup;v=m[g]
  if g=='b':raise ValueError("unsupported operator '%s'"%v)
  if g=='i'and v in K:g,v='o',K[v]
  k+=[(g,v)]
 return k
class P:
 def __init__(s,t):s.t=t;s.i=0
 pk=lambda s:s.t[s.i]if s.i<len(s.t)else(None,None)
 def tk(s):t=s.pk();s.i+=1;return t
 def at(s,o):k,v=s.pk();return k=='o'and v in o
 def parse(s):
  n=s.o()
  if s.i!=len(s.t):raise ValueError('unexpected token %r'%(s.pk()[1],))
  return n
 def b(s,o,f):
  n=f()
  while s.at(o):n='b',s.tk()[1],n,f()
  return n
 o=lambda s:s.b(('||',),s.a)
 a=lambda s:s.b(('&&',),s.n)
 def n(s):
  if s.at(('!',)):s.tk();return'u','!',s.n()
  return s.b(('>','>=','<','<=','==','!='),s.d)
 d=lambda s:s.b(('+','-'),s.m)
 m=lambda s:s.b(('*','/'),s.u)
 def u(s):
  if s.at(('+','-')):return'u',s.tk()[1],s.u()
  if s.at(('!',)):s.tk();return'u','!',s.u()
  k,v=s.tk()
  if k=='n':return'l',float(v)if'.'in v else int(v)
  if k=='s':return'l',v[1:-1]
  if k=='i':return('l',L[v])if v in L else('i',v)
  if k=='o'and v=='(':
   n=s.o()
   if s.tk()!=('o',')'):raise ValueError('missing closing parenthesis')
   return n
  raise ValueError('unexpected end of expression'if k is None else'unexpected token %r'%v)
def px(t,p):
 try:return P(tk(t)).parse()
 except ValueError as e:m=str(e);raise E('BAD_EXPR','ETL_ERROR: '+(m if m.startswith('unsupported operator')else'invalid expression: '+m),p)
N=lambda v:isinstance(v,(int,float))and not isinstance(v,bool)
Y=lambda v:v is not None and bool(v)
NR=lambda v:int(v)if isinstance(v,float)and v.is_integer()and abs(v)<1e15 else v
def ev(n,r):
 k=n[0]
 if k=='l':return n[1]
 if k=='i':return r.get(n[1])
 o=n[1]
 if k=='u':
  v=ev(n[2],r)
  if o=='!':return not Y(v)
  if v is None:return
  if not N(v):raise TypeError("unary '%s' requires a number"%o)
  return v if o=='+'else NR(-v)
 if o=='&&':return Y(ev(n[2],r))and Y(ev(n[3],r))
 if o=='||':return Y(ev(n[2],r))or Y(ev(n[3],r))
 l,q=ev(n[2],r),ev(n[3],r)
 if o in('+','-','*','/'):
  if l is None or q is None:return
  if o=='+'and isinstance(l,str)and isinstance(q,str):return l+q
  if not(N(l)and N(q)):raise TypeError("operator '%s' requires numeric operands"%o)
  return NR(l+q)if o=='+'else NR(l-q)if o=='-'else NR(l*q)if o=='*'else None if q==0 else NR(l/q)
 if l is None or q is None or not(N(l)and N(q))and type(l)is not type(q):return False
 if o=='==':return l==q
 if o=='!=':return l!=q
 return not isinstance(l,(bool,list,dict))and{'<':l<q,'<=':l<=q,'>':l>q,'>=':l>=q}[o]
def ea(n,r,p):
 try:return ev(n,r)
 except(TypeError,OverflowError,ValueError)as e:raise E('EXECUTION_FAILED','ETL_ERROR: %s'%e,p)
