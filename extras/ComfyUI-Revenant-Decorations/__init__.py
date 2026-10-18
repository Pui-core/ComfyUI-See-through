import numpy as np
import torch
from .core import candidates, extract, add_layers


def array(t):
    if t.shape[0]!=1: raise ValueError('Use batch size 1')
    return t[0].detach().cpu().numpy()


def source(t): return np.rint(np.clip(array(t),0,1)*255).astype(np.uint8)


class RevenantDecorationMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'image':('IMAGE',), 'source_transparency':('MASK',),
            'mode':(['blue_violet','silver_metal','manual_only'],),
            'hue_min':('INT',{'default':150,'min':0,'max':255}),
            'hue_max':('INT',{'default':205,'min':0,'max':255}),
            'saturation_min':('INT',{'default':70,'min':0,'max':255}),
            'value_min':('INT',{'default':50,'min':0,'max':255}),
        },'optional':{'region':('MASK',),'add':('MASK',),'exclude':('MASK',)}}
    RETURN_TYPES=('MASK','IMAGE')
    RETURN_NAMES=('mask','overlay_preview')
    FUNCTION='run'
    CATEGORY='SeeThrough/Decorations'
    def run(self,image,source_transparency,mode,hue_min,hue_max,saturation_min,value_min,region=None,add=None,exclude=None):
        rgb=source(image)
        m=candidates(rgb,array(source_transparency),mode,hue_min,hue_max,saturation_min,value_min,
                     *[array(t) if t is not None else None for t in (region,add,exclude)])
        p=rgb.astype(np.float32)/255
        p=p*(1-m[...,None]*.55)+np.array([1,.15,.1],np.float32)*m[...,None]*.55
        return torch.from_numpy(m).unsqueeze(0),torch.from_numpy(p.astype(np.float32)).unsqueeze(0)


class RevenantExtractDecorations:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'image':('IMAGE',),'source_transparency':('MASK',),'mask':('MASK',),
                'prefix':('STRING',{'default':'flowers_vines'}),
                'minimum_area':('INT',{'default':8,'min':1,'max':100000}),
                'split_components':('BOOLEAN',{'default':True})}}
    RETURN_TYPES=('SEETHROUGH_PARTS','IMAGE')
    RETURN_NAMES=('decorations','preview')
    FUNCTION='run'
    CATEGORY='SeeThrough/Decorations'
    def run(self,image,source_transparency,mask,prefix,minimum_area,split_components):
        rgb=source(image)
        parts=extract(rgb,array(source_transparency),array(mask),prefix,minimum_area,split_components)
        canvas=np.full(rgb.shape,.35,np.float32)
        for p in parts['tag2pinfo'].values():
            x,y,x2,y2=p['xyxy']; rgba=p['img'].astype(np.float32)/255; a=rgba[...,3:4]
            canvas[y:y2,x:x2]=rgba[...,:3]*a+canvas[y:y2,x:x2]*(1-a)
        return parts,torch.from_numpy(canvas).unsqueeze(0)


class RevenantAddDecorationLayers:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'base':('SEETHROUGH_PARTS',),'decorations':('SEETHROUGH_PARTS',),
            'offset_x':('INT',{'default':0,'min':-16384,'max':16384}),
            'offset_y':('INT',{'default':0,'min':-16384,'max':16384})}}
    RETURN_TYPES=('SEETHROUGH_PARTS',)
    FUNCTION='run'
    CATEGORY='SeeThrough/Decorations'
    def run(self,base,decorations,offset_x,offset_y):
        return (add_layers(base,decorations,offset_x,offset_y),)


NODE_CLASS_MAPPINGS={c.__name__:c for c in (RevenantDecorationMask,RevenantExtractDecorations,RevenantAddDecorationLayers)}
NODE_DISPLAY_NAME_MAPPINGS={'RevenantDecorationMask':'SeeThrough Decoration Mask (Candidates)', 'RevenantExtractDecorations':'SeeThrough Extract Decorations', 'RevenantAddDecorationLayers':'SeeThrough Add Decoration Layers'}


class RevenantFitDecorationSource:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'image':('IMAGE',),'source_transparency':('MASK',),'reference_parts':('SEETHROUGH_PARTS',)}}
    RETURN_TYPES=('IMAGE','MASK')
    RETURN_NAMES=('image','source_transparency')
    FUNCTION='run'
    CATEGORY='SeeThrough/Decorations'
    def run(self,image,source_transparency,reference_parts):
        from .core import fit_source
        rgb,trans=fit_source(source(image),array(source_transparency),reference_parts['frame_size'])
        return torch.from_numpy(rgb.astype(np.float32)/255).unsqueeze(0),torch.from_numpy(trans).unsqueeze(0)

NODE_CLASS_MAPPINGS['RevenantFitDecorationSource']=RevenantFitDecorationSource
NODE_DISPLAY_NAME_MAPPINGS['RevenantFitDecorationSource']='SeeThrough Fit Source to Canvas (Contain)'
