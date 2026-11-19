"""Run with Python/PyYAML and promtool on PATH (or PROMTOOL=/path/to/promtool)."""
import os
from pathlib import Path
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
values = yaml.safe_load((ROOT / 'infrastructure/base/monitoring/kube-prometheus-stack.yaml').read_text())['spec']['values']
rule = values['additionalPrometheusRulesMap']['homelab-job-health']
assert values['defaultRules']['disabled']['KubeJobFailed'] is True
# The recovery timestamp comparison relies on no overlapping executions.
for name in ['apps/matrix/bsky/resources.yaml', 'apps/media/anime-guard.yaml',
             'apps/media/qbittorrent-watchdog.yaml', 'apps/media/recyclarr.yaml',
             'infrastructure/base/vault/snapshot-cronjob.yaml']:
    cron = next(d for d in yaml.safe_load_all((ROOT / name).read_text()) if d and d['kind'] == 'CronJob')
    assert cron['spec']['concurrencyPolicy'] == 'Forbid', name

cases = []
def case(name, success=None, namespace='matrix', owner='bsky-notifier', owned=True, created=True, duplicate=False, expected=True):
    labels = {'job': 'kube-state-metrics', 'namespace': namespace, 'job_name': 'failed-100', 'condition': 'true'}
    def series(metric, tags, value):
        return {'series': metric + '{' + ','.join(f'{k}="{v}"' for k, v in tags.items()) + '}', 'values': f'{value}+0x20'}
    common = {'job': 'kube-state-metrics', 'namespace': namespace, 'job_name': 'failed-100'}
    data = [series('kube_job_failed', labels, 1)]
    if created:
        data.append(series('kube_job_created', common, 100))
    if owned:
        data.append(series('kube_job_owner', dict(common, owner_kind='CronJob', owner_name=owner, owner_is_controller='true'), 1))
    if success is not None:
        data.append(series('kube_cronjob_status_last_successful_time', {'job': 'kube-state-metrics', 'namespace': namespace, 'cronjob': owner}, success))
    if duplicate:
        data.extend(dict(s, series=s['series'][:-1] + ',instance="second-scrape"}') for s in list(data)[1:])
    annotations = rule['groups'][0]['rules'][0]['annotations'].copy()
    annotations['description'] = annotations['description'].replace('{{ $labels.namespace }}', namespace).replace('{{ $labels.job_name }}', 'failed-100')
    alerts = [{'exp_labels': dict(labels, severity='warning'), 'exp_annotations': annotations}] if expected else []
    cases.append({'name': name, 'interval': '1m', 'input_series': data, 'alert_rule_test': [
        {'eval_time': '14m', 'alertname': 'KubeJobFailed', 'exp_alerts': []},
        {'eval_time': '16m', 'alertname': 'KubeJobFailed', 'exp_alerts': alerts}]})

case('failure without a successful run')
case('old success does not hide a new failure', success=50)
case('later success clears serial job failure', success=200, expected=False)
case('duplicate scrape series remain safe', success=200, duplicate=True, expected=False)
case('one-off job stays visible', success=200, owned=False)
case('unlisted cronjob stays visible', success=200, owner='one-off-backup')
case('same cronjob name in another namespace stays visible', success=200, namespace='other')
case('missing creation metric fails open', success=200, created=False)
case('media serial job recovers', success=200, namespace='media', owner='anime-guard', expected=False)
case('vault serial job recovers', success=200, namespace='vault', owner='vault-snapshot', expected=False)
with tempfile.TemporaryDirectory() as tmp:
    rules = Path(tmp) / 'rules.yaml'
    rules.write_text(yaml.safe_dump(rule))
    tests = Path(tmp) / 'tests.yaml'
    tests.write_text(yaml.safe_dump({'rule_files': [str(rules)], 'evaluation_interval': '1m', 'tests': cases}))
    subprocess.run([os.environ.get('PROMTOOL', 'promtool'), 'check', 'rules', str(rules)], check=True)
    subprocess.run([os.environ.get('PROMTOOL', 'promtool'), 'test', 'rules', str(tests)], check=True)
