"""Colour candidates and source-pixel extraction, not semantic segmentation."""
from collections import deque
import re
import numpy as np
from PIL import Image


def mask_array(mask, shape):
    m = np.asarray(mask, dtype=np.float32)
    if m.shape != shape or not np.isfinite(m).all():
        raise ValueError('Mask must be finite and match the source canvas exactly')
    return np.clip(m, 0, 1)


def candidates(rgb, transparency, mode='blue_violet', hue_min=150, hue_max=205,
               saturation_min=70, value_min=50, region=None, add=None, exclude=None):
    rgb = np.asarray(rgb)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError('Expected uint8 RGB source')
    shape = rgb.shape[:2]
    trans = mask_array(transparency, shape)
    hsv = np.asarray(Image.fromarray(rgb, 'RGB').convert('HSV'))
    h,s,v = hsv[...,0],hsv[...,1],hsv[...,2]
    if mode == 'manual_only':
        selected = np.zeros(shape, np.float32)
    elif mode == 'blue_violet':
        hue = (h>=hue_min)&(h<=hue_max) if hue_min<=hue_max else (h>=hue_min)|(h<=hue_max)
        selected = (hue & (s>=saturation_min) & (v>=value_min)).astype(np.float32)
    elif mode == 'silver_metal':
        if region is None:
            raise ValueError('Metal candidates require a region mask to avoid silver hair/skin')
        selected = ((s<=45)&(v>=max(value_min,140))).astype(np.float32)
    else:
        raise ValueError('Unknown candidate mode')
    if region is not None:
        selected *= mask_array(region, shape)
    if add is not None:
        selected = np.maximum(selected, mask_array(add, shape))
    if exclude is not None:
        selected *= 1-mask_array(exclude, shape)
    # Do not multiply antialias alpha twice: only exclude fully transparent pixels here.
    return selected * (trans < 1)


def components(binary):
    seen = np.zeros(binary.shape, bool)
    h,w = binary.shape
    for y,x in np.argwhere(binary):
        if seen[y,x]: continue
        todo=deque([(int(y),int(x))]); seen[y,x]=True; points=[]
        while todo:
            cy,cx=todo.popleft(); points.append((cy,cx))
            for dy,dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
                yy,xx=cy+dy,cx+dx
                if 0<=yy<h and 0<=xx<w and binary[yy,xx] and not seen[yy,xx]:
                    seen[yy,xx]=True; todo.append((yy,xx))
        yield np.asarray(points)


def extract(rgb, transparency, mask, prefix='decor', minimum_area=8, split=True):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',prefix):
        raise ValueError('Prefix must contain only ASCII letters, digits, underscore or hyphen')
    h,w=rgb.shape[:2]
    mask=mask_array(mask,(h,w)); trans=mask_array(transparency,(h,w))
    alpha=np.rint(255*(1-trans)*mask).astype(np.uint8)
    binary=alpha>0
    groups=components(binary) if split else [np.argwhere(binary)]
    result={}
    for points in groups:
        if len(points)<minimum_area: continue
        ys,xs=points[:,0],points[:,1]; x,y=int(xs.min()),int(ys.min()); x2,y2=int(xs.max())+1,int(ys.max())+1
        rgba=np.zeros((y2-y,x2-x,4),np.uint8)
        rgba[ys-y,xs-x,:3]=rgb[ys,xs]
        rgba[ys-y,xs-x,3]=alpha[ys,xs]
        name=f'{prefix}_{len(result)+1:03d}'
        result[name]={'img':rgba,'xyxy':[x,y,x2,y2],'depth_median':-1.,'tag':name}
    if not result: raise ValueError('No decoration pixels found; inspect mask / lower minimum_area')
    return {'frame_size':(h,w),'tag2pinfo':result}


def add_layers(base, decorations, offset_x=0, offset_y=0):
    if base['frame_size']!=decorations['frame_size']:
        raise ValueError('Canvas mismatch: align source to the saved PSD canvas; no automatic resize')
    result=dict(base['tag2pinfo'])
    if result.keys() & decorations['tag2pinfo'].keys():
        raise ValueError('Duplicate layer names: use a different prefix')
    front=min((p.get('depth_median',1) for p in result.values()),default=1)-1
    for name,p in decorations['tag2pinfo'].items():
        part=dict(p); x,y,x2,y2=part['xyxy']
        part['xyxy']=[x+offset_x,y+offset_y,x2+offset_x,y2+offset_y]
        part['depth_median']=front
        result[name]=part
    return {'frame_size':base['frame_size'],'tag2pinfo':result}


def fit_source(rgb, transparency, frame_size):
    """Explicit contain/centre transform, not content-based registration."""
    h,w=frame_size; sh,sw=rgb.shape[:2]
    trans=mask_array(transparency,(sh,sw))
    rgba=np.dstack((rgb,np.rint((1-trans)*255).astype(np.uint8)))
    scale=min(w/sw,h/sh); nw,nh=max(1,round(sw*scale)),max(1,round(sh*scale))
    image=Image.fromarray(rgba,'RGBA')
    if (nw,nh)!=(sw,sh): image=image.resize((nw,nh),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(w,h));canvas.paste(image,((w-nw)//2,(h-nh)//2))
    arr=np.asarray(canvas)
    return arr[...,:3].copy(),1-arr[...,3].astype(np.float32)/255
