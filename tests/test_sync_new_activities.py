import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from services import activity_processor
from services.activity_processor import ActivityProcessor
from services.sync_state import SyncState


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(activity_processor.time, 'sleep', lambda *_: None)


def ride(id_, days_ago):
    ts = int((datetime.now() - timedelta(days=days_ago)).timestamp())
    return {'id': id_, 'name': f'Ride {id_}', 'date': ts, 'activityFileId': f'f{id_}'}


def make(activities, duplicate_ids=()):
    mw, fit, garmin = MagicMock(), MagicMock(), MagicMock()
    mw.get_activities.return_value = activities
    mw.download_activity.side_effect = lambda a: f"orig_{a['id']}.fit"
    fit.modify_device_info.side_effect = lambda p: p.replace('orig', 'mod')
    garmin.check_duplicate_activity.side_effect = (
        lambda when, name: name.split()[-1] in duplicate_ids)
    garmin.upload_activity.return_value = {'ok': True}
    return ActivityProcessor(mw, fit, garmin), garmin


def test_uploads_new_oldest_first_and_records(tmp_path):
    state = SyncState(tmp_path / 's.json')
    proc, garmin = make([ride('b', 1), ride('a', 2)])
    stats = proc.sync_new_activities(state)
    assert stats['synced'] == 2
    assert stats['uploaded'] == ['Ride a', 'Ride b']
    assert [c.args[0] for c in garmin.upload_activity.call_args_list] == ['mod_a.fit', 'mod_b.fit']
    assert SyncState(tmp_path / 's.json').is_synced('a')


def test_second_run_does_nothing(tmp_path):
    state = SyncState(tmp_path / 's.json')
    proc, _ = make([ride('a', 1)])
    proc.sync_new_activities(state)
    proc2, garmin2 = make([ride('a', 1)])
    stats = proc2.sync_new_activities(SyncState(tmp_path / 's.json'))
    assert stats['total'] == 0
    garmin2.authenticate.assert_not_called()
    garmin2.upload_activity.assert_not_called()


def test_old_activities_ignored(tmp_path):
    proc, garmin = make([ride('old', 30)])
    stats = proc.sync_new_activities(SyncState(tmp_path / 's.json'), max_age_days=14)
    assert stats['total'] == 0
    garmin.upload_activity.assert_not_called()


def test_already_on_garmin_is_recorded_not_uploaded(tmp_path):
    state = SyncState(tmp_path / 's.json')
    proc, garmin = make([ride('a', 1)], duplicate_ids={'a'})
    stats = proc.sync_new_activities(state)
    assert stats['skipped'] == 1
    garmin.upload_activity.assert_not_called()
    assert state.is_synced('a')


def test_409_is_recorded(tmp_path):
    state = SyncState(tmp_path / 's.json')
    proc, garmin = make([ride('a', 1)])
    garmin.upload_activity.return_value = {'status': 'skipped'}
    assert proc.sync_new_activities(state)['skipped'] == 1
    assert state.is_synced('a')


def test_rate_limit_stops_and_keeps_rest_pending(tmp_path):
    state = SyncState(tmp_path / 's.json')
    proc, garmin = make([ride('b', 1), ride('a', 2)])
    garmin.upload_activity.side_effect = [{'ok': True}, RuntimeError('429 Too Many Requests')]
    stats = proc.sync_new_activities(state)
    assert stats['rate_limited'] and stats['synced'] == 1
    assert state.is_synced('a') and not state.is_synced('b')


def test_failed_upload_not_recorded_and_cleans_up(tmp_path):
    state = SyncState(tmp_path / 's.json')
    proc, garmin = make([ride('a', 1)])
    garmin.upload_activity.side_effect = RuntimeError('Upload failed: 500')
    stats = proc.sync_new_activities(state)
    assert stats['errors'] == 1 and not state.is_synced('a')
    cleaned = [c.args[0] for c in proc.fit_file_service.cleanup_file.call_args_list]
    assert cleaned == ['orig_a.fit', 'mod_a.fit']

