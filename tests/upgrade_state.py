"""Create/read a private local run fixture across a package upgrade; no API calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

action, directory = sys.argv[1:]
root = Path(directory)
run = {"version":1,"id":"package-upgrade","kind":"bulk","status":"accepted","remoteId":"upgrade-test-job"}
path = root / 'profiles/default/runs' / (hashlib.sha256(run['id'].encode()).hexdigest()+'.json')
payload = (json.dumps(run, sort_keys=True)+'\n').encode()
if action == 'prepare':
    for folder in [root, root/'profiles', root/'profiles/default', path.parent]:
        folder.mkdir(parents=True, exist_ok=True)
        folder.chmod(0o700)
    path.write_bytes(payload)
    path.chmod(0o600)
assert path.read_bytes() == payload, 'Upgrade changed the saved run record'
actual = json.loads(subprocess.check_output(['flashdata','runs','show',run['id'],'--state-dir',str(root),'--json','--non-interactive']).decode('utf-8'))
assert actual['ok'] and all(actual['data'][key] == value for key,value in run.items())
print('PASS: preserved private run record is readable by the installed CLI')
