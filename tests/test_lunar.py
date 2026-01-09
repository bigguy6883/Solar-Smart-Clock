"""Tests for lunar data provider and moon calculations."""

import datetime
from unittest.mock import patch

import pytest

from solar_clock.data.lunar import (
    LunarProvider,
    MoonPhase,
    MoonTimes,
    SolsticeEquinox,
    AnalemmaPoint,
)


class TestLunarProvider:
    """Tests for the LunarProvider class."""

    @pytest.fixture
    def provider(self):
        """Create a LunarProvider instance."""
        return LunarProvider(latitude=40.7128, longitude=-74.0060)

    def test_initialization(self, provider):
        """Test LunarProvider initialization."""
        assert provider.latitude == 40.7128
        assert provider.longitude == -74.0060

    def test_available_property(self, provider):
        """Test that available property reflects ephem availability."""
        # Should return True or False depending on whether ephem is installed
        assert isinstance(provider.available, bool)

    @pytest.mark.skipif(
        not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
    )
    def test_get_moon_phase(self, provider):
        """Test getting moon phase data."""
        phase = provider.get_moon_phase()

        assert phase is not None
        assert isinstance(phase, MoonPhase)
        assert 0 <= phase.phase <= 1
        assert 0 <= phase.illumination <= 100
        assert isinstance(phase.phase_name, str)
        assert isinstance(phase.next_new, datetime.date)
        assert isinstance(phase.next_full, datetime.date)
        assert isinstance(phase.days_to_new, int)
        assert isinstance(phase.days_to_full, int)

    @pytest.mark.skipif(
        not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
    )
    def test_get_moon_times(self, provider):
        """Test getting moonrise and moonset times."""
        times = provider.get_moon_times()

        assert times is not None
        assert isinstance(times, MoonTimes)
        # Moonrise/moonset can be None if moon is always up or never up
        if times.moonrise is not None:
            assert isinstance(times.moonrise, datetime.datetime)
        if times.moonset is not None:
            assert isinstance(times.moonset, datetime.datetime)

    @pytest.mark.skipif(
        not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
    )
    def test_get_moon_times_specific_date(self, provider):
        """Test getting moon times for a specific date."""
        test_date = datetime.date(2024, 6, 15)
        times = provider.get_moon_times(test_date)

        assert times is not None
        assert isinstance(times, MoonTimes)

    @pytest.mark.skipif(
        not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
    )
    def test_get_solstice_equinox(self, provider):
        """Test getting solstice and equinox dates."""
        year = 2024
        dates = provider.get_solstice_equinox(year)

        assert isinstance(dates, SolsticeEquinox)
        assert dates.spring_equinox.year == year
        assert dates.summer_solstice.year == year
        assert dates.fall_equinox.year == year
        assert dates.winter_solstice.year == year

        # Check approximate months (accounting for timezone/precision)
        assert dates.spring_equinox.month == 3
        assert dates.summer_solstice.month == 6
        assert dates.fall_equinox.month in [9, 10]
        assert dates.winter_solstice.month == 12

        # Check chronological order
        assert dates.spring_equinox < dates.summer_solstice
        assert dates.summer_solstice < dates.fall_equinox
        assert dates.fall_equinox < dates.winter_solstice

    def test_get_solstice_equinox_without_ephem(self):
        """Test solstice/equinox returns fallback dates when ephem unavailable."""
        with patch("solar_clock.data.lunar.EPHEM_AVAILABLE", False):
            provider = LunarProvider(40.7128, -74.0060)
            dates = provider.get_solstice_equinox(2024)

            # Should return approximate dates
            assert isinstance(dates, SolsticeEquinox)
            assert dates.spring_equinox == datetime.date(2024, 3, 20)
            assert dates.summer_solstice == datetime.date(2024, 6, 21)
            assert dates.fall_equinox == datetime.date(2024, 9, 22)
            assert dates.winter_solstice == datetime.date(2024, 12, 21)

    @pytest.mark.skipif(
        not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
    )
    def test_get_equation_of_time(self, provider):
        """Test getting equation of time."""
        eot = provider.get_equation_of_time()

        assert eot is not None
        assert isinstance(eot, float)
        # Equation of time ranges from about -16 to +16 minutes
        assert -20 <= eot <= 20

    @pytest.mark.skipif(
        not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
    )
    def test_get_equation_of_time_specific_date(self, provider):
        """Test equation of time for specific dates."""
        # Test dates where equation of time has known characteristics
        # Equation of time varies throughout the year

        feb_eot = provider.get_equation_of_time(datetime.date(2024, 2, 11))
        nov_eot = provider.get_equation_of_time(datetime.date(2024, 11, 3))

        assert feb_eot is not None
        assert nov_eot is not None

        # Both should be within valid range
        assert -20 <= feb_eot <= 20
        assert -20 <= nov_eot <= 20

        # They should have different values (equation of time changes)
        assert abs(feb_eot - nov_eot) > 5

    @pytest.mark.skipif(
        not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
    )
    def test_get_analemma_data(self, provider):
        """Test getting analemma data points."""
        points = provider.get_analemma_data()

        assert isinstance(points, list)
        assert len(points) > 0  # Should have ~52 points (weekly samples)

        for point in points:
            assert isinstance(point, AnalemmaPoint)
            assert isinstance(point.elevation, float)
            assert isinstance(point.equation_of_time, float)
            assert isinstance(point.date, datetime.date)

            # Elevation should be reasonable for NYC latitude
            # (roughly 20-70 degrees at solar noon)
            assert 0 <= point.elevation <= 90

            # Equation of time should be in expected range
            assert -20 <= point.equation_of_time <= 20

    def test_get_analemma_data_without_ephem(self):
        """Test analemma data returns empty list when ephem unavailable."""
        with patch("solar_clock.data.lunar.EPHEM_AVAILABLE", False):
            provider = LunarProvider(40.7128, -74.0060)
            points = provider.get_analemma_data()

            assert points == []

    def test_get_moon_phase_without_ephem(self):
        """Test moon phase returns None when ephem unavailable."""
        with patch("solar_clock.data.lunar.EPHEM_AVAILABLE", False):
            provider = LunarProvider(40.7128, -74.0060)
            phase = provider.get_moon_phase()

            assert phase is None

    def test_get_moon_times_without_ephem(self):
        """Test moon times returns None when ephem unavailable."""
        with patch("solar_clock.data.lunar.EPHEM_AVAILABLE", False):
            provider = LunarProvider(40.7128, -74.0060)
            times = provider.get_moon_times()

            assert times is None

    def test_get_equation_of_time_without_ephem(self):
        """Test equation of time returns None when ephem unavailable."""
        with patch("solar_clock.data.lunar.EPHEM_AVAILABLE", False):
            provider = LunarProvider(40.7128, -74.0060)
            eot = provider.get_equation_of_time()

            assert eot is None


