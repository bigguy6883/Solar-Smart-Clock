"""Solar data provider using astral library."""

import datetime
import logging
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun, elevation, azimuth, golden_hour, twilight

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

        Golden hour is approximately 30 minutes before/after sunrise/sunset.

        Args:
            date: Date to get times for (default: today)

        Returns:
            Tuple of (morning_golden_hour, evening_golden_hour)
        """
        sun_times = self.get_sun_times(date)
        if sun_times is None:
            return None, None

        morning = None
        evening = None

        if sun_times.sunrise:
            # Morning golden hour: sunrise to ~45 min after (sun rises through golden zone)
            morning = GoldenHour(
                start=sun_times.sunrise,
                end=sun_times.sunrise + datetime.timedelta(minutes=45),
            )

        if sun_times.sunset:
            # Evening golden hour: ~45 min before sunset to sunset
            evening = GoldenHour(
                start=sun_times.sunset - datetime.timedelta(minutes=45),
                end=sun_times.sunset,
            )

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
