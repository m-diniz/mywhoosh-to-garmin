import pytest
from pathlib import Path
from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError
from services.garmin_service import GarminService, GarminTokenInvalid, is_rate_limited


def test_garmin_service_init_token_only(tmp_path):
    svc = GarminService(tmp_path)
    assert svc.tokenstore == Path(tmp_path)
    assert not hasattr(svc, 'password')


def test_missing_token_asks_for_login(tmp_path):
    svc = GarminService(tmp_path / 'nao-existe')
    with pytest.raises(GarminTokenInvalid, match='login_garmin'):
        svc.authenticate()


def test_expired_token_asks_for_login(tmp_path):
    svc = GarminService(tmp_path)
    svc.client.login = lambda *_: (_ for _ in ()).throw(GarminConnectAuthenticationError('401'))
    with pytest.raises(GarminTokenInvalid):
        svc.authenticate()


def test_upload_rate_limit_propagates(tmp_path):
    svc = GarminService(tmp_path)
    svc._authenticated = True
    svc.client.upload_activity = lambda *_: (_ for _ in ()).throw(
        GarminConnectTooManyRequestsError('429 Too Many Requests'))
    with pytest.raises(GarminConnectTooManyRequestsError):
        svc.upload_activity('x.fit')


def test_is_rate_limited():
    assert is_rate_limited(RuntimeError('HTTP 429'))
    assert not is_rate_limited(RuntimeError('HTTP 500'))