class TestPhaseNameMapping:
    """Tests for moon phase name mapping."""

    @pytest.mark.parametrize(
        "phase,expected_name",
        [
            (0.00, "New Moon"),
            (0.02, "New Moon"),
            (0.05, "Waxing Crescent"),
            (0.15, "Waxing Crescent"),
            (0.25, "First Quarter"),
            (0.30, "Waxing Gibbous"),
            (0.40, "Waxing Gibbous"),
            (0.50, "Full Moon"),
            (0.52, "Full Moon"),
            (0.60, "Waning Gibbous"),
            (0.70, "Waning Gibbous"),
            (0.75, "Last Quarter"),
            (0.80, "Waning Crescent"),
            (0.90, "Waning Crescent"),
            (0.98, "New Moon"),
        ],
    )
    def test_get_phase_name(self, phase, expected_name):
        """Test phase name mapping for various phase values."""
        result = LunarProvider._get_phase_name(phase)
        assert result == expected_name

    def test_all_phase_names_covered(self):
        """Test that all phase values from 0 to 1 return a valid name."""
        valid_names = {
            "New Moon",
            "Waxing Crescent",
            "First Quarter",
            "Waxing Gibbous",
            "Full Moon",
            "Waning Gibbous",
            "Last Quarter",
            "Waning Crescent",
        }

        # Test 100 points across the phase range
        for i in range(100):
            phase = i / 100.0
            name = LunarProvider._get_phase_name(phase)
            assert name in valid_names


class TestMoonPhaseDataclass:
    """Tests for MoonPhase dataclass."""

    def test_moon_phase_creation(self):
        """Test creating MoonPhase instance."""
        today = datetime.date.today()
        phase = MoonPhase(
            phase=0.25,
            illumination=50.0,
            phase_name="First Quarter",
            next_new=today + datetime.timedelta(days=15),
            next_full=today + datetime.timedelta(days=7),
            days_to_new=15,
            days_to_full=7,
        )

        assert phase.phase == 0.25
        assert phase.illumination == 50.0
        assert phase.phase_name == "First Quarter"
        assert phase.days_to_new == 15
        assert phase.days_to_full == 7


