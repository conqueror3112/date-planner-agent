"""
OpenWeatherMap API integration for weather forecasts.
Documentation: https://openweathermap.org/api
"""
import httpx
from typing import Optional
from datetime import datetime
from utils.helpers import get_env_variable, get_logger
from utils.schemas import WeatherResult

logger = get_logger("WeatherAPI")


class WeatherAPIService:
    """Service for interacting with OpenWeatherMap API"""

    def __init__(self):
        self.api_key = get_env_variable("OPENWEATHER_API_KEY", required=True)
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.client = httpx.Client(timeout=30.0)

    def get_forecast(
        self,
        latitude: float,
        longitude: float,
        target_datetime: Optional[str] = None
    ) -> Optional[WeatherResult]:
        """
        Get weather forecast for a location.

        Args:
            latitude: Latitude
            longitude: Longitude
            target_datetime: Target date/time (if None, gets current weather)

        Returns:
            WeatherResult object
        """
        logger.info(f"Fetching weather: lat={latitude}, lon={longitude}, datetime={target_datetime}")

        # Use current weather endpoint (upgrade to forecast for future dates in production)
        url = f"{self.base_url}/weather"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": self.api_key,
            "units": "metric"  # Celsius
        }

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            weather_result = self._parse_weather(data)
            logger.info(f"Weather fetched: {weather_result.condition}, {weather_result.temperature}°C")
            return weather_result

        except Exception as e:
            logger.error(f"Error fetching weather: {str(e)}")
            return None

    def _parse_weather(self, data: dict) -> WeatherResult:
        """Parse OpenWeatherMap API response into WeatherResult"""
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        rain = data.get("rain", {})

        temperature = main.get("temp", 0)
        feels_like = main.get("feels_like", temperature)
        humidity = main.get("humidity", 0)
        condition = weather.get("main", "Unknown")
        description = weather.get("description", "").capitalize()
        wind_speed = wind.get("speed", 0)

        # Rain probability (approximation based on rain data)
        rain_probability = None
        if rain:
            rain_probability = 80.0  # High probability if rain data present
        elif "rain" in condition.lower() or "drizzle" in description.lower():
            rain_probability = 60.0

        # Generate weather-based suggestion
        suggestion = self._generate_suggestion(temperature, condition, rain_probability)

        return WeatherResult(
            temperature=temperature,
            feels_like=feels_like,
            condition=condition,
            description=description,
            humidity=humidity,
            wind_speed=wind_speed,
            rain_probability=rain_probability,
            suggestion=suggestion
        )

    def _generate_suggestion(self, temperature: float, condition: str, rain_prob: Optional[float]) -> str:
        """Generate weather-based suggestion for the date"""
        suggestions = []

        # Temperature advice
        if temperature < 15:
            suggestions.append("Bring a jacket - it's quite cool")
        elif temperature < 20:
            suggestions.append("Wear a light sweater")
        elif temperature > 32:
            suggestions.append("Dress light - it's hot outside")
            suggestions.append("Choose an air-conditioned venue")

        # Rain advice
        if rain_prob and rain_prob > 50:
            suggestions.append("High chance of rain - carry an umbrella")
            suggestions.append("Consider indoor activities or venues with covered seating")
        elif "rain" in condition.lower():
            suggestions.append("Rain expected - plan for indoor activities")

        # Weather condition advice
        if "clear" in condition.lower() or "sunny" in condition.lower():
            suggestions.append("Perfect weather for outdoor dining")
        elif "cloud" in condition.lower():
            suggestions.append("Pleasant weather for a date")

        # Humidity advice
        # Note: humidity data available in main response

        return " | ".join(suggestions) if suggestions else "Weather looks good for your date"

    def __del__(self):
        """Cleanup HTTP client"""
        if hasattr(self, 'client'):
            self.client.close()
