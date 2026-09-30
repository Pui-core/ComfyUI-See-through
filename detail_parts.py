"""Conservative, CPU-only refinement of SeeThrough RGBA parts.

Automatic regions are candidates, not new learned semantic classes. Every split
is a disjoint partition of the original alpha; input arrays are never modified.
"""
import re

import cv2
import numpy as np

HAIR = {"hair", "hairf", "hairb", "front hair", "back hair"}
EYES = {"eyes", "eyel", "eyer", "irides", "iridesl", "iridesr", "irides-l", "irides-r"}
ACCESSORIES = {"headwear", "earwear", "neckwear", "eyewear", "objects"}


def _copy(part):
    return {key: value.copy() if isinstance(value, np.ndarray) else value
            for key, value in part.items()}


def _components(mask, minimum, maximum=64):
    count, labels, stats, centers = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8)
    ids = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= minimum]
    ids.sort(key=lambda i: (-int(stats[i, cv2.CC_STAT_AREA]), float(centers[i, 0])))
    ids = ids[:maximum]
    ids.sort(key=lambda i: (float(centers[i, 0]), float(centers[i, 1])))
    return [labels == i for i in ids]


def _piece(parent, mask, tag, kind):
    """Crop while preserving canvas offsets, depth dtype and exact RGBA bytes."""
    img = parent["img"]
    ys, xs = np.nonzero(mask & (img[..., 3] > 0))
    if not len(xs):
        return None
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    result = _copy(parent)
    cropped = img[y0:y1, x0:x1].copy()
    cropped[..., 3] = np.where(mask[y0:y1, x0:x1], cropped[..., 3], 0)
    result["img"] = cropped
    ox, oy = parent.get("xyxy", [0, 0])[:2]
    result["xyxy"] = [int(ox + x0), int(oy + y0), int(ox + x1), int(oy + y1)]
    if parent.get("depth") is not None:
        result["depth"] = parent["depth"][y0:y1, x0:x1].copy()
    result.pop("mask", None)
    result.update(tag=tag, detail_kind=kind)
    return result


def _unique(parts, name):
    candidate = name
    index = 2
    while candidate in parts:
        candidate = f"{name}_{index:02d}"
        index += 1
    return candidate


def partition(parts, source, masks, kind):
    """Extract nonoverlapping regions, retaining all rejected/remainder pixels."""
    parent = parts[source]
    available = parent["img"][..., 3] > 0
    for index, mask in enumerate(masks, 1):
        selected = np.asarray(mask, dtype=bool) & available
        if not selected.any():
            continue
        tag = _unique(parts, f"{source}_{kind}_{index:02d}")
        child = _piece(parent, selected, tag, kind)
        child["parent_tag"] = source
        parts[tag] = child
        available &= ~selected
    remainder = _piece(parent, available, source, parent.get("detail_kind", "base"))
    if remainder is None:
        del parts[source]
    else:
        parts[source] = remainder


def highlight_masks(img, minimum=3, contrast=0.10, brightness=0.72):
    """Find locally bright, low-saturation islands inside opaque material.

    The erosion excludes boundary glow; a size cap rejects a white-hair base or
    the white of a composite eye. Colored/diffuse highlights may need a mask.
    """
    rgb = img[..., :3].astype(np.float32) / 255.0
    value = rgb.max(axis=2)
    saturation = value - rgb.min(axis=2)
    opaque = (img[..., 3] > 200).astype(np.uint8)
    interior = cv2.erode(opaque, np.ones((3, 3), np.uint8)) > 0
    radius = max(3, min(41, int(min(img.shape[:2]) * .06) | 1))
    # Normalize blur by alpha to keep transparent padding out of local contrast.
    weight = (img[..., 3].astype(np.float32) / 255.0)
    blurred_weight = cv2.GaussianBlur(weight, (radius, radius), 0)
    local = cv2.GaussianBlur(value * weight, (radius, radius), 0)
    local /= np.maximum(blurred_weight, 1e-6)
    candidates = interior & (value >= brightness) & (saturation < .32) & (value - local >= contrast)
    maximum_area = max(minimum, int(opaque.sum() * .15))
    return [mask for mask in _components(candidates, minimum, 16)
            if int(mask.sum()) <= maximum_area]


