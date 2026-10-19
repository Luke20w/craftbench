import json,re,sys,argparse as A
class E(Exception):
 def __init__(s,c,m,p):s.args='ETL_ERROR: '+m,;s.c=c;s.p=p
def R(e):raise e
X=lambda*a:R(E(*a))
S=lambda m,p:X('SCHEMA_VALIDATION_FAILED',m,p)
T=re.compile('\\s*(?:(?P<b>\\*{2,}|\\^+|%|&{3,}|\\|{3,}|&(?!&)|\\|(?!\\|)|=(?!=))|(?P<n>\\d+\\.\\d*|\\.\\d+|\\d+)|(?P<i>[A-Za-z_][A-Za-z0-9_]*)|(?P<s>"[^"]*"|\'[^\']*\')|(?P<o>>=|<=|==|!=|&&|\\|\\||[-+*/<>()!]))')
K={'and':'&&','or':'||','not':'!'}
L={'true':1>0,'false':1<0,'null':None}
M=int,float
def tokenize(t):
 k=[];p=0
 while p<len(t)and t[p:].strip():
  m=T.match(t,p)or R(ValueError('unexpected character %r'%t[p:].lstrip()[0]));p=m.end();g=m.lastgroup;v=m[g];g=='b'and R(ValueError("unsupported operator '%s'"%v))
  if g=='i'and v in K:g,v='o',K[v]
  k+=[(g,v)]
 return k
class P:
 def __init__(s,t):s.t=t+[(0,0)];s.i=0
 def at(s,o):k,v=s.t[s.i];return k=='o'and v in o
 def take(s):s.i+=1;return s.t[s.i-1]
 def parse(s):n=s.o();k,v=s.t[s.i];return n if k==0 else R(ValueError('unexpected token %r'%v))
 def b(s,o,f):
  n=f()
  while s.at(o):n='b',s.take()[1],n,f()
  return n
 o=lambda s:s.b(['||'],s.a)
 a=lambda s:s.b(['&&'],s.n)
 n=lambda s:s.at('!')and s.take()and('u','!',s.n())or s.c()
 c=lambda s:s.b('> >= < <= == !='.split(),s.d)
 d=lambda s:s.b('+-',s.m)
 m=lambda s:s.b('*/',s.u)
 u=lambda s:s.at('+-')and('u',s.take()[1],s.u())or s.at('!')and s.take()and('u','!',s.u())or s.p()
 def p(s):
  k,v=s.take()
  if k=='n':return'l',float(v)if'.'in v else int(v)
  if k=='s':return'l',v[1:-1]
  if k=='i':return('l',L[v])if v in L else('i',v)
  if k=='o'and v=='(':n=s.o();s.take()==('o',')')or R(ValueError('missing closing parenthesis'));return n
  R(ValueError('unexpected end of expression'if k==0 else'unexpected token %r'%v))
def parse_expr(t,p):
 try:return P(tokenize(t)).parse()
 except ValueError as e:m=str(e);X('BAD_EXPR',m if m[:5]=='unsup'else'invalid expression: '+m,p)
def G(s,k,P):v=F(s,k,P,str,'a string').strip();return v or S("'%s' must not be empty"%k,P+'.'+k)
def F(s,k,P,t,a):p=P+'.'+k;k in s or S("missing required field '%s'"%k,p);v=s[k];type(v)is t or S("'%s' must be %s"%(k,a),p);return v
def normalize_step(s,i,P=0):
 P=P or'pipeline.steps[%d]'%i;isinstance(s,dict)or S('step must be an object',P);o=F(s,'op',P,str,'a string').strip().lower();o in('select','filter','map','rename','limit','branch')or X('UNKNOWN_OP',"unsupported op '%s'"%o,P+'.op')
 if o=='select':
  c=F(s,'columns',P,list,'an array')
  for j,k in enumerate(c):isinstance(k,str)or S('column names must be strings','%s.columns[%d]'%(P,j))
  return{'op':o,'columns':c}
 if o=='filter':w=G(s,'where',P);parse_expr(w,P+'.where');return{'op':o,'where':w}
 if o=='map':a=G(s,'as',P);e=G(s,'expr',P);parse_expr(e,P+'.expr');return{'op':o,'as':a,'expr':e}
 if o=='rename':
  if'mapping'in s:
   m=F(s,'mapping',P,dict,'an object')
   for k,v in m.items():isinstance(v,str)or S('mapping values must be strings','%s.mapping.%s'%(P,k))
   return{'op':o,'mapping':m}
  'from'in s or'to'in s or S("rename requires 'from' and 'to' or 'mapping'",P);return{'op':o,'mapping':{G(s,'from',P):G(s,'to',P)}}
 if o=='limit':n=F(s,'n',P,int,'an integer');n<0 and S("'n' must be >= 0",P+'.n');return{'op':o,'n':n}
 B=F(s,'branches',P,list,'an array');p=P+'.branches';B or S("'branches' must be non-empty",p);z=[j for j,b in enumerate(B)if isinstance(b,dict)and b.get('when')=='otherwise'];len(z)>1 and X('MALFORMED_STEP',"at most one 'otherwise' branch allowed",p);z and z[0]!=len(B)-1 and X('MALFORMED_STEP',"'otherwise' branch must be last",p);l=[]
 for j,b in enumerate(B):
  q='%s[%d]'%(p,j);isinstance(b,dict)or S('branch must be an object',q);h=F(b,'when',q,str,'a string');h=='otherwise'or parse_expr(h,q+'.when');t=F(b,'steps',q,list,'an array');d={'when':h}
  if'id'in b:d['id']=F(b,'id',q,str,'a string')
  d['steps']=[normalize_step(u,k,'%s.steps[%d]'%(q,k))for k,u in enumerate(t)];l+=d,
 m=F(s,'merge',P,dict,'an object')if'merge'in s else{};m.get('strategy','concat')=='concat'or S("only 'concat' merge strategy is supported",P+'.merge.strategy');return{'op':o,'branches':l,'merge':{'strategy':'concat'}}
