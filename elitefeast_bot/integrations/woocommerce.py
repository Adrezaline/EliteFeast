from dataclasses import dataclass
from typing import Dict, List

import httpx


@dataclass
class WooCommerceClient:
    base_url: str
    consumer_key: str
    consumer_secret: str

    async def products(self, page: int = 1, per_page: int = 100) -> List[Dict]:
        url = f"{self.base_url.rstrip('/')}/wp-json/wc/v3/products"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                url,
                params={
                    "consumer_key": self.consumer_key,
                    "consumer_secret": self.consumer_secret,
                    "page": page,
                    "per_page": per_page,
                    "status": "publish",
                },
            )
            response.raise_for_status()
            return response.json()
