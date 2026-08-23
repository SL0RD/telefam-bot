"""Tests for the weather module's formatting helpers."""

from datetime import datetime

from modules.module_weather import _forecast_line, _local_display, _status_emoji


class TestForecastLine:
    def test_forecast_line_shows_date_only(self):
        line = _forecast_line("2026-08-24 12:00:00+00:00", 21.44, "clear sky")
        assert line == "\u2600\ufe0f Mon Aug 24 - Clear sky Temp: 21\u00b0C"

    def test_forecast_line_rain_emoji(self):
        line = _forecast_line("2026-08-23T09:05:00+00:00", 15.5, "light rain")
        assert line == "\U0001f327\ufe0f Sun Aug 23 - Light rain Temp: 16\u00b0C"

    def test_forecast_line_snow_emoji(self):
        line = _forecast_line("2026-12-31T20:30:00+00:00", 0.4, "snow")
        assert line == "\U0001f328\ufe0f Thu Dec 31 - Snow Temp: 0\u00b0C"

    def test_forecast_line_rounds_temperature(self):
        assert "Temp: 22\u00b0C" in _forecast_line("2026-08-24T12:00:00+00:00", 21.6, "cloudy")


class TestStatusEmoji:
    def test_thunder_wins_over_rain(self):
        # 'thunderstorm with heavy rain' contains both keywords; thunder must match first
        assert _status_emoji("thunderstorm with heavy rain") == "\u26c8\ufe0f"

    def test_cloud_variants(self):
        assert _status_emoji("few clouds") == "\u2601\ufe0f"
        assert _status_emoji("overcast clouds") == "\u2601\ufe0f"

    def test_fog_family(self):
        assert _status_emoji("mist") == "\U0001f32b\ufe0f"
        assert _status_emoji("fog") == "\U0001f32b\ufe0f"

    def test_unknown_condition_gets_default(self):
        assert _status_emoji("sandstorms of mars") == "\U0001f324\ufe0f"
        assert _status_emoji("") == "\U0001f324\ufe0f"

    def test_all_emoji_encode_to_utf8(self):
        statuses = [
            "thunderstorm with heavy rain",
            "shower drizzle",
            "light rain",
            "snow",
            "sleet",
            "hail",
            "few clouds",
            "fog",
            "mist",
            "haze",
            "clear sky",
            "sunny",
            "sandstorms of mars",
        ]
        for status in statuses:
            emoji = _status_emoji(status)
            assert emoji.encode("utf-8").decode("utf-8") == emoji


class TestLocalDisplay:
    def test_halifax_summer_is_adt(self):
        dt = datetime(2026, 8, 24, 22, 30)  # naive UTC
        assert _local_display(dt, 44.65, -63.57) == "7:30 PM ADT"

    def test_los_angeles_winter_is_pst(self):
        dt = datetime(2026, 1, 15, 4, 0)
        assert _local_display(dt, 34.05, -118.24) == "8:00 PM PST"

    def test_london_summer_is_bst(self):
        dt = datetime(2026, 7, 1, 12, 0)
        assert _local_display(dt, 51.51, -0.13) == "1:00 PM BST"

    def test_midday_has_no_leading_zero_artifact(self):
        dt = datetime(2026, 8, 24, 15, 5)  # 12:05 PM ADT in Halifax
        assert _local_display(dt, 44.65, -63.57).startswith("12:05 PM")

    def test_open_ocean_maps_to_etc_gmt(self):
        dt = datetime(2026, 8, 24, 12, 0)
        assert _local_display(dt, 0.0, 0.0) == "12:00 PM GMT"

    def test_unknown_zone_falls_back_to_utc(self, monkeypatch):
        from types import SimpleNamespace

        from modules import module_weather

        monkeypatch.setattr(
            module_weather,
            "_TZ_FINDER",
            SimpleNamespace(timezone_at=lambda **kwargs: None),
        )
        dt = datetime(2026, 8, 24, 12, 0)
        assert _local_display(dt, 44.65, -63.57) == "12:00 PM UTC"
