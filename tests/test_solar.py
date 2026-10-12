"""Tests for solar data provider."""

import datetime
import pytest

from solar_clock.data.solar import SolarProvider, SunTimes, SolarPosition, GoldenHour


class TestSolarProvider:
    """Tests for SolarProvider."""

    @pytest.fixture
    def provider(self):
        """Create a solar provider instance."""
        return SolarProvider(
            name="Test City",
            region="Test Region",
            timezone="America/New_York",
            latitude=40.7128,
            longitude=-74.0060,
        )

    def test_init(self, provider):
        """Test provider initialization."""
        assert provider.location.name == "Test City"
        assert provider.location.latitude == 40.7128
        assert provider.location.longitude == -74.0060

    def test_get_sun_times(self, provider):
        """Test getting sun times."""
        sun_times = provider.get_sun_times()

        assert sun_times is not None
        assert isinstance(sun_times, SunTimes)
        assert sun_times.sunrise < sun_times.sunset
        assert sun_times.dawn < sun_times.sunrise
        assert sun_times.sunset < sun_times.dusk

    def test_get_sun_times_specific_date(self, provider):
        """Test getting sun times for specific date."""
        date = datetime.date(2024, 6, 21)  # Summer solstice
        sun_times = provider.get_sun_times(date)

        assert sun_times is not None
        assert sun_times.sunrise.date() == date

    def test_get_solar_position(self, provider):
        """Test getting current solar position."""
        position = provider.get_solar_position()

        assert position is not None
        assert isinstance(position, SolarPosition)
        assert -90 <= position.elevation <= 90
        assert 0 <= position.azimuth <= 360

    def test_get_solar_position_specific_time(self, provider):
        """Test solar position at specific time."""
        # Noon should have higher elevation than early morning
        noon = datetime.datetime(2024, 6, 21, 12, 0, tzinfo=datetime.timezone.utc)
        morning = datetime.datetime(2024, 6, 21, 6, 0, tzinfo=datetime.timezone.utc)

        noon_pos = provider.get_solar_position(noon)
        morning_pos = provider.get_solar_position(morning)

        assert noon_pos is not None
        assert morning_pos is not None
        assert noon_pos.elevation > morning_pos.elevation

    def test_get_golden_hour(self, provider):
        """Test golden hour calculation."""
        morning, evening = provider.get_golden_hour()

        assert morning is not None
        assert evening is not None
        assert isinstance(morning, GoldenHour)
        assert isinstance(evening, GoldenHour)
        assert morning.start < morning.end
        assert evening.start < evening.end
        assert morning.end < evening.start  # Morning before evening

    def test_get_day_length(self, provider):
        """Test day length calculation."""
        length = provider.get_day_length()

        assert length is not None
        assert 0 < length < 24  # Hours

    def test_day_length_variation(self, provider):
        """Test day length varies by season."""
        summer = datetime.date(2024, 6, 21)
        winter = datetime.date(2024, 12, 21)

        summer_length = provider.get_day_length(summer)
        winter_length = provider.get_day_length(winter)

        assert summer_length is not None
        assert winter_length is not None
        # Summer days are longer in northern hemisphere
        assert summer_length > winter_length

    def test_get_day_length_change(self, provider):
        """Test day length change calculation."""
        change = provider.get_day_length_change()

        # Change should be a small number of minutes
        assert change is not None
        assert -10 < change < 10  # Minutes

    def test_get_next_solar_event(self, provider):
        """Test next solar event calculation."""
        event = provider.get_next_solar_event()

        assert event is not None
        name, time = event
        assert name in ["Dawn", "Sunrise", "Solar Noon", "Sunset", "Dusk"]
        assert time > datetime.datetime.now(time.tzinfo)

    def test_get_twilight_times(self, provider):
        """Test twilight times calculation."""
        twilight = provider.get_twilight_times()

        if twilight is not None:
            dawn, dusk = twilight
            assert dawn < dusk

    def test_get_sun_times_cached_per_date(self, provider):
        """get_sun_times() should call astral sun() only once per date."""
        from unittest.mock import patch
        import datetime

        today = datetime.date(2026, 2, 20)
        fake_times = {
            "dawn": datetime.datetime(2026, 2, 20, 6, 0, tzinfo=datetime.timezone.utc),
            "sunrise": datetime.datetime(
                2026, 2, 20, 6, 30, tzinfo=datetime.timezone.utc
            ),
            "noon": datetime.datetime(2026, 2, 20, 12, 0, tzinfo=datetime.timezone.utc),
            "sunset": datetime.datetime(
                2026, 2, 20, 18, 0, tzinfo=datetime.timezone.utc
            ),
            "dusk": datetime.datetime(
                2026, 2, 20, 18, 30, tzinfo=datetime.timezone.utc
            ),
        }

        with patch("solar_clock.data.solar.sun", return_value=fake_times) as mock_sun:
            result1 = provider.get_sun_times(today)
            result2 = provider.get_sun_times(today)
            result3 = provider.get_sun_times(today)

        assert (
            mock_sun.call_count == 1
        ), f"Expected 1 astral sun() call, got {mock_sun.call_count}"
        assert result1 == result2 == result3
        assert result1 is not None
        assert result1.sunrise.hour == 6


