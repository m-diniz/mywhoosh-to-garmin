from services.notify import Alerts, GENERIC_FAILURES_BEFORE_ALERT


def make(tmp_path):
    sent = []
    return Alerts(tmp_path / 'a.json', notifier=lambda t, b: sent.append(t)), sent


def test_same_problem_alerts_once(tmp_path):
    alerts, sent = make(tmp_path)
    for _ in range(5):
        Alerts(tmp_path / 'a.json', notifier=lambda t, b: sent.append(t)).problem('garmin_token', 'T', 'B')
    assert sent == ['T']


def test_success_resets_so_problem_alerts_again(tmp_path):
    alerts, sent = make(tmp_path)
    alerts.problem('garmin_token', 'T', 'B')
    alerts.ok()
    alerts.problem('garmin_token', 'T', 'B')
    assert sent == ['T', 'T']


def test_generic_failures_wait_before_alerting(tmp_path):
    sent = []
    for _ in range(GENERIC_FAILURES_BEFORE_ALERT - 1):
        Alerts(tmp_path / 'a.json', notifier=lambda t, b: sent.append(t)).problem('x', 'T', 'B', generic=True)
    assert sent == []
    Alerts(tmp_path / 'a.json', notifier=lambda t, b: sent.append(t)).problem('x', 'T', 'B', generic=True)
    assert sent == ['T']


def test_different_problem_alerts_again(tmp_path):
    alerts, sent = make(tmp_path)
    alerts.problem('garmin_token', 'A', 'B')
    alerts.problem('intervals_key', 'C', 'D')
    assert sent == ['A', 'C']
