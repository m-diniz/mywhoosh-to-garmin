import gzip
from unittest.mock import MagicMock

import pytest

from services.intervals_service import IntervalsService

FIT = b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT" + b"\x00" * 20


def svc_with(responses, source="MYWHOOSH"):
    svc = IntervalsService("i1", "key", source=source)
    def get(url, params=None, timeout=None):
        for suffix, (status, payload) in responses.items():
            if url.endswith(suffix):
                r = MagicMock(status_code=status)
                if isinstance(payload, bytes):
                    r.content = payload
                else:
                    r.json.return_value = payload
                return r
        raise AssertionError(url)
    svc.session.get = get
    return svc


def test_auth_is_basic_api_key():
    svc = IntervalsService("i1", "segredo")
    assert svc.session.auth == ("API_KEY", "segredo")


def test_filters_by_source_and_maps_fields():
    svc = svc_with({"/activities": (200, [
        {"id": "i2", "name": "Ride B", "start_date_local": "2026-11-20T08:00:00", "source": "MYWHOOSH"},
        {"id": "i1", "name": "Run", "start_date_local": "2026-11-19T08:00:00", "source": "GARMIN_CONNECT"},
        {"id": "i3", "name": "Ride A", "start_date_local": "2026-11-18T08:00:00", "device_name": "MyWhoosh"},
    ])})
    acts = svc.get_activities()
    assert [a["id"] for a in acts] == ["i2", "i3"]
    assert acts[0]["date"] == "2026-11-20T08:00:00" and acts[0]["name"] == "Ride B"


def test_source_none_returns_all():
    svc = svc_with({"/activities": (200, [{"id": "x", "source": "STRAVA"}])}, source=None)
    assert len(svc.get_activities()) == 1


def test_download_decompresses_gzip(tmp_path):
    svc = svc_with({"/activity/i2/file": (200, gzip.compress(FIT))})
    path = svc.download_activity({"id": "i2"})
    assert open(path, "rb").read() == FIT


def test_download_rejects_non_fit():
    svc = svc_with({"/activity/i2/file": (200, b"<gpx>not a fit file</gpx>")})
    with pytest.raises(RuntimeError, match="não é um FIT"):
        svc.download_activity({"id": "i2"})


def test_bad_key_message():
    svc = svc_with({"/athlete/i1": (401, {})})
    with pytest.raises(PermissionError, match="--setup"):
        svc.authenticate()
