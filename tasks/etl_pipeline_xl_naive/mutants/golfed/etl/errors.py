class E(Exception):
 def __init__(s,c,m,p):super().__init__(m);s.c=c;s.p=p
S=lambda m,p:E('SCHEMA_VALIDATION_FAILED','ETL_ERROR: '+m,p)
def R(e):raise e
Z=lambda m,p:R(S(m,p))
