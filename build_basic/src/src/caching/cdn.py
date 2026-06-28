# caching/cdn.py – CDN provider integration for cache purging and headers
import os
import requests
import json
from typing import Optional, List

class CDNProvider:
    def __init__(self):
        self.provider = os.environ.get("CDN_PROVIDER", "none").lower()
        self.cloudflare_zone = os.environ.get("CLOUDFLARE_ZONE_ID", "")
        self.cloudflare_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        self.cloudfront_distribution = os.environ.get("CLOUDFRONT_DISTRIBUTION_ID", "")
    
    def purge_urls(self, urls: List[str]) -> bool:
        if self.provider == "cloudflare":
            return self._purge_cloudflare(urls)
        elif self.provider == "cloudfront":
            return self._purge_cloudfront(urls)
        else:
            return False
    
    def _purge_cloudflare(self, urls: List[str]) -> bool:
        if not self.cloudflare_zone or not self.cloudflare_token:
            return False
        headers = {
            "Authorization": f"Bearer {self.cloudflare_token}",
            "Content-Type": "application/json"
        }
        data = {"files": urls}
        url = f"https://api.cloudflare.com/client/v4/zones/{self.cloudflare_zone}/purge_cache"
        try:
            resp = requests.post(url, headers=headers, json=data)
            return resp.status_code == 200 and resp.json().get("success", False)
        except:
            return False
    
    def _purge_cloudfront(self, urls: List[str]) -> bool:
        if not self.cloudfront_distribution:
            return False
        # AWS CloudFront invalidation (simplified)
        import boto3
        try:
            client = boto3.client('cloudfront')
            invalidation = client.create_invalidation(
                DistributionId=self.cloudfront_distribution,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(urls),
                        'Items': urls
                    },
                    'CallerReference': str(int(time.time()))
                }
            )
            return True
        except:
            return False
    
    def get_cache_headers(self, max_age: int = 3600, stale_while_revalidate: int = 86400) -> dict:
        """Return Cache‑Control headers for edge caching"""
        return {
            "Cache-Control": f"public, max-age={max_age}, stale-while-revalidate={stale_while_revalidate}",
            "CDN-Cache-Control": f"max-age={max_age}",
            "CloudFront-Cache-Control": f"max-age={max_age}"
        }

# Global instance
_cdn = None
def get_cdn():
    global _cdn
    if _cdn is None:
        _cdn = CDNProvider()
    return _cdn
