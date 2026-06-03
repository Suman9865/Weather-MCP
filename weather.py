"""
MCP Weather Server
Provides US weather alerts and forecasts via the National Weather Service API.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"
VALID_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}

# Shared HTTP client (connection pooling)
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Return the shared HTTP client, creating it if necessary."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/geo+json",
            },
            timeout=30.0,
        )
    return _http_client


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    client = _get_http_client()
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        logger.error("Timeout requesting %s", url)
    except httpx.HTTPStatusError as exc:
        logger.error("HTTP %s for %s", exc.response.status_code, url)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error requesting %s: %s", url, exc)
    return None


def format_alert(feature: dict[str, Any]) -> str:
    """Format an alert feature into a readable string."""
    props = feature.get("properties", {})
    return (
        f"Event: {props.get('event', 'Unknown')}\n"
        f"Area: {props.get('areaDesc', 'Unknown')}\n"
        f"Severity: {props.get('severity', 'Unknown')}\n"
        f"Description: {props.get('description', 'No description available')}\n"
        f"Instructions: {props.get('instruction', 'No specific instructions provided')}"
    )


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    state = state.upper().strip()
    if state not in VALID_US_STATES:
        return (
            f"Invalid state code '{state}'. "
            "Please provide a valid two-letter US state code (e.g. CA, NY)."
        )

    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return f"No active weather alerts for {state}."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location (must be a US location)
        longitude: Longitude of the location (must be a US location)
    """
    if not (-90.0 <= latitude <= 90.0):
        return "Invalid latitude. Must be between -90 and 90."
    if not (-180.0 <= longitude <= 180.0):
        return "Invalid longitude. Must be between -180 and 180."

    # NWS only covers the US (broad bounding box to include AK, HI, territories)
    if not ((17.0 <= latitude <= 72.0) and (-180.0 <= longitude <= -65.0)):
        return (
            "The National Weather Service API only covers US locations. "
            "Please provide coordinates within the United States."
        )

    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    try:
        forecast_url = points_data["properties"]["forecast"]
    except (KeyError, TypeError):
        return (
            "Unexpected response format from the NWS points API. "
            "The location may not be supported."
        )

    forecast_data = await make_nws_request(forecast_url)
    if not forecast_data:
        return "Unable to fetch detailed forecast."

    try:
        periods = forecast_data["properties"]["periods"]
    except (KeyError, TypeError):
        return "Unexpected response format from the NWS forecast API."

    forecasts: list[str] = []
    for period in periods[:5]:
        forecasts.append(
            f"{period.get('name', 'Unknown')}:\n"
            f"Temperature: {period.get('temperature', 'N/A')}°"
            f"{period.get('temperatureUnit', 'F')}\n"
            f"Wind: {period.get('windSpeed', 'N/A')} "
            f"{period.get('windDirection', '')}\n"
            f"Forecast: {period.get('detailedForecast', 'N/A')}"
        )

    return "\n---\n".join(forecasts)


def main() -> None:
    """Entry point — start the MCP server with stdio transport."""
    logger.info("Starting weather MCP server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()