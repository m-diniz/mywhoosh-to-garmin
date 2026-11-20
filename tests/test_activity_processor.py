from unittest.mock import MagicMock
from services.activity_processor import ActivityProcessor


def test_activity_processor_init():
    source, fit, garmin = MagicMock(), MagicMock(), MagicMock()
    ap = ActivityProcessor(source, fit, garmin)
    assert ap.source_service is source
    assert ap.fit_file_service is fit
    assert ap.garmin_service is garmin


def test_parse_iso_and_timestamp():
    ap = ActivityProcessor(MagicMock(), MagicMock(), MagicMock())
    assert ap._parse_activity_date("2026-11-20T17:16:29").hour == 17
    assert ap._parse_activity_date(1768039347) is not None
    assert ap._parse_activity_date("lixo") is None