def hair_masks(img, minimum=24, limit=16):
    """Watershed candidates seeded by separated silhouette distance peaks.

    Do not slice the image into arbitrary vertical strips. Connected locks with
    no distinct silhouette peaks remain joined for user-mask correction.
    """
    support = img[..., 3] > 0
    core = (img[..., 3] > 127).astype(np.uint8)
    distance = cv2.distanceTransform(core, cv2.DIST_L2, 5)
    if distance.max() < 2:
        return []
    spacing = max(5, min(65, (int(min(core.shape) * .06) | 1)))
    maxima = cv2.dilate(distance, np.ones((spacing, spacing), np.uint8))
    peaks = (distance >= maxima - 1e-5) & (distance >= max(2, distance.max() * .16))
    seeds = _components(peaks, 1, limit)
    if len(seeds) < 2:
        return []
    markers = np.zeros(core.shape, np.int32)
    markers[~support] = 1
    for i, seed in enumerate(seeds, 2):
        markers[seed] = i
    # RGB edges guide the partition between silhouette seeds.
    cv2.watershed(np.ascontiguousarray(img[..., :3]), markers)
    return [mask for i in range(2, len(seeds) + 2)
            if (mask := (markers == i) & support).sum() >= minimum]


def refine_parts(data, eye_highlights=True, hair_highlights=True, hair_locks=True,
                 accessories=True, minimum_area=8, highlight_contrast=.08,
                 max_hair_locks=16):
    output = dict(data)
    parts = {tag: _copy(part) for tag, part in data["tag2pinfo"].items()}
    output["tag2pinfo"] = parts
    report = []
    for tag in list(parts):
        # Existing detail children are not recursively auto-refined.
        if parts[tag].get("detail_kind"):
            continue
        category = tag.lower().replace("_", " ")
        img = parts[tag]["img"]
        is_hair = category in HAIR
        is_eye = category in EYES
        if (is_hair and hair_highlights) or (is_eye and eye_highlights):
            masks = highlight_masks(img, minimum_area, highlight_contrast)
            partition(parts, tag, masks, "highlight")
            report.append(f"{tag}: highlight candidates={len(masks)}")
        if tag not in parts:
            continue
        if is_hair and hair_locks:
            masks = hair_masks(parts[tag]["img"], minimum_area, max_hair_locks)
            if len(masks) >= 2:
                partition(parts, tag, masks, "lock")
            report.append(f"{tag}: lock candidates={len(masks)}")
        elif category in ACCESSORIES and accessories:
            masks = _components(parts[tag]["img"][..., 3] > 0, minimum_area)
            if len(masks) >= 2:
                partition(parts, tag, masks, "accessory")
            report.append(f"{tag}: accessory islands={len(masks)}")
    if "nose" not in parts:
        report.append("Nose not detected by the model: extract it from face using a mask.")
    output["detail_report"] = report
    return output


def extract_mask(data, source, name, mask, threshold=.5):
    """Extract a canvas-space user mask, including nose/accessory corrections."""
    if source not in data["tag2pinfo"]:
        raise ValueError(f"Unknown source part: {source}")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise ValueError("Part name must use 1–80 ASCII letters, digits, _ or -")
    if name in data["tag2pinfo"]:
        raise ValueError(f"Part name already exists: {name}")
    if mask.ndim != 2 or tuple(mask.shape) != tuple(data["frame_size"]):
        raise ValueError("Mask must match the full canvas height and width")
    if not np.isfinite(mask).all() or not 0 <= threshold <= 1:
        raise ValueError("Mask and threshold must be finite; threshold must be in [0, 1]")
    output = dict(data)
    parts = {tag: _copy(part) for tag, part in data["tag2pinfo"].items()}
    output["tag2pinfo"] = parts
    parent = parts[source]
    h, w = parent["img"].shape[:2]
    x, y = [int(v) for v in parent.get("xyxy", [0, 0])[:2]]
    if x < 0 or y < 0 or x + w > mask.shape[1] or y + h > mask.shape[0]:
        raise ValueError("Source part lies outside the canvas")
    selected = (mask[y:y+h, x:x+w] > threshold) & (parent["img"][..., 3] > 0)
    child = _piece(parent, selected, name, "manual")
    if child is None:
        raise ValueError("The mask does not overlap any visible pixels of the source part")
    child["parent_tag"] = source
    parts[name] = child
    remainder = _piece(parent, ~selected, source, "base")
    if remainder is None:
        del parts[source]
    else:
        parts[source] = remainder
    return output
