"""Tests for the weather module's forecast formatting."""

from modules.module_weather import _forecast_line


def test_forecast_line_shows_date_only():
    line = _forecast_line("2026-08-24 12:00:00+00:00", 21.44, "clear sky")
    assert line == "Mon Aug 24 - Clear sky Temp: 21\u00b0C"


def test_forecast_line_different_date():
    line = _forecast_line("2026-08-23T09:05:00+00:00", 15.5, "light rain")
    assert line == "Sun Aug 23 - Light rain Temp: 16\u00b0C"


def test_forecast_line_year_boundary():
    line = _forecast_line("2026-12-31T20:30:00+00:00", 0.4, "snow")
    assert line == "Thu Dec 31 - Snow Temp: 0\u00b0C"


def test_forecast_line_rounds_temperature():
    assert "Temp: 22\u00b0C" in _forecast_line("2026-08-24T12:00:00+00:00", 21.6, "cloudy")
