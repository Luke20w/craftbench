import json
from etl.errors import E,R
from etl.expr import N
def MC(c,p):R(E('MISSING_COLUMN',"ETL_ERROR: column '%s' not found in row"%c,p))
def cvs(t,rows,k='columns'):
 c=t[k]
 for r in rows:
  for j,x in enumerate(c):x in r or MC(x,t.at(k,j))
 return c
def cv(t,r,k='column'):c=t[k];return r[c]if c in r else MC(c,t.at(k))
def XE(t,m,*a):R(E('EXECUTION_FAILED','ETL_ERROR: '+m,t.at(*a)))
sv=lambda t,r:v if(v:=cv(t,r))is None or isinstance(v,str)else XE(t,t.o.name+' requires a string','column')
nv=lambda t,r:v if(v:=cv(t,r))is None or N(v)else XE(t,t.o.name+' requires a number','column')
tt=lambda v:v if isinstance(v,str)else json.dumps(v)