class TestMoonTimesDataclass:
    """Tests for MoonTimes dataclass."""

    def test_moon_times_creation(self):
        """Test creating MoonTimes instance."""
        now = datetime.datetime.now()
        times = MoonTimes(
            moonrise=now + datetime.timedelta(hours=1),
            moonset=now + datetime.timedelta(hours=12),
        )

        assert times.moonrise is not None
        assert times.moonset is not None

    def test_moon_times_with_none(self):
        """Test MoonTimes can have None values."""
        times = MoonTimes(moonrise=None, moonset=None)

        assert times.moonrise is None
        assert times.moonset is None


class TestSolsticeEquinoxDataclass:
    """Tests for SolsticeEquinox dataclass."""

    def test_solstice_equinox_creation(self):
        """Test creating SolsticeEquinox instance."""
        dates = SolsticeEquinox(
            spring_equinox=datetime.date(2024, 3, 20),
            summer_solstice=datetime.date(2024, 6, 21),
            fall_equinox=datetime.date(2024, 9, 22),
            winter_solstice=datetime.date(2024, 12, 21),
        )

        assert dates.spring_equinox.month == 3
        assert dates.summer_solstice.month == 6
        assert dates.fall_equinox.month == 9
        assert dates.winter_solstice.month == 12


class TestAnalemmaPointDataclass:
    """Tests for AnalemmaPoint dataclass."""

    def test_analemma_point_creation(self):
        """Test creating AnalemmaPoint instance."""
        point = AnalemmaPoint(
            elevation=45.5, equation_of_time=10.2, date=datetime.date(2024, 6, 15)
        )

        assert point.elevation == 45.5
        assert point.equation_of_time == 10.2
        assert point.date == datetime.date(2024, 6, 15)


@pytest.mark.skipif(
    not pytest.importorskip("ephem", reason="ephem not installed"), reason=""
)
class TestLunarProviderIntegration:
    """Integration tests for LunarProvider with real calculations."""

    @pytest.fixture
    def provider(self):
        """Create a LunarProvider for New York City."""
        return LunarProvider(latitude=40.7128, longitude=-74.0060)

    def test_moon_phase_illumination_matches_phase(self, provider):
        """Test that moon illumination roughly matches phase."""
        phase_data = provider.get_moon_phase()

        if phase_data:
            # Around new moon (phase ~0), illumination should be low
            if phase_data.phase < 0.1 or phase_data.phase > 0.9:
                assert phase_data.illumination < 25

            # Around full moon (phase ~0.5), illumination should be high
            if 0.45 < phase_data.phase < 0.55:
                assert phase_data.illumination > 90

    def test_solstice_dates_reasonable(self, provider):
        """Test that solstice/equinox dates are in expected ranges."""
        dates = provider.get_solstice_equinox(2024)

        # Spring equinox: Mar 19-21
        assert 19 <= dates.spring_equinox.day <= 21

        # Summer solstice: Jun 20-22
        assert 20 <= dates.summer_solstice.day <= 22

        # Fall equinox: Sep 21-23
        assert 21 <= dates.fall_equinox.day <= 23

        # Winter solstice: Dec 20-22
        assert 20 <= dates.winter_solstice.day <= 22

    def test_analemma_creates_figure_eight_pattern(self, provider):
        """Test that analemma data shows expected pattern."""
        points = provider.get_analemma_data()

        if len(points) > 0:
            # Extract elevations and equation of time values
            elevations = [p.elevation for p in points]
            eot_values = [p.equation_of_time for p in points]

            # Elevation should vary (higher in summer, lower in winter)
            elevation_range = max(elevations) - min(elevations)
            assert elevation_range > 20  # At least 20 degrees variation

            # Equation of time should have both positive and negative values
            assert max(eot_values) > 5  # At least +5 minutes
            assert min(eot_values) < -5  # At least -5 minutes

    def test_days_to_full_and_new_are_positive(self, provider):
        """Test that days to next full/new moon are positive."""
        phase_data = provider.get_moon_phase()

        if phase_data:
            assert phase_data.days_to_new >= 0
            assert phase_data.days_to_full >= 0
            # One should be roughly half a month away
            assert (
                phase_data.days_to_new > 10
                or phase_data.days_to_full > 10
                or (phase_data.days_to_new + phase_data.days_to_full) > 20
            )
