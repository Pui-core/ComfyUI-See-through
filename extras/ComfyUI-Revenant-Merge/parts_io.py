"""CPU-only loading and selective replacement of SeeThrough saved parts."""
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image


def read_parts(path):
    path = Path(path).expanduser().resolve()
    doc = json.loads(path.read_text(encoding='utf-8'))
    w, h = doc['width'], doc['height']
    if type(w) is not int or type(h) is not int or not (0 < w <= 16384 and 0 < h <= 16384):
        raise ValueError('Invalid canvas dimensions')
    parts = {}
    for entry in doc['layers']:
        name = entry['name']
        if not isinstance(name, str) or not name or name in parts or any(c in name for c in '/\\\x00') or name in ('.', '..'):
            raise ValueError('Invalid or duplicate part name')
        image_path = (path.parent / entry['filename']).resolve()
        if not image_path.is_relative_to(path.parent):
            raise ValueError('Layer PNG must be within the manifest directory')
        with Image.open(image_path) as im:
            rgba = np.array(im.convert('RGBA'))
        x, y = entry['left'], entry['top']
        if type(x) is not int or type(y) is not int:
            raise ValueError('Layer coordinates must be integers')
        depth = float(entry.get('depth_median', 1))
        if not math.isfinite(depth):
            raise ValueError('Invalid layer depth')
        ih, iw = rgba.shape[:2]
        parts[name] = {'img': rgba, 'xyxy': [x, y, x+iw, y+ih], 'depth_median': depth, 'tag': name}
    if not parts:
        raise ValueError('Manifest has no layers')
    return {'frame_size': (h, w), 'tag2pinfo': parts}


def names(text):
    return list(dict.fromkeys(t.strip() for t in text.replace(',', '\n').splitlines() if t.strip()))


def merge_parts(original, underlay, replace, remove='', offset_x=0, offset_y=0):
    if original['frame_size'] != underlay['frame_size']:
        raise ValueError('Canvas sizes differ. Align canvases before merging; automatic resizing is disabled.')
    selected, removed = names(replace), names(remove)
    if set(selected) & set(removed):
        raise ValueError('A part cannot be both replaced and removed')
    a, b = original['tag2pinfo'], underlay['tag2pinfo']
    for name in selected:
        if name not in a or name not in b:
            raise ValueError(f'Part {name!r} must exist in both inputs. Original: {list(a)}; underlay: {list(b)}')
    for name in removed:
        if name not in a:
            raise ValueError(f'Unknown removal: {name}; available: {list(a)}')
    result = dict(a)
    for name in selected:
        part = dict(b[name])
        x, y, x2, y2 = part['xyxy']
        part['xyxy'] = [x+offset_x, y+offset_y, x2+offset_x, y2+offset_y]
        # Independent depth predictions are not comparable: retain original ordering.
        part['depth_median'] = a[name].get('depth_median', 1)
        result[name] = part
    for name in removed:
        del result[name]
    if not result:
        raise ValueError('Cannot produce an empty document')
    return {'frame_size': original['frame_size'], 'tag2pinfo': result}


def preview(parts):
    h, w = parts['frame_size']
    # Downscaled preview only. Export data and coordinates remain untouched.
    ratio = min(1, 1536/max(h, w))
    pw, ph = max(1, round(w*ratio)), max(1, round(h*ratio))
    canvas = Image.new('RGBA', (pw, ph), (96, 96, 96, 255))
    for p in sorted(parts['tag2pinfo'].values(), key=lambda p:p.get('depth_median', 1), reverse=True):
        image = Image.fromarray(p['img'], 'RGBA')
        if ratio != 1:
            image = image.resize((max(1, round(image.width*ratio)), max(1, round(image.height*ratio))), Image.Resampling.LANCZOS)
        x, y = p['xyxy'][:2]
        canvas.alpha_composite(image, (round(x*ratio), round(y*ratio)))
    return np.asarray(canvas.convert('RGB'), dtype=np.float32)/255


def inventory(parts):
    return '\n'.join(f"{n}: xy={p['xyxy'][:2]}, depth={p.get('depth_median', 1)}" for n,p in parts['tag2pinfo'].items())
