"""
Google Places API integration for venue search.
Documentation: https://developers.google.com/maps/documentation/places/web-service
"""
import httpx
from typing import List, Optional, Dict, Any
from utils.helpers import get_env_variable, get_logger, generate_google_maps_url
from utils.schemas import VenueResult

logger = get_logger("PlacesAPI")


class PlacesAPIService:
    """Service for interacting with Google Places API"""

    def __init__(self):
        self.api_key = get_env_variable("GOOGLE_PLACES_API_KEY", required=False, default="demo_mode")
        # NEW Places API endpoint (not legacy)
        self.base_url = "https://places.googleapis.com/v1"
        self.client = httpx.Client(timeout=30.0)
        # Check if demo mode
        self.demo_mode = (self.api_key == "demo_mode_placeholder" or self.api_key == "demo_mode" or not self.api_key)
        if self.demo_mode:
            logger.info("📝 Using DEMO venues (Google Places API not configured)")
        else:
            logger.info("🎉 Using REAL Google Places API (New)!")

    def search_venues(
        self,
        query: str,
        latitude: float,
        longitude: float,
        radius: int = 3000,
        venue_type: str = "restaurant",
        max_results: int = 5
    ) -> List[VenueResult]:
        """
        Search for venues near a location.

        Args:
            query: Search query (e.g., "vegetarian restaurants")
            latitude: Latitude of search center
            longitude: Longitude of search center
            radius: Search radius in meters
            venue_type: Type of venue (restaurant, cafe, bar, etc.)
            max_results: Maximum number of results to return

        Returns:
            List of VenueResult objects
        """
        logger.info(f"Searching venues: query='{query}', lat={latitude}, lon={longitude}")

        # If in demo mode, return sample venues
        if self.demo_mode:
            logger.info("Demo mode active - returning sample venues")
            return self._get_demo_venues(query, latitude, longitude, max_results)

        # NEW Places API - Text Search
        url = f"{self.base_url}/places:searchText"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.currentOpeningHours,places.internationalPhoneNumber,places.websiteUri,places.photos,places.types,places.accessibilityOptions,places.id,places.location"
        }

        body = {
            "textQuery": f"{query} {venue_type}",
            "locationBias": {
                "circle": {
                    "center": {
                        "latitude": latitude,
                        "longitude": longitude
                    },
                    "radius": float(radius)
                }
            },
            "maxResultCount": max_results
        }

        try:
            response = self.client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

            venues = []
            for place in data.get("places", []):
                venue = self._parse_place_new_api(place)
                if venue:
                    venues.append(venue)

            logger.info(f"Found {len(venues)} venues")
            return venues

        except Exception as e:
            logger.error(f"Error searching venues: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response: {e.response.text if hasattr(e.response, 'text') else str(e.response)}")
            return []

    def get_place_details(self, place_id: str) -> Optional[VenueResult]:
        """
        Get detailed information about a specific place.

        Args:
            place_id: Google Places place_id

        Returns:
            VenueResult with detailed information
        """
        logger.info(f"Fetching place details: place_id={place_id}")

        url = f"{self.base_url}/details/json"
        params = {
            "key": self.api_key,
            "place_id": place_id,
            "fields": "name,formatted_address,rating,price_level,opening_hours,formatted_phone_number,website,photos,types,wheelchair_accessible_entrance"
        }

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                logger.error(f"Place details error: {data.get('status')}")
                return None

            place = data.get("result", {})
            return self._parse_place(place, detailed=True)

        except Exception as e:
            logger.error(f"Error fetching place details: {str(e)}")
            return None

    def _parse_place_new_api(self, place: Dict[str, Any]) -> Optional[VenueResult]:
        """Parse NEW Google Places API response into VenueResult"""
        try:
            # Extract basic info
            name = place.get("displayName", {}).get("text", "Unknown")
            address = place.get("formattedAddress", "Address not available")
            rating = place.get("rating")

            # Price level (convert from string like "PRICE_LEVEL_MODERATE" to int)
            price_level_str = place.get("priceLevel", "")
            price_level_map = {
                "PRICE_LEVEL_FREE": 0,
                "PRICE_LEVEL_INEXPENSIVE": 1,
                "PRICE_LEVEL_MODERATE": 2,
                "PRICE_LEVEL_EXPENSIVE": 3,
                "PRICE_LEVEL_VERY_EXPENSIVE": 4
            }
            price_level = price_level_map.get(price_level_str)

            # Opening hours
            opening_hours = None
            open_now = None
            current_hours = place.get("currentOpeningHours", {})
            if current_hours:
                open_now = current_hours.get("openNow")
                weekday_descriptions = current_hours.get("weekdayDescriptions", [])
                if weekday_descriptions:
                    opening_hours = weekday_descriptions

            # Contact info
            phone = place.get("internationalPhoneNumber")
            website = place.get("websiteUri")

            # Generate Google Maps URL
            place_id = place.get("id")
            location = place.get("location", {})
            lat = location.get("latitude")
            lon = location.get("longitude")

            google_maps_url = None
            if lat and lon:
                google_maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}&query_place_id={place_id}"
            elif place_id:
                google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"

            # Photos
            photos = []
            if "photos" in place:
                for photo in place["photos"][:3]:  # Get up to 3 photos
                    photo_name = photo.get("name")
                    if photo_name:
                        # NEW API uses photo names like "places/ChIJ.../photos/..."
                        photo_url = f"https://places.googleapis.com/v1/{photo_name}/media?maxHeightPx=400&maxWidthPx=400&key={self.api_key}"
                        photos.append(photo_url)

            # Cuisine type (from types)
            cuisine_type = None
            types = place.get("types", [])
            cuisine_keywords = ["restaurant", "cafe", "bar", "bakery", "food"]
            for t in types:
                if t in cuisine_keywords:
                    cuisine_type = t.replace("_", " ").title()
                    break

            # Accessibility
            wheelchair_accessible = None
            accessibility = place.get("accessibilityOptions", {})
            if accessibility:
                wheelchair_accessible = accessibility.get("wheelchairAccessibleEntrance")

            return VenueResult(
                name=name,
                address=address,
                rating=rating,
                price_level=price_level,
                open_now=open_now,
                opening_hours=opening_hours,
                phone=phone,
                website=website,
                google_maps_url=google_maps_url,
                photos=photos,
                cuisine_type=cuisine_type,
                wheelchair_accessible=wheelchair_accessible
            )

        except Exception as e:
            logger.error(f"Error parsing place data (NEW API): {str(e)}")
            return None

    def _parse_place(self, place: Dict[str, Any], detailed: bool = False) -> Optional[VenueResult]:
        """Parse Google Places API response into VenueResult"""
        try:
            # Extract basic info
            name = place.get("name", "Unknown")
            address = place.get("formatted_address") or place.get("vicinity", "Address not available")
            rating = place.get("rating")
            price_level = place.get("price_level")

            # Opening hours
            opening_hours = None
            open_now = None
            if "opening_hours" in place:
                open_now = place["opening_hours"].get("open_now")
                if detailed:
                    opening_hours = place["opening_hours"].get("weekday_text", [])

            # Contact info
            phone = place.get("formatted_phone_number")
            website = place.get("website")

            # Generate Google Maps URL
            place_id = place.get("place_id")
            google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None

            # Photos
            photos = []
            if "photos" in place:
                for photo in place["photos"][:3]:  # Get up to 3 photos
                    photo_reference = photo.get("photo_reference")
                    if photo_reference:
                        photo_url = f"{self.base_url}/photo?maxwidth=400&photo_reference={photo_reference}&key={self.api_key}"
                        photos.append(photo_url)

            # Cuisine type (from types)
            cuisine_type = None
            types = place.get("types", [])
            cuisine_keywords = ["restaurant", "cafe", "bar", "bakery", "food"]
            for t in types:
                if t in cuisine_keywords:
                    cuisine_type = t.replace("_", " ").title()
                    break

            # Accessibility
            wheelchair_accessible = place.get("wheelchair_accessible_entrance")

            return VenueResult(
                name=name,
                address=address,
                rating=rating,
                price_level=price_level,
                open_now=open_now,
                opening_hours=opening_hours,
                phone=phone,
                website=website,
                google_maps_url=google_maps_url,
                photos=photos,
                cuisine_type=cuisine_type,
                wheelchair_accessible=wheelchair_accessible
            )

        except Exception as e:
            logger.error(f"Error parsing place data: {str(e)}")
            return None

    def _get_demo_venues(self, query: str, latitude: float, longitude: float, max_results: int) -> List[VenueResult]:
        """Return demo venues when Google Places API is not available"""
        # Determine city based on coordinates
        city = "City"
        if 18.5 < latitude < 19.5 and 72.5 < longitude < 73.5:
            city = "Mumbai"
        elif 12.5 < latitude < 13.5 and 77.0 < longitude < 78.0:
            city = "Bangalore"
        elif 18.3 < latitude < 18.7 and 73.5 < longitude < 74.0:
            city = "Pune"

        venues = [
            VenueResult(
                name=f"Sample Restaurant 1 - {city}",
                address=f"123 Main Street, {city}",
                rating=4.5,
                price_level=2,
                open_now=True,
                opening_hours=["Monday-Sunday: 11:00 AM – 11:00 PM"],
                phone="+91-1234567890",
                website=f"https://example.com/restaurant1",
                google_maps_url=f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}",
                photos=["https://images.unsplash.com/photo-1517248135467-4c7edcad34c4"],
                cuisine_type="Indian Vegetarian",
                wheelchair_accessible=True
            ),
            VenueResult(
                name=f"Demo Cafe - {city}",
                address=f"456 Park Avenue, {city}",
                rating=4.3,
                price_level=2,
                open_now=True,
                opening_hours=["Monday-Sunday: 10:00 AM – 10:00 PM"],
                phone="+91-9876543210",
                website=f"https://example.com/cafe",
                google_maps_url=f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}",
                photos=["https://images.unsplash.com/photo-1554118811-1e0d58224f24"],
                cuisine_type="Cafe",
                wheelchair_accessible=True
            ),
            VenueResult(
                name=f"Sample Bistro - {city}",
                address=f"789 Garden Road, {city}",
                rating=4.7,
                price_level=3,
                open_now=True,
                opening_hours=["Monday-Sunday: 12:00 PM – 11:00 PM"],
                phone="+91-5555555555",
                website=f"https://example.com/bistro",
                google_maps_url=f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}",
                photos=["https://images.unsplash.com/photo-1592861956120-e524fc739696"],
                cuisine_type="Continental",
                wheelchair_accessible=False
            ),
        ]

        return venues[:max_results]

    def __del__(self):
        """Cleanup HTTP client"""
        if hasattr(self, 'client'):
            self.client.close()
