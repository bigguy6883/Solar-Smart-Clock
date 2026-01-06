"""Tests for solar data provider."""

import datetime
import pytest
from unittest.mock import patch, MagicMock

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
        assert name in ["Dawn", "Sunrise", "Sunset", "Dusk"]
        assert time > datetime.datetime.now(time.tzinfo)

    def test_get_twilight_times(self, provider):
        """Test twilight times calculation."""
        twilight = provider.get_twilight_times()

        if twilight is not None:
            dawn, dusk = twilight
            assert dawn < dusk


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
