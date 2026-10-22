import json,re
from etl.fields import T,Lb,C,B,Cn,Pt,CL
from etl.steps import Op
from etl.ops.common import cvs,cv,XE,sv,tt
class Cat(Op):
 name='concat';f=T('as'),CL(ne=1),Lb('sep',q=0,d='')
 def run(s,t,rows,c):
  k=cvs(t,rows)
  for r in rows:r[t['as']]=t['sep'].join(''if r[a]is None else tt(r[a])for a in k)
  return rows
class Spl(Op):
 name='split';f=T('column'),Lb('sep',ne=1),CL('into',ne=1)
 def run(s,t,rows,c):
  for r in rows:
   v=sv(t,r);q=v.split(t['sep'])if v is not None else[]
   for i,n in enumerate(t['into']):r[n]=q[i]if i<len(q)else None
  return rows
class Txt(Op):
 name='text';f=CL(),C('fn',('upper','lower','trim'))
 def run(s,t,rows,c):
  k=cvs(t,rows);g={'upper':str.upper,'lower':str.lower,'trim':str.strip}[t['fn']]
  for r in rows:
   for j,a in enumerate(k):
    if r[a]is not None:isinstance(r[a],str)or XE(t,'text requires a string','columns',j);r[a]=g(r[a])
  return rows
class Rep(Op):
 name='replace';f=T('column'),Lb('find',ne=1),Lb('with')
 def run(s,t,rows,c):
  for r in rows:
   v=sv(t,r)
   if v is not None:r[t['column']]=v.replace(t['find'],t['with'])
  return rows
class RxE(Op):
 name='regex_extract';f=T('column'),Pt('pattern'),T('as'),Cn('group',q=0,d=0)
 def run(s,t,rows,c):
  x=re.compile(t['pattern'])
  for r in rows:
   v=sv(t,r);m=x.search(v)if v is not None else None
   if m and t['group']>x.groups:XE(t,'pattern has no group %d'%t['group'],'group')
   r[t['as']]=m[t['group']]if m else None
  return rows
class RxF(Op):
 name='regex_filter';f=T('column'),Pt('pattern'),B('invert',q=0,d=False)
 def run(s,t,rows,c):x=re.compile(t['pattern']);return[r for r in rows if(isinstance(v:=r.get(t['column']),str)and x.search(v)is not None)!=t['invert']]
class Sub(Op):
 name='substr';f=T('column'),T('as'),Cn('start'),Cn('length',q=0)
 def run(s,t,rows,c):
  for r in rows:v=sv(t,r);a=t['start'];r[t['as']]=None if v is None else v[a:a+t['length']]if'length'in t.v else v[a:]
  return rows
class Pad(Op):
 name='pad';f=T('column'),Cn('width'),Lb('fill',ne=1,q=0,d=' '),C('side',('left','right'),q=0,d='left')
 def run(s,t,rows,c):
  for r in rows:
   v=cv(t,r)
   if v is not None:x=tt(v);n=max(0,t['width']-len(x));d=(t['fill']*n)[:n];r[t['column']]=d+x if t['side']=='left'else x+d
  return rows
class Len(Op):
 name='length';f=T('column'),T('as')
 def run(s,t,rows,c):
  for r in rows:
   v=cv(t,r)
   if v is not None and not isinstance(v,(str,list,dict)):XE(t,'length requires a string, array or object','column')
   r[t['as']]=None if v is None else len(v)
  return rows
class JP(Op):
 name='json_parse';f=T('column'),
 def run(s,t,rows,c):
  for r in rows:
   v=sv(t,r)
   if v is not None:
    try:r[t['column']]=json.loads(v)
    except ValueError:XE(t,'invalid JSON text','column')
  return rows
class JD(Op):
 name='json_dump';f=T('column'),
 def run(s,t,rows,c):
  for r in rows:
   v=cv(t,r)
   if v is not None:r[t['column']]=json.dumps(v,sort_keys=True)
  return rows
class DP(Op):
 name='date_part';f=T('column'),C('part',('year','month','day')),T('as')
 def run(s,t,rows,c):
  for r in rows:
   v=cv(t,r)
   if v is None:r[t['as']]=None;continue
   m=re.match(r'^(\d{4})-(\d{2})-(\d{2})',v)if isinstance(v,str)else None
   m or XE(t,'expected a YYYY-MM-DD date','column');r[t['as']]=int(m[('year','month','day').index(t['part'])+1])
  return rows
