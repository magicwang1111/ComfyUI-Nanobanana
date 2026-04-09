import httpx

from .exceptions import NanoBananaAPIError


class Client:
    def __init__(self, api_key, timeout=60, base_url="https://generativelanguage.googleapis.com"):
        api_key = (api_key or "").strip()
        if not api_key:
            raise ValueError("api_key is required.")

        self.api_key = api_key
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        timeout_config = httpx.Timeout(connect=10.0, read=timeout, write=timeout, pool=timeout)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_config,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
        )

    def request(self, method, path, **kwargs):
        if "json" in kwargs and isinstance(kwargs["json"], dict):
            print(f"[ComfyUI-Nanobanana] {method} {path} payload keys={list(kwargs['json'].keys())}")

        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"Gemini API request timed out after {self.timeout}s while waiting for {method} {path}."
            ) from exc
        except httpx.HTTPError as exc:
            raise ConnectionError(f"Gemini API request failed for {method} {path}: {exc}") from exc

        if response.status_code != 200:
            raise NanoBananaAPIError.from_response(response)

        return response.json()

    def generate_content(self, model_name, payload):
        return self.request("POST", f"/v1beta/models/{model_name}:generateContent", json=payload)

    def close(self):
        self._client.close()