def nr(v):return int(v)if type(v)is float and v.is_integer()and abs(v)<1e15 else v
def evaluate(n,r):
 k,o=n[:2];e=lambda x:evaluate(x,r)
 if k=='l':return o
 if k=='i':return r.get(o)
 if k=='u':
  v=e(n[2])
  if o=='!':return not v
  if v is None:return
  type(v)in M or R(TypeError("unary '%s' requires a number"%o));return v if o=='+'else nr(-v)
 if o=='&&':return bool(e(n[2])and e(n[3]))
 if o=='||':return bool(e(n[2])or e(n[3]))
 a,b=e(n[2]),e(n[3])
 if o in'+-*/':
  if a is None or b is None:return
  if o=='+'and type(a)==type(b)==str:return a+b
  type(a)in M and type(b)in M or R(TypeError("operator '%s' requires numeric operands"%o));return None if o=='/'and b==0 else nr(eval('a'+o+'b'))
 if a is None or b is None:return 1<0
 return(type(a)in M and type(b)in M or type(a)is type(b))and(o in'==!='or not isinstance(a,(bool,list,dict)))and eval('a'+o+'b')
def eval_at(n,r,p):
 try:return evaluate(n,r)
 except(TypeError,OverflowError,ValueError)as e:X('EXECUTION_FAILED',str(e),p)
def execute_steps(u,w,z,P):
 for i,s in enumerate(u):
  p='%s[%d]'%(P,i);o=s['op']
  if o=='select':
   c=s['columns']
   for r in z:
    for j,k in enumerate(c):k in r or X('MISSING_COLUMN',"column '%s' not found in row"%k,'%s.columns[%d]'%(p,j))
   z=[{k:r[k]for k in c}for r in z]
  elif o=='filter':n=parse_expr(s['where'],p+'.where');z=[r for r in z if eval_at(n,r,p+'.where')]
  elif o=='map':
   n=parse_expr(s['expr'],p+'.expr')
   for r in z:r[s['as']]=eval_at(n,r,p+'.expr')
  elif o=='rename':
   f=w and'mapping'not in w[i]
   for a,d in s['mapping'].items():
    q=p+'.from'if f else'%s.mapping.%s'%(p,a)
    for r in z:a in r or X('MISSING_COLUMN',"column '%s' not found in row"%a,q)
    z=[{(d if k==a else k):v for k,v in r.items()if k==a or k!=d}for r in z]
  elif o=='limit':z=z[:s['n']]
  elif o=='branch':
   B=s['branches'];Q=[[]for _ in B]
   for r in z:
    for j,b in enumerate(B):
     if b['when']=='otherwise'or eval_at(parse_expr(b['when'],q:='%s.branches[%d].when'%(p,j)),r,q):Q[j].append(r);break
   z=sum((execute_steps(b['steps'],[],[dict(r)for r in Q[j]],'%s.branches[%d].steps'%(p,j))for j,b in enumerate(B)),[])
 return z
def process(q,run=0):
 isinstance(q,dict)or S('request must be an object','');p=q.get('pipeline');isinstance(p,dict)or S("'pipeline' must be an object",'pipeline');s=p.get('steps');isinstance(s,list)or S("'steps' must be an array",'pipeline.steps');d=q.get('dataset');isinstance(d,list)or S("'dataset' must be an array",'dataset')
 for i,r in enumerate(d):isinstance(r,dict)or S('dataset rows must be objects','dataset[%d]'%i)
 n=[normalize_step(t,i)for i,t in enumerate(s)]
 if not run:return{'status':'ok','normalized':{'steps':n}}
 x=execute_steps(n,s,[dict(r)for r in d],'pipeline.steps');return{'status':'ok','data':x,'metrics':{'rows_in':len(d),'rows_out':len(x)}}
def parse_bool(v):v=v.lower();return v in('true','1','yes')or(v in('false','0','no')or R(A.ArgumentTypeError('expected true or false')))and 0
def main():
 p=A.ArgumentParser();p.add_argument('--execute',nargs='?',const=1,type=parse_bool);a=p.parse_args()
 try:
  try:q=json.loads(sys.stdin.read())
  except ValueError:S('invalid JSON input','')
  r=process(q,a.execute);c=0
 except E as e:r={'status':'error','error_code':e.c,'message':str(e),'path':e.p};c=1
 print(json.dumps(r));sys.exit(c)
main()
