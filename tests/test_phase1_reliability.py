import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
import baseline
import collector
from data_utils import _merge_manual
from sklearn.linear_model import LinearRegression


def test_fold_preprocessing_uses_training_only():
    X = pd.DataFrame({'x': [1., 3., np.nan, 1000.], 'empty': [np.nan]*4})
    model = baseline._model_pipeline(LinearRegression())
    model.fit(X.iloc[:3], [1., 3., 2.])
    assert model.named_steps['imputer'].statistics_[0] == 2.
    assert model.named_steps['scaler'].mean_[0] == 2.
    assert np.isfinite(model.predict(X.iloc[3:])).all()


def test_unusable_fold_reports_insufficient():
    df = pd.DataFrame({'verdict':['pass','pass','fail','fail'], 'x':[1.,np.nan,np.nan,np.nan]})
    result = baseline.verdict_baseline(df, df[['x']])
    assert result['status'] == 'insufficient'
    assert '某折' in result['reason']


def test_nonfinite_features_and_targets():
    df = pd.DataFrame({'task':['t']*8, 'seed':range(8), 'verdict':['pass','fail']*4,
                       'success_rate':[np.inf]*8, 'duration_seconds':range(8),
                       'x':[1.,2.,np.inf,4.,5.,6.,7.,8.]})
    X = baseline.feature_matrix(df)
    assert pd.isna(X.iloc[2]['x'])
    assert baseline.regression_baseline(df, X, 'success_rate')['status'] == 'insufficient'
    assert baseline.regression_baseline(df, X, 'duration_seconds')['status'] == 'ok'


@pytest.mark.parametrize('override', [
    {'verdict':'other'}, {'success_rate':1.1}, {'success_rate':'bad'},
    {'label_updated_at':'not-a-time'}, {'task':''},
])
def test_manual_invalid_values_rejected(override):
    base = pd.DataFrame([{'task':'t','seed':'s','verdict':'pass','success_rate':1.}])
    manual = pd.DataFrame([{'task':'t','seed':'s',**override}])
    with pytest.raises(ValueError): _merge_manual(base, manual)


def test_duplicate_manual_key_rejected():
    df = pd.DataFrame([{'task':'t','seed':'s','verdict':'pass'}])
    with pytest.raises(ValueError): _merge_manual(df, pd.concat([df,df]))


def test_atomic_csv_write_failure_keeps_old(tmp_path):
    target = tmp_path/'runs.csv';target.write_text('old')
    df = pd.DataFrame(columns=collector.table_columns('runs'))
    with patch.object(pd.DataFrame, 'to_csv', side_effect=OSError('disk full')):
        with pytest.raises(OSError): collector.write_frame(df, 'runs', tmp_path)
    assert target.read_text() == 'old'
    assert not list(tmp_path.glob('*.tmp'))


def test_local_config_precedence(tmp_path):
    p=tmp_path/'config.local.json';p.write_text(json.dumps({'source_repo':'','lianghua_db':'','output_dir':'data','raw_dir':'raw'}))
    with patch.object(collector,'PROJECT_ROOT',tmp_path):
        assert collector.load_config()['_config_path'] == str(p)
        assert collector.load_config()['source_repo'] is None


def test_monitor_has_no_outbound_notification():
    import realtime_monitor
    assert not hasattr(realtime_monitor.RealtimeMonitor,'send_feishu')
    source = Path(realtime_monitor.__file__).read_text()
    assert 'requests.post' not in source

import os
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def command(*args, cwd=None, env=None):
    return subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True)

@pytest.mark.parametrize('failed_step', ['collector.py','run_pipeline.py'])
def test_daily_failure_no_marker_or_publish(tmp_path, failed_step):
    scripts=tmp_path/'scripts';scripts.mkdir()
    shutil.copy(ROOT/'scripts/cron_cycle.sh',scripts/'cron_cycle.sh')
    (scripts/'sync_github.sh').write_text('touch "'+str(tmp_path/'published')+'"\n')
    bin_dir=tmp_path/'bin';bin_dir.mkdir()
    flock=bin_dir/'flock';flock.write_text('#!/bin/sh\nexit 0\n');flock.chmod(0o755)
    venv=tmp_path/'.venv/bin';venv.mkdir(parents=True)
    python=venv/'python';python.write_text('#!/bin/sh\ncase "$1" in *'+failed_step+') exit 7;; esac\nexit 0\n');python.chmod(0o755)
    result=command('bash',str(scripts/'cron_cycle.sh'),env={**os.environ,'PATH':str(bin_dir)+os.pathsep+os.environ['PATH'],'TMPDIR':str(tmp_path)})
    assert result.returncode != 0
    assert not (tmp_path/'data/.quant_last_date').exists()
    assert not (tmp_path/'published').exists()
    assert '失败' in (tmp_path/'data/cycle.log').read_text()
    python.write_text('#!/bin/sh\nexit 0\n')
    retried=command('bash',str(scripts/'cron_cycle.sh'),env={**os.environ,'PATH':str(bin_dir)+os.pathsep+os.environ['PATH'],'TMPDIR':str(tmp_path)})
    assert retried.returncode == 0
    assert (tmp_path/'data/.quant_last_date').exists()
    assert (tmp_path/'published').exists()


def setup_sync(tmp_path):
    remote=tmp_path/'remote.git';assert command('git','init','--bare',str(remote)).returncode == 0
    repo=tmp_path/'repo';repo.mkdir();command('git','init','-b','main',cwd=repo)
    command('git','config','user.name','Test',cwd=repo);command('git','config','user.email','test@example.invalid',cwd=repo)
    scripts=repo/'scripts';scripts.mkdir();shutil.copy(ROOT/'scripts/sync_github.sh',scripts/'sync_github.sh')
    (repo/'data/datasets').mkdir(parents=True);(repo/'data/datasets/x.csv').write_text('x\n1\n')
    command('git','add','.',cwd=repo);command('git','commit','-m','initial',cwd=repo)
    command('git','remote','add','origin',str(remote),cwd=repo);command('git','push','origin','main',cwd=repo)
    return repo,remote

@pytest.mark.parametrize('case',['branch','staged','nondata','remote'])
def test_sync_guards(tmp_path,case):
    repo,remote=setup_sync(tmp_path)
    if case=='branch':command('git','switch','-c','other',cwd=repo)
    elif case=='staged':
        (repo/'data/datasets/x.csv').write_text('x\n2\n');command('git','add','.',cwd=repo)
    elif case=='nondata':(repo/'notes.txt').write_text('private')
    else:
        peer=tmp_path/'peer';command('git','clone','-b','main',str(remote),str(peer))
        command('git','config','user.name','Test',cwd=peer);command('git','config','user.email','test@example.invalid',cwd=peer)
        (peer/'new.txt').write_text('new');command('git','add','.',cwd=peer);command('git','commit','-m','remote',cwd=peer);command('git','push','origin','main',cwd=peer)
    head=command('git','rev-parse','HEAD',cwd=repo).stdout
    result=command('bash','scripts/sync_github.sh','--once',cwd=repo)
    assert result.returncode != 0
    assert command('git','rev-parse','HEAD',cwd=repo).stdout==head
