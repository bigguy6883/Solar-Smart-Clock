"""The real /api/now JSON must render in every view of the page.

The JavaScript tests use a hand-written sample; this test feeds the page's
views the JSON that WebDataService actually builds, through Node.js, so a
renamed or missing field fails here instead of on a phone. Skipped when Node
is not installed.
"""

import json
import shutil
import subprocess
from unittest.mock import MagicMock

import pytest

from solar_clock.data.weather import AirQuality, CurrentWeather, DailyForecast
from solar_clock.web_api import WebDataService
from solar_clock.web_static import WEB_DIR

NODE = shutil.which("node")

RENDER_EVERY_VIEW = """
let text = "";
for await (const chunk of process.stdin) text += chunk;
const data = JSON.parse(text);
const { VIEWS } = await import(process.argv[1]);
const out = {};
for (const view of VIEWS) out[view.name] = view.render(data, new Date(data.generated_at));
process.stdout.write(JSON.stringify(out));
"""


def _weather():
    provider = MagicMock()
    provider.get_current_weather.return_value = CurrentWeather(
        temperature=64.5,
        feels_like=63.2,
        humidity=58,
        description="Scattered Clouds",
        wind_speed=7.4,
        wind_direction="WSW",
    )
    provider.get_forecast.return_value = [
        DailyForecast(date="2026-10-08", high_temp=66.1, low_temp=51.3, rain_chance=10),
        DailyForecast(date="2026-10-09", high_temp=61.0, low_temp=48.8, rain_chance=40),
        DailyForecast(date="2026-10-10", high_temp=58.4, low_temp=45.0, rain_chance=0),
    ]
    provider.get_air_quality.return_value = AirQuality(
        aqi=42,
        category="Good",
        pm25=10.1,
        pm10=18.4,
        o3=61.2,
        no2=12.7,
        so2=1.9,
        co=230.5,
        updated_at=1791485880.0,
    )
    return provider


@pytest.mark.skipif(NODE is None, reason="Node.js is not installed")
@pytest.mark.parametrize("weather", [_weather, lambda: None], ids=["weather", "no-key"])
def test_every_view_renders_the_real_api_response(sample_config, weather):
    service = WebDataService(
        sample_config, weather=weather(), theme_mode=lambda: "auto"
    )
    payload = json.dumps(service.build_now())
    views_module = (WEB_DIR / "js" / "views" / "index.js").as_uri()
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", RENDER_EVERY_VIEW, views_module],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    rendered = json.loads(result.stdout)
    assert rendered, "no views rendered"
    for name, html in rendered.items():
        assert html.strip(), f"{name} rendered nothing"
        for broken in ("undefined", "NaN", "Invalid Date"):
            assert broken not in html, f"{name} shows {broken!r}"
