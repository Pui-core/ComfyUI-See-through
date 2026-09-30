"""
ComfyUI-See-through: Anime Layer Decomposition from a Single Image

Wraps the See-through research project as ComfyUI custom nodes.
Paper: arxiv:2602.03749
"""
import traceback

WEB_DIRECTORY = "./web"

print("[ComfyUI-See-through] __init__.py loading...", flush=True)

try:
    from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
    from .detail_nodes import NODE_CLASS_MAPPINGS as DETAIL_CLASSES, NODE_DISPLAY_NAME_MAPPINGS as DETAIL_NAMES
    NODE_CLASS_MAPPINGS.update(DETAIL_CLASSES)
    NODE_DISPLAY_NAME_MAPPINGS.update(DETAIL_NAMES)
    print(f"[ComfyUI-See-through] Loaded {len(NODE_CLASS_MAPPINGS)} nodes: {list(NODE_CLASS_MAPPINGS.keys())}", flush=True)
except Exception as e:
    print(f"[ComfyUI-See-through] Failed to import nodes: {e}", flush=True)
    traceback.print_exc()
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
__version__ = "0.2.2"
