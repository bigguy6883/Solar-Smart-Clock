"""Lunar data provider using ephem library."""

import datetime
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import ephem (optional dependency)
try:
    import ephem
    EPHEM_AVAILABLE = True
except ImportError:
    EPHEM_AVAILABLE = False
    logger.info("ephem library not available - lunar features disabled")


@dataclass
class MoonPhase:
    """Moon phase data."""
    phase: float           # 0-1 (0=new, 0.5=full, 1=new)
    illumination: float    # 0-100 percentage
    phase_name: str        # "New Moon", "Waxing Crescent", etc.
    next_new: datetime.date
    next_full: datetime.date
    days_to_new: int
    days_to_full: int


@dataclass
class MoonTimes:
    """Moon rise and set times."""
    moonrise: Optional[datetime.datetime]
    moonset: Optional[datetime.datetime]


@dataclass
class SolsticeEquinox:
    """Solstice and equinox dates for a year."""
    spring_equinox: datetime.date
    summer_solstice: datetime.date
    fall_equinox: datetime.date
    winter_solstice: datetime.date


@dataclass
class AnalemmaPoint:
    """Sun position data for analemma calculation."""
    elevation: float
    equation_of_time: float  # Minutes early/late
    date: datetime.date


class LunarProvider:
    """
    Provides lunar and astronomical calculations.

    Uses the ephem library for accurate moon phase, solstice/equinox,
    and analemma calculations.
    """

    def __init__(self, latitude: float, longitude: float):
        """
        Initialize lunar provider.

        Args:
            latitude: Location latitude
            longitude: Location longitude
        """
        self.latitude = latitude
        self.longitude = longitude

        if EPHEM_AVAILABLE:
            self._observer = ephem.Observer()
            self._observer.lat = str(latitude)
            self._observer.lon = str(longitude)

    @property
    def available(self) -> bool:
        """Check if ephem library is available."""
        return EPHEM_AVAILABLE

    def get_moon_phase(self) -> Optional[MoonPhase]:
        """
        Get current moon phase data.

        Returns:
            MoonPhase with illumination, phase name, and upcoming dates
        """
        if not EPHEM_AVAILABLE:
            return None

        try:
            now = datetime.datetime.now()
            moon = ephem.Moon()
            moon.compute(now)

            illumination = moon.phase  # Percentage 0-100

            # Get next and previous new moon dates
            next_new = ephem.next_new_moon(now)
            next_full = ephem.next_full_moon(now)
            prev_new = ephem.previous_new_moon(now)

            # Calculate lunation (cycle position 0-1) from days since last new moon
            # Synodic month is ~29.53 days
            synodic_month = 29.530588853
            days_since_new = ephem.Date(now) - prev_new
            lunation = (days_since_new / synodic_month) % 1.0

            next_new_date = ephem.Date(next_new).datetime().date()
            next_full_date = ephem.Date(next_full).datetime().date()

            days_to_new = (next_new_date - now.date()).days
            days_to_full = (next_full_date - now.date()).days

            phase_name = self._get_phase_name(lunation)

            return MoonPhase(
                phase=lunation,
                illumination=illumination,
                phase_name=phase_name,
                next_new=next_new_date,
                next_full=next_full_date,
                days_to_new=days_to_new,
                days_to_full=days_to_full,
            )

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to calculate moon phase: {e}")
            return None

    def get_moon_times(
        self, date: Optional[datetime.date] = None
    ) -> Optional[MoonTimes]:
        """
        Get moonrise and moonset times.

        Args:
            date: Date to get times for (default: today)

        Returns:
            MoonTimes with rise and set times
        """
        if not EPHEM_AVAILABLE:
            return None

        if date is None:
            date = datetime.date.today()

        try:
            observer = ephem.Observer()
            observer.lat = str(self.latitude)
            observer.lon = str(self.longitude)
            observer.date = date.strftime("%Y/%m/%d")

            moon = ephem.Moon()

            try:
                rise = observer.next_rising(moon)
                moonrise = ephem.Date(rise).datetime()
            except ephem.NeverUpError:
                moonrise = None
            except ephem.AlwaysUpError:
                moonrise = None

            try:
                set_time = observer.next_setting(moon)
                moonset = ephem.Date(set_time).datetime()
            except ephem.NeverUpError:
                moonset = None
            except ephem.AlwaysUpError:
                moonset = None

            return MoonTimes(moonrise=moonrise, moonset=moonset)

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to calculate moon times: {e}")
            return None

    def get_solstice_equinox(self, year: int) -> SolsticeEquinox:
        """
        Get solstice and equinox dates for a year.

        Args:
            year: Year to calculate for

        Returns:
            SolsticeEquinox with all four dates
        """
        if not EPHEM_AVAILABLE:
            # Return approximate dates as fallback
            return SolsticeEquinox(
                spring_equinox=datetime.date(year, 3, 20),
                summer_solstice=datetime.date(year, 6, 21),
                fall_equinox=datetime.date(year, 9, 22),
                winter_solstice=datetime.date(year, 12, 21),
            )

        try:
            start = f"{year}/1/1"

            spring = ephem.next_vernal_equinox(start)
            summer = ephem.next_summer_solstice(start)
            fall = ephem.next_autumnal_equinox(start)
            winter = ephem.next_winter_solstice(start)

            return SolsticeEquinox(
                spring_equinox=ephem.Date(spring).datetime().date(),
                summer_solstice=ephem.Date(summer).datetime().date(),
                fall_equinox=ephem.Date(fall).datetime().date(),
                winter_solstice=ephem.Date(winter).datetime().date(),
            )

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to calculate solstice/equinox: {e}")
            return SolsticeEquinox(
                spring_equinox=datetime.date(year, 3, 20),
                summer_solstice=datetime.date(year, 6, 21),
                fall_equinox=datetime.date(year, 9, 22),
                winter_solstice=datetime.date(year, 12, 21),
            )

    def get_equation_of_time(
        self, date: Optional[datetime.date] = None
    ) -> Optional[float]:
        """
        Get equation of time (difference between solar and clock time).

        Args:
            date: Date to calculate for (default: today)

        Returns:
            Minutes that sun is early (positive) or late (negative)
        """
        if not EPHEM_AVAILABLE:
            return None

        if date is None:
            date = datetime.date.today()

        try:
            # Set up observer at prime meridian for standard calculation
            observer = ephem.Observer()
            observer.lat = '0'
            observer.lon = '0'
            observer.elevation = 0
            observer.pressure = 0  # No atmospheric refraction

            # Set date to noon UTC
            dt = datetime.datetime(date.year, date.month, date.day, 12, 0)
            observer.date = dt

            # Find when sun transits (crosses meridian)
            sun = ephem.Sun()
            transit = observer.next_transit(sun)

            # Equation of time = 12:00 - transit time (in minutes)
            # Positive = sun is early (ahead of clock), negative = sun is late
            transit_dt = ephem.Date(transit).datetime()
            eot_minutes = (12 * 60) - (transit_dt.hour * 60 + transit_dt.minute + transit_dt.second / 60)

            return eot_minutes

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to calculate equation of time: {e}")
            return None

    def get_analemma_data(self) -> list[AnalemmaPoint]:
        """
        Get analemma data points for the year.

        Calculates sun position at solar noon (transit) for each sample date,
        giving the characteristic figure-8 pattern.

        Returns:
            List of AnalemmaPoint for each week of the year
        """
        if not EPHEM_AVAILABLE:
            return []

        points = []
        year = datetime.date.today().year

        try:
            observer = ephem.Observer()
            observer.lat = str(self.latitude)
            observer.lon = str(self.longitude)
            observer.pressure = 0  # No refraction for consistency

            # Sample every 7 days
            date = datetime.date(year, 1, 1)
            while date.year == year:
                # Set observer to morning of this date
                observer.date = datetime.datetime(date.year, date.month, date.day, 6, 0)

                sun = ephem.Sun()
                # Find solar noon (transit) for this date
                transit = observer.next_transit(sun)
                observer.date = transit
                sun.compute(observer)

                # Elevation at solar noon
                elevation = float(sun.alt) * 180 / ephem.pi
                eot = self.get_equation_of_time(date) or 0

                points.append(
                    AnalemmaPoint(
                        elevation=elevation,
                        equation_of_time=eot,
                        date=date,
                    )
                )

                date += datetime.timedelta(days=7)

            return points

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to calculate analemma: {e}")
            return []

    @staticmethod
    def _get_phase_name(phase: float) -> str:
        """
        Get moon phase name from phase value.

        Args:
            phase: Phase value 0-1 (0=new, 0.5=full)

        Returns:
            Human-readable phase name
        """
        if phase < 0.03:
            return "New Moon"
        elif phase < 0.22:
            return "Waxing Crescent"
        elif phase < 0.28:
            return "First Quarter"
        elif phase < 0.47:
            return "Waxing Gibbous"
        elif phase < 0.53:
            return "Full Moon"
        elif phase < 0.72:
            return "Waning Gibbous"
        elif phase < 0.78:
            return "Last Quarter"
        elif phase < 0.97:
            return "Waning Crescent"
        else:
            return "New Moon"
