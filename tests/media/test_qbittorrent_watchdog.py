"""Exercise the checked-in watchdog shell with a fake Kubernetes API; no live writes."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = list(yaml.safe_load_all((ROOT / 'apps/media/qbittorrent-watchdog.yaml').read_text()))
SCRIPT = next(d for d in DOCS if d['kind'] == 'CronJob')['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['command'][-1]
NOW = 1795179600


def timestamp(age):
    return datetime.datetime.fromtimestamp(NOW - age, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class WatchdogTests(unittest.TestCase):
    def run_case(self, *, desired=1, available=0, outage=7200, condition='False', pods=(3600,), api_error=False, restart=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'watchdog.sh').write_text(SCRIPT)
            kubectl = path / 'kubectl'
            kubectl.write_text('''#!/usr/bin/env python3
import json, os, sys
s = json.loads(os.environ['TEST_STATE'])
a = sys.argv[1:]
if a[:2] == ['rollout', 'restart']:
    with open(os.environ['TEST_ACTIONS'], 'a') as f: f.write('restart\\n')
    sys.exit(0)
if a[:2] == ['get', 'pods']:
    if s['api_error']: sys.exit(1)
    print('\\n'.join(s['pods']))
    sys.exit(0)
query = a[-1]
if query == "jsonpath={.spec.replicas}": print(s['desired'])
elif query == "jsonpath={.status.availableReplicas}": print(s['available'])
elif 'lastTransitionTime' in query: print(s['since'])
elif 'conditions' in query: print(s['condition'])
else: sys.exit(2)
''')
            kubectl.chmod(0o755)
            date = path / 'date'
            date.write_text(f'''#!/bin/sh
if [ "$#" -eq 2 ] && [ "$1" = -u ] && [ "$2" = +%s ]; then
  echo {NOW}
else
  exec /usr/bin/date "$@"
fi
''')
            date.chmod(0o755)
            state = dict(desired=desired, available=available, since=timestamp(outage) if outage is not None else '', condition=condition, pods=[timestamp(age) for age in pods], api_error=api_error)
            actions = path / 'actions'
            env = dict(os.environ, PATH=f'{path}:{os.environ["PATH"]}', TEST_STATE=json.dumps(state), TEST_ACTIONS=str(actions))
            result = subprocess.run(['sh', '-ec', SCRIPT], env=env, capture_output=True, text=True)
            self.assertEqual(actions.read_text() if actions.exists() else '', 'restart\n' if restart else '', result.stdout + result.stderr)
            self.assertEqual(result.returncode, 1 if api_error else 0, result.stdout + result.stderr)

    def test_healthy(self): self.run_case(available=1)
    def test_scaled_to_zero(self): self.run_case(desired=0)
    def test_recent_outage(self): self.run_case(outage=899)
    def test_new_pod_during_old_outage(self): self.run_case(pods=(300,))
    def test_pod_just_under_grace(self): self.run_case(pods=(899,))
    def test_grace_elapsed(self): self.run_case(pods=(900,), restart=True)
    def test_old_pod(self): self.run_case(restart=True)
    def test_recent_pod_alongside_old(self): self.run_case(pods=(7200, 60))
    def test_missing_pod(self): self.run_case(pods=())
    def test_missing_transition(self): self.run_case(outage=None)
    def test_unknown_availability(self): self.run_case(condition='Unknown')
    def test_clock_skew(self): self.run_case(pods=(-60,))
    def test_api_failure_does_not_restart(self): self.run_case(api_error=True)


if __name__ == '__main__':
    unittest.main()
