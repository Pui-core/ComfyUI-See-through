"""ComfyUI nodes for optional SeeThrough fine-part refinement."""
import numpy as np
import torch

from .detail_parts import refine_parts, extract_mask


def preview(data):
    h, w = data["frame_size"]
    canvas = np.zeros((h, w, 3), np.float32)
    for part in sorted(data["tag2pinfo"].values(),
                       key=lambda p: p.get("depth_median", 1), reverse=True):
        img = part["img"]
        x, y = [int(v) for v in part.get("xyxy", [0, 0])[:2]]
        ph, pw = img.shape[:2]
        x0, y0, x1, y1 = max(0, x), max(0, y), min(w, x+pw), min(h, y+ph)
        if x1 <= x0 or y1 <= y0:
            continue
        rgba = img[y0-y:y1-y, x0-x:x1-x].astype(np.float32) / 255.0
        alpha = rgba[..., 3:4]
        canvas[y0:y1, x0:x1] = rgba[..., :3] * alpha + canvas[y0:y1, x0:x1] * (1-alpha)
    return torch.from_numpy(canvas).unsqueeze(0)


def inventory(data):
    lines = [f"{tag}: {p['img'].shape[1]}x{p['img'].shape[0]} at {p.get('xyxy', [0, 0])[:2]}"
             for tag, p in data["tag2pinfo"].items()]
    return "\n".join(lines + data.get("detail_report", []))


class SeeThrough_RefineDetails:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "parts": ("SEETHROUGH_PARTS",),
            "eye_highlights": ("BOOLEAN", {"default": True}),
            "hair_highlights": ("BOOLEAN", {"default": True}),
            "hair_locks": ("BOOLEAN", {"default": True}),
            "accessories": ("BOOLEAN", {"default": True}),
            "minimum_area": ("INT", {"default": 8, "min": 1, "max": 4096}),
            "highlight_contrast": ("FLOAT", {"default": .08, "min": .01, "max": .5, "step": .01}),
            "max_hair_locks": ("INT", {"default": 16, "min": 2, "max": 64}),
        }}

    RETURN_TYPES = ("SEETHROUGH_PARTS", "IMAGE", "STRING")
    RETURN_NAMES = ("parts", "preview", "part_names_and_report")
    FUNCTION = "refine"
    CATEGORY = "SeeThrough/Details"

    def refine(self, parts, **options):
        result = refine_parts(parts, **options)
        return result, preview(result), inventory(result)


class SeeThrough_ExtractDetailMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "parts": ("SEETHROUGH_PARTS",),
            "mask": ("MASK",),
            "source_part": ("STRING", {"default": "face"}),
            "new_part_name": ("STRING", {"default": "nose_detail"}),
            "threshold": ("FLOAT", {"default": .5, "min": 0, "max": 1, "step": .01}),
        }}

    RETURN_TYPES = ("SEETHROUGH_PARTS", "IMAGE", "STRING")
    RETURN_NAMES = ("parts", "preview", "part_names_and_report")
    FUNCTION = "extract"
    CATEGORY = "SeeThrough/Details"

    def extract(self, parts, mask, source_part, new_part_name, threshold=.5):
        if mask.ndim != 3 or mask.shape[0] != 1:
            raise ValueError("Use a single full-canvas mask (batch size 1)")
        result = extract_mask(parts, source_part, new_part_name,
                              mask[0].detach().cpu().numpy(), threshold)
        return result, preview(result), inventory(result)


class SeeThrough_EditDetail:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "parts": ("SEETHROUGH_PARTS",),
            "part_name": ("STRING", {"default": "irides-l_highlight_01"}),
            "brightness": ("FLOAT", {"default": 1., "min": 0., "max": 3., "step": .05}),
            "saturation": ("FLOAT", {"default": 1., "min": 0., "max": 3., "step": .05}),
        }}

    RETURN_TYPES = ("SEETHROUGH_PARTS", "IMAGE")
    RETURN_NAMES = ("parts", "preview")
    FUNCTION = "edit"
    CATEGORY = "SeeThrough/Details"

    def edit(self, parts, part_name, brightness=1., saturation=1.):
        if part_name not in parts["tag2pinfo"]:
            raise ValueError(f"Unknown part: {part_name}")
        result = dict(parts)
        result["tag2pinfo"] = dict(parts["tag2pinfo"])
        part = dict(parts["tag2pinfo"][part_name])
        img = part["img"].copy()
        rgb = img[..., :3].astype(np.float32)
        gray = (rgb * np.array([.2126, .7152, .0722], np.float32)).sum(axis=2, keepdims=True)
        img[..., :3] = np.clip(np.rint((gray + (rgb-gray)*saturation)*brightness), 0, 255).astype(np.uint8)
        part["img"] = img
        result["tag2pinfo"][part_name] = part
        return result, preview(result)


NODE_CLASS_MAPPINGS = {
    "SeeThrough_RefineDetails": SeeThrough_RefineDetails,
    "SeeThrough_ExtractDetailMask": SeeThrough_ExtractDetailMask,
    "SeeThrough_EditDetail": SeeThrough_EditDetail,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "SeeThrough_RefineDetails": "SeeThrough Refine Details (Candidates)",
    "SeeThrough_ExtractDetailMask": "SeeThrough Extract Detail by Mask",
    "SeeThrough_EditDetail": "SeeThrough Edit Detail Color",
}
