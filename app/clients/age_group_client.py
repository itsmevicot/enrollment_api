from typing import List
import httpx

class AgeGroupClient:
    """
    Wraps calls to the Age‑Groups API.
    """
    def __init__(self, base_url: str, http_client: httpx.Client):
        self.base_url = base_url.rstrip("/")
        self.http = http_client

    def list(self) -> List[dict]:
        resp = self.http.get(f"{self.base_url}/age-groups/")
        resp.raise_for_status()
        return resp.json()
