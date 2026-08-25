"""In-container Python payloads used only by the R2C Docker lock fixture."""

THREAD_NOOP_FLOCK = r"""
import json,threading,time
from concurrent.futures import ThreadPoolExecutor
import shaiwei.storage.interprocess_lock as backend
from shaiwei.storage.interprocess_lock import logical_lock
from shaiwei.storage.lock_resources import DAILY_CYCLE
backend.fcntl.flock=lambda *_args: None
barrier=threading.Barrier(8); guard=threading.Lock(); state={'active':0,'maximum':0}
def worker(_index):
 barrier.wait()
 with logical_lock(DAILY_CYCLE):
  with guard:
   state['active']+=1; state['maximum']=max(state['maximum'],state['active'])
  time.sleep(.005)
  with guard: state['active']-=1
with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(worker,range(8)))
assert state=={'active':0,'maximum':1},state
print(json.dumps({'threads':8,'maximum_active':1,'explicit_root':False},sort_keys=True))
"""

HOLDER = """
import sys,time
from pathlib import Path
from shaiwei.storage.interprocess_lock import LockMode,logical_lock
resource,mode,ready,release=sys.argv[1:]
with logical_lock(resource,mode=LockMode(mode)):
 Path(ready).write_text('ready',encoding='utf-8')
 deadline=time.monotonic()+30
 while not Path(release).exists():
  if time.monotonic()>deadline: raise RuntimeError('holder gate timeout')
  time.sleep(.01)
"""

PROBE = """
import sys
from shaiwei.storage.interprocess_lock import LockBusy,LockMode,logical_lock
resource,mode,expected=sys.argv[1:]
actual='acquired'
try:
 with logical_lock(resource,mode=LockMode(mode),blocking=False): pass
except LockBusy: actual='busy'
if actual!=expected: raise RuntimeError(f'{actual}!={expected}')
print(actual)
"""

LEDGER = r"""
import csv,subprocess,sys
from pathlib import Path
from shaiwei import ledger
p=Path('/workspace/ledger/r2c_synthetic.csv'); p.write_text('id,value\n',encoding='utf-8')
worker="from pathlib import Path; import sys; from shaiwei import ledger; ledger._append(Path(sys.argv[1]),{'id':sys.argv[2],'value':'v'+sys.argv[2]})"
ps=[subprocess.Popen([sys.executable,'-c',worker,str(p),str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(8)]
errors=[]
for x in ps:
 out,err=x.communicate(timeout=20)
 if x.returncode: errors.append((x.returncode,out,err))
if errors: raise RuntimeError(str(errors))
with p.open(newline='',encoding='utf-8') as h: rows=list(csv.DictReader(h))
assert len(rows)==8 and {r['id'] for r in rows}=={str(i) for i in range(8)}
q=Path('/workspace/ledger/r2c_collision.csv'); q.write_text('id,value\n',encoding='utf-8')
assert ledger._append_idempotent(q,{'id':'one','value':'a'},key='id')
assert not ledger._append_idempotent(q,{'id':'one','value':'a'},key='id')
try: ledger._append_idempotent(q,{'id':'one','value':'b'},key='id')
except ValueError: pass
else: raise RuntimeError('collision accepted')
"""

MISSING_MOUNT = (
    "from shaiwei.storage.interprocess_lock import *; "
    "\ntry:\n with logical_lock('runtime:daily-cycle'): pass"
    "\nexcept LockConfigurationError: pass\nelse: raise RuntimeError('missing mount accepted')"
)

READONLY_MOUNT = (
    "from shaiwei.storage.interprocess_lock import *; "
    "\ntry:\n with logical_lock('runtime:scheduler-timeline:20991231'): pass"
    "\nexcept LockConfigurationError: pass\nelse: raise RuntimeError('readonly mount accepted')"
)

RESOURCE_RULES = r"""
from shaiwei.storage.interprocess_lock import *
try: logical_lock('runtime:unknown').__enter__()
except Exception: pass
else: raise RuntimeError('unknown accepted')
with logical_lock('runtime:daily-cycle'):
 try: logical_lock('runtime:daily-cycle').__enter__()
 except LockOrderError: pass
 else: raise RuntimeError('reentrant accepted')
 with logical_lock('ledger:r2c.csv'):
  try: logical_lock('runtime:shadow-cycle').__enter__()
  except LockOrderError: pass
  else: raise RuntimeError('reverse order accepted')
"""
