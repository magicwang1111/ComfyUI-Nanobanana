import httpx

from .capabilities import AUTH_MODES, DEFAULT_AUTH_MODE, DEFAULT_BASE_URL, DEFAULT_SEND_SEED
from .exceptions import NanoBananaAPIError


def _build_timeout_config(timeout):
    return httpx.Timeout(connect=10.0, read=timeout, write=timeout, pool=timeout)


def _normalize_auth_mode(auth_mode):
    normalized = (auth_mode or DEFAULT_AUTH_MODE).strip().lower()
    if normalized not in AUTH_MODES:
        raise ValueError(f"auth_mode must be one of: {', '.join(AUTH_MODES)}.")
    return normalized


def _build_headers(api_key, auth_mode):
    headers = {"Content-Type": "application/json"}
    if auth_mode == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["x-goog-api-key"] = api_key
    return headers


class Client:
    def __init__(
        self,
        api_key,
        timeout=60,
        base_url=DEFAULT_BASE_URL,
        auth_mode=DEFAULT_AUTH_MODE,
        send_seed=DEFAULT_SEND_SEED,
    ):
        api_key = (api_key or "").strip()
        if not api_key:
            raise ValueError("api_key is required.")

        self.api_key = api_key
        self.timeout = timeout
        self.base_url = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
        self.auth_mode = self.normalize_auth_mode(auth_mode)
        self.send_seed = bool(send_seed)
        timeout_config = _build_timeout_config(timeout)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout_config,
            headers=self.build_headers(self.api_key, self.auth_mode),
        )

    @staticmethod
    def normalize_auth_mode(auth_mode):
        return _normalize_auth_mode(auth_mode)

    @staticmethod
    def build_headers(api_key, auth_mode):
        return _build_headers(api_key, auth_mode)

    def request(self, method, path, **kwargs):
        if "json" in kwargs and isinstance(kwargs["json"], dict):
            print(f"[ComfyUI-Nanobanana] {method} {path} payload keys={list(kwargs['json'].keys())}")

        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"API request timed out after {self.timeout}s while waiting for {method} {path}.") from exc
        except httpx.HTTPError as exc:
            raise ConnectionError(f"API request failed for {method} {path}: {exc}") from exc

        if response.status_code != 200:
            raise NanoBananaAPIError.from_response(response)

        return response.json()

    def generate_content(self, model_name, payload):
        return self.request("POST", f"/v1beta/models/{model_name}:generateContent", json=payload)

    def close(self):
        self._client.close()


class AsyncClient:
    def __init__(
        self,
        api_key,
        timeout=60,
        base_url=DEFAULT_BASE_URL,
        auth_mode=DEFAULT_AUTH_MODE,
        send_seed=DEFAULT_SEND_SEED,
    ):
        api_key = (api_key or "").strip()
        if not api_key:
            raise ValueError("api_key is required.")

        self.api_key = api_key
        self.timeout = timeout
        self.base_url = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
        self.auth_mode = self.normalize_auth_mode(auth_mode)
        self.send_seed = bool(send_seed)
        timeout_config = _build_timeout_config(timeout)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout_config,
            headers=self.build_headers(self.api_key, self.auth_mode),
        )

    @staticmethod
    def normalize_auth_mode(auth_mode):
        return _normalize_auth_mode(auth_mode)

    @staticmethod
    def build_headers(api_key, auth_mode):
        return _build_headers(api_key, auth_mode)

    async def request(self, method, path, **kwargs):
        if "json" in kwargs and isinstance(kwargs["json"], dict):
            print(f"[ComfyUI-Nanobanana] {method} {path} payload keys={list(kwargs['json'].keys())}")

        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"API request timed out after {self.timeout}s while waiting for {method} {path}.") from exc
        except httpx.HTTPError as exc:
            raise ConnectionError(f"API request failed for {method} {path}: {exc}") from exc

        if response.status_code != 200:
            raise NanoBananaAPIError.from_response(response)

        return response.json()

    async def generate_content(self, model_name, payload):
        return await self.request("POST", f"/v1beta/models/{model_name}:generateContent", json=payload)

    async def close(self):
        await self._client.aclose()