class TestSolarPositionCalculations:
    """Tests for specific solar calculations."""

    @pytest.fixture
    def equator_provider(self):
        """Provider at equator."""
        return SolarProvider(
            name="Equator",
            region="Test",
            timezone="UTC",
            latitude=0.0,
            longitude=0.0,
        )

    @pytest.fixture
    def arctic_provider(self):
        """Provider in arctic (high latitude)."""
        return SolarProvider(
            name="Arctic",
            region="Test",
            timezone="UTC",
            latitude=70.0,
            longitude=0.0,
        )

    def test_equinox_equal_day_night(self, equator_provider):
        """Test day length near equinox at equator."""
        equinox = datetime.date(2024, 3, 20)
        length = equator_provider.get_day_length(equinox)

        assert length is not None
        # Should be close to 12 hours at equator during equinox
        assert 11.5 < length < 12.5

    def test_high_latitude_long_summer_day(self, arctic_provider):
        """Test long summer days at high latitude."""
        summer = datetime.date(2024, 6, 21)
        length = arctic_provider.get_day_length(summer)

        # Arctic should have very long summer days (potentially 24h)
        # But sun times calculation may fail for polar day
        if length is not None:
            assert length > 18  # Very long day


class TestNextEventWithoutTwilight:
    """get_next_solar_event(include_twilight=False): sunrise, solar noon, sunset only."""

    TZ = "America/New_York"

    @pytest.fixture
    def provider(self):
        return SolarProvider(
            name="Test City",
            region="Test Region",
            timezone=self.TZ,
            latitude=40.7128,
            longitude=-74.0060,
        )

    @staticmethod
    def _stub_days(provider, today_offsets, tomorrow_offsets):
        """Make the provider's sun times sit at the given hours from now."""
        now = datetime.datetime.now(provider.tz)

        def times(offsets):
            return SunTimes(*(now + datetime.timedelta(hours=h) for h in offsets))

        today, tomorrow = times(today_offsets), times(tomorrow_offsets)
        next_day = now.date() + datetime.timedelta(days=1)
        provider.get_sun_times = lambda date=None: (
            tomorrow if date == next_day else today
        )
        return today, tomorrow

    # Offsets are (dawn, sunrise, noon, sunset, dusk) in hours from now.
    TOMORROW = (20, 20.5, 26, 32, 32.5)

    def test_before_dawn_it_skips_dawn(self, provider):
        today, _ = self._stub_days(provider, (0.2, 0.7, 6, 12, 12.5), self.TOMORROW)
        assert provider.get_next_solar_event() == ("Dawn", today.dawn)
        assert provider.get_next_solar_event(include_twilight=False) == (
            "Sunrise",
            today.sunrise,
        )

    def test_in_daylight_it_agrees_with_the_full_list(self, provider):
        today, _ = self._stub_days(provider, (-3, -2.5, 3, 9, 9.5), self.TOMORROW)
        assert provider.get_next_solar_event(include_twilight=False) == (
            "Solar Noon",
            today.noon,
        )
        today, _ = self._stub_days(provider, (-9, -8.5, -3, 3, 3.5), self.TOMORROW)
        assert provider.get_next_solar_event(include_twilight=False) == (
            "Sunset",
            today.sunset,
        )
        assert provider.get_next_solar_event() == ("Sunset", today.sunset)

    def test_between_sunset_and_dusk_it_skips_dusk(self, provider):
        today, tomorrow = self._stub_days(
            provider, (-13, -12.5, -6, -0.2, 0.3), self.TOMORROW
        )
        assert provider.get_next_solar_event() == ("Dusk", today.dusk)
        assert provider.get_next_solar_event(include_twilight=False) == (
            "Sunrise",
            tomorrow.sunrise,
        )

    def test_at_night_it_is_tomorrows_sunrise_not_dawn(self, provider):
        _, tomorrow = self._stub_days(
            provider, (-16, -15.5, -9, -3, -2.5), self.TOMORROW
        )
        assert provider.get_next_solar_event() == ("Dawn", tomorrow.dawn)
        assert provider.get_next_solar_event(include_twilight=False) == (
            "Sunrise",
            tomorrow.sunrise,
        )
