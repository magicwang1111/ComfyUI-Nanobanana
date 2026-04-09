class NanoBananaAPIError(Exception):
    def __init__(self, status_code, status, message, details=None, response_body=None):
        self.status_code = status_code
        self.status = status
        self.message = message or "Unknown Gemini API error"
        self.details = details or []
        self.response_body = response_body
        super().__init__(self._format_message())

    def _format_message(self):
        status_label = f" {self.status}" if self.status else ""
        return f"Gemini API request failed ({self.status_code}{status_label}): {self.message}"

    @classmethod
    def from_response(cls, response):
        try:
            payload = response.json()
        except Exception:
            payload = {}

        error_payload = payload.get("error", {}) if isinstance(payload, dict) else {}
        return cls(
            status_code=response.status_code,
            status=error_payload.get("status"),
            message=error_payload.get("message") or response.text,
            details=error_payload.get("details"),
            response_body=payload,
        )
