from .api.capabilities import NODE_PREFIX
from .nodes import (
    NanoBanana25Node,
    NanoBanana31Node,
    NanoBananaClientNode,
    NanoBananaProNode,
)


def _node_name(label):
    return f"{NODE_PREFIX} {label}"


NODE_CLASS_MAPPINGS = {
    _node_name("Client"): NanoBananaClientNode,
    _node_name("Nano Banana"): NanoBanana25Node,
    _node_name("Nano Banana 2"): NanoBanana31Node,
    _node_name("Nano Banana Pro"): NanoBananaProNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {key: key for key in NODE_CLASS_MAPPINGS}

