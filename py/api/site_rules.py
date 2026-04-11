from urllib.parse import urlparse


AIHUBMIX_RULE_ID = "aihubmix"
AIHUBMIX_HOSTS = {"aihubmix.com", "api.aihubmix.com"}
AIHUBMIX_THINKING_LEVEL_BLOCKLIST = {"gemini-3-pro-image-preview"}


def get_site_rule_id(base_url):
    if not isinstance(base_url, str) or not base_url.strip():
        return None

    hostname = (urlparse(base_url.strip()).hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    if hostname in AIHUBMIX_HOSTS:
        return AIHUBMIX_RULE_ID

    return None


def apply_generation_payload_rules(base_url, canonical_model_name, request_model_name, payload):
    if get_site_rule_id(base_url) != AIHUBMIX_RULE_ID:
        return payload

    if canonical_model_name not in AIHUBMIX_THINKING_LEVEL_BLOCKLIST and request_model_name not in AIHUBMIX_THINKING_LEVEL_BLOCKLIST:
        return payload

    generation_config = payload.get("generationConfig")
    if not isinstance(generation_config, dict):
        return payload

    thinking_config = generation_config.get("thinkingConfig")
    if not isinstance(thinking_config, dict) or "thinkingLevel" not in thinking_config:
        return payload

    next_thinking_config = dict(thinking_config)
    next_thinking_config.pop("thinkingLevel", None)

    next_generation_config = dict(generation_config)
    if next_thinking_config:
        next_generation_config["thinkingConfig"] = next_thinking_config
    else:
        next_generation_config.pop("thinkingConfig", None)

    next_payload = dict(payload)
    next_payload["generationConfig"] = next_generation_config
    return next_payload
