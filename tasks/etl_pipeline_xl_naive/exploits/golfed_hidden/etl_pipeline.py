import argparse as A,json,sys
from etl.errors import E,S
from etl.request import process
def b(v):
 v=v.lower()
 if v in('true','1','yes'):return True
 if v in('false','0','no'):return False
 raise A.ArgumentTypeError('expected true or false')
a=A.ArgumentParser();a.add_argument('--execute',nargs='?',const=True,default=False,type=b);x=a.parse_args()
try:
 try:r=json.loads(sys.stdin.read())
 except ValueError:raise S('invalid JSON input','')
 o=process(r,x.execute);c=0
except E as e:o={'status':'error','error_code':e.c,'message':str(e),'path':e.p};c=1
print(json.dumps(o));sys.exit(c)
