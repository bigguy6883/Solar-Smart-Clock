"""Solar data provider using astral library."""

import datetime
import logging
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun, elevation, azimuth, golden_hour, twilight, SunDirection

logger = logging.getLogger(__name__)


@dataclass
class SunTimes:
    """Sun event times for a day."""
    dawn: datetime.datetime
    sunrise: datetime.datetime
    noon: datetime.datetime
    sunset: datetime.datetime
    dusk: datetime.datetime


@dataclass
class GoldenHour:
    """Golden hour time range."""
    start: datetime.datetime
    end: datetime.datetime


@dataclass
class SolarPosition:
    """Current sun position in the sky."""
    elevation: float  # Degrees above horizon (negative = below)
    azimuth: float    # Degrees from north (0-360)


class SolarProvider:
    """
    Provides solar calculation data.

    Uses the astral library for sunrise/sunset, solar position,
    golden hour, and twilight calculations.
    """

    def __init__(
        self,
        name: str,
        region: str,
        timezone: str,
        latitude: float,
        longitude: float,
    ):
        """
        Initialize solar provider.

        Args:
            name: Location name
            region: Region/country
            timezone: Timezone string (e.g., "America/New_York")
            latitude: Location latitude
            longitude: Location longitude
        """
        self.location = LocationInfo(
            name=name,
            region=region,
            timezone=timezone,
            latitude=latitude,
            longitude=longitude,
        )
        self.tz = ZoneInfo(timezone)

    def get_sun_times(self, date: Optional[datetime.date] = None) -> Optional[SunTimes]:
        """
        Get sun event times for a date.

        Args:
            date: Date to get times for (default: today)

        Returns:
            SunTimes with dawn, sunrise, noon, sunset, dusk
        """
        if date is None:
            date = datetime.date.today()

        try:
            s = sun(self.location.observer, date=date, tzinfo=self.location.timezone)
            return SunTimes(
                dawn=s["dawn"],
                sunrise=s["sunrise"],
                noon=s["noon"],
                sunset=s["sunset"],
                dusk=s["dusk"],
            )
        except ValueError as e:
            # Can happen at extreme latitudes (polar day/night)
            logger.warning(f"Could not calculate sun times for {date}: {e}")
            return None
        except KeyError as e:
            logger.error(f"Missing sun time data: {e}")
            return None

    def get_solar_position(
        self, dt: Optional[datetime.datetime] = None
    ) -> Optional[SolarPosition]:
        """
        Get current sun position.

        Args:
            dt: Datetime to calculate for (default: now)

        Returns:
            SolarPosition with elevation and azimuth
        """
        if dt is None:
            dt = datetime.datetime.now(datetime.timezone.utc)

        try:
            elev = elevation(self.location.observer, dt)
            azim = azimuth(self.location.observer, dt)
            return SolarPosition(elevation=elev, azimuth=azim)
        except ValueError as e:
            logger.warning(f"Could not calculate solar position: {e}")
            return None

    def get_golden_hour(
        self, date: Optional[datetime.date] = None
    ) -> tuple[Optional[GoldenHour], Optional[GoldenHour]]:
        """
        Get morning and evening golden hour times.

        Uses astral library's golden_hour() for accurate calculation
        based on sun elevation (typically -4 to +6 degrees).

        Args:
            date: Date to get times for (default: today)

        Returns:
            Tuple of (morning_golden_hour, evening_golden_hour)
        """
        if date is None:
            date = datetime.date.today()

        morning = None
        evening = None

        try:
            # Morning golden hour (sun rising through golden zone)
            morning_times = golden_hour(
                self.location.observer, date,
                direction=SunDirection.RISING,
                tzinfo=self.location.timezone
            )
            if morning_times:
                morning = GoldenHour(start=morning_times[0], end=morning_times[1])
        except ValueError as e:
            logger.debug(f"Could not calculate morning golden hour: {e}")

        try:
            # Evening golden hour (sun setting through golden zone)
            evening_times = golden_hour(
                self.location.observer, date,
                direction=SunDirection.SETTING,
                tzinfo=self.location.timezone
            )
            if evening_times:
                evening = GoldenHour(start=evening_times[0], end=evening_times[1])
        except ValueError as e:
            logger.debug(f"Could not calculate evening golden hour: {e}")

        return morning, evening

    def get_twilight_times(
        self, date: Optional[datetime.date] = None
    ) -> Optional[tuple[datetime.datetime, datetime.datetime]]:
        """
        Get civil twilight times.

        Args:
            date: Date to get times for (default: today)

        Returns:
            Tuple of (dawn_twilight, dusk_twilight)
        """
        if date is None:
            date = datetime.date.today()

        try:
            dawn, dusk = twilight(
                self.location.observer, date, tzinfo=self.location.timezone
            )
            return dawn, dusk
        except ValueError as e:
            logger.warning(f"Could not calculate twilight for {date}: {e}")
            return None

    def get_day_length(self, date: Optional[datetime.date] = None) -> Optional[float]:
        """
        Get day length in hours.

        Args:
            date: Date to calculate for (default: today)

        Returns:
            Day length in hours, or None if unavailable
        """
        sun_times = self.get_sun_times(date)
        if sun_times is None:
            return None

        if sun_times.sunrise and sun_times.sunset:
            delta = sun_times.sunset - sun_times.sunrise
            return delta.total_seconds() / 3600

        return None

    def get_day_length_change(self) -> Optional[float]:
        """
        Get day length change from yesterday.

        Returns:
            Change in minutes (positive = longer days)
        """
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        today_length = self.get_day_length(today)
        yesterday_length = self.get_day_length(yesterday)

        if today_length is not None and yesterday_length is not None:
            return (today_length - yesterday_length) * 60  # Convert to minutes

        return None

    def get_next_solar_event(self) -> Optional[tuple[str, datetime.datetime]]:
        """
        Get the next upcoming solar event.

        Returns:
            Tuple of (event_name, event_time) for dawn, sunrise, sunset, or dusk
        """
        now = datetime.datetime.now(self.tz)
        sun_times = self.get_sun_times(now.date())

        if sun_times is None:
            return None

        events = [
            ("Dawn", sun_times.dawn),
            ("Sunrise", sun_times.sunrise),
            ("Sunset", sun_times.sunset),
            ("Dusk", sun_times.dusk),
        ]

        for name, event_time in events:
            if event_time and event_time > now:
                return name, event_time

        # All today's events passed, get tomorrow's dawn
        tomorrow = now.date() + datetime.timedelta(days=1)
        tomorrow_times = self.get_sun_times(tomorrow)
        if tomorrow_times and tomorrow_times.dawn:
            return "Dawn", tomorrow_times.dawn

        return None
