import os, socket, subprocess, tempfile, time, urllib.request, json
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
def request(port, path='/api/identity', data=None):
 return urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}'+path, data=data, headers={'Content-Type':'application/json'}), timeout=1)
with tempfile.TemporaryDirectory() as d:
 env=dict(os.environ,CONTROLE_AGENCES_DATA_DIR=d)
 blockers=[]
 try:
  for port in (8600,8601):
   s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('127.0.0.1',port)); s.listen(); blockers.append(s)
  p=subprocess.Popen([sys.executable,'server.py','--no-browser'],cwd=root,env=env)
  try:
   for _ in range(60):
    try:
     with request(8602) as r: assert json.load(r)['app_id']=='fr.controle-agences.desktop'
     break
    except OSError: time.sleep(.1)
   else: raise AssertionError('startup failed')
   subprocess.run([sys.executable,'server.py','--no-browser'],cwd=root,env=env,check=True,timeout=10)
   with request(8602,'/api/quit',b'{}') as r: assert json.load(r)['ok']
   assert p.wait(timeout=10)==0
  finally:
   if p.poll() is None: p.kill()
  s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(('127.0.0.1',8602)); s.listen(); blockers.append(s)
  failed=subprocess.run([sys.executable,'server.py','--no-browser'],cwd=root,env=env,capture_output=True,timeout=10)
  assert failed.returncode==1 and 'Les ports 8600, 8601 et 8602'.encode() in failed.stderr
  print('PASS fallback 8602, identity reuse, shutdown, occupied-port error')
 finally:
  for s in blockers:s.close()
