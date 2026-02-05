"""
Unsplash API integration for venue images.
Documentation: https://unsplash.com/documentation
"""
import httpx
from typing import List, Optional
from utils.helpers import get_env_variable, get_logger
from utils.schemas import ImageResult

logger = get_logger("UnsplashAPI")


class UnsplashAPIService:
    """Service for interacting with Unsplash API"""

    def __init__(self):
        self.access_key = get_env_variable("UNSPLASH_ACCESS_KEY", required=True)
        self.base_url = "https://api.unsplash.com"
        self.client = httpx.Client(
            timeout=30.0,
            headers={"Authorization": f"Client-ID {self.access_key}"}
        )

    def search_images(
        self,
        query: str,
        count: int = 3,
        orientation: str = "landscape"
    ) -> List[ImageResult]:
        """
        Search for images on Unsplash.

        Args:
            query: Search query (e.g., "romantic restaurant")
            count: Number of images to return
            orientation: Image orientation (landscape, portrait, squarish)

        Returns:
            List of ImageResult objects
        """
        logger.info(f"Searching images: query='{query}', count={count}")

        url = f"{self.base_url}/search/photos"
        params = {
            "query": query,
            "per_page": count,
            "orientation": orientation
        }

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            images = []
            for result in data.get("results", []):
                image = self._parse_image(result)
                if image:
                    images.append(image)

            logger.info(f"Found {len(images)} images")
            return images

        except Exception as e:
            logger.error(f"Error searching images: {str(e)}")
            return []

    def _parse_image(self, data: dict) -> Optional[ImageResult]:
        """Parse Unsplash API response into ImageResult"""
        try:
            url = data.get("urls", {}).get("regular")
            photographer = data.get("user", {}).get("name", "Unknown")
            description = data.get("description") or data.get("alt_description")

            if not url:
                return None

            return ImageResult(
                url=url,
                photographer=photographer,
                description=description
            )

        except Exception as e:
            logger.error(f"Error parsing image data: {str(e)}")
            return None

    def __del__(self):
        """Cleanup HTTP client"""
        if hasattr(self, 'client'):
            self.client.close()
