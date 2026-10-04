import importlib.util
from pathlib import Path
import unittest
import numpy as np
s=importlib.util.spec_from_file_location('core',Path(__file__).resolve().parents[1]/'extras/ComfyUI-Revenant-Decorations/core.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
    def test_candidates_and_corrections(self):
        rgb=np.zeros((4,4,3),np.uint8);rgb[1,1]=[70,20,230];rgb[2,2]=[70,20,230]
        t=np.zeros((4,4),np.float32);t[2,2]=1
        a=m.candidates(rgb,t);self.assertEqual(a.sum(),1)
        exclude=np.zeros((4,4));exclude[1,1]=1
        self.assertEqual(m.candidates(rgb,t,exclude=exclude).sum(),0)
        with self.assertRaises(ValueError):m.candidates(rgb,t,mode='silver_metal')
        with self.assertRaises(ValueError):m.candidates(rgb,t,add=np.zeros((2,2)))
    def test_source_alpha_not_squared_and_components(self):
        rgb=np.full((5,5,3),100,np.uint8);t=np.ones((5,5));t[0,0]=.5;t[4,4]=0
        mask=np.ones((5,5));out=m.extract(rgb,t,mask,minimum_area=1)
        self.assertEqual(len(out['tag2pinfo']),2)
        first=next(iter(out['tag2pinfo'].values()));self.assertEqual(first['img'][0,0,3],128)
        np.testing.assert_array_equal(first['img'][0,0,:3],[100]*3)
        self.assertEqual(first['xyxy'],[0,0,1,1])
        self.assertEqual(t[0,0],.5)
    def test_add_keeps_base_and_refuses_bad_canvas(self):
        d=m.extract(np.zeros((3,3,3),np.uint8),np.zeros((3,3)),np.eye(3),minimum_area=1)
        base={'frame_size':(3,3),'tag2pinfo':{'body':{'depth_median':5}}}
        merged=m.add_layers(base,d,1,2)
        self.assertEqual(len(base['tag2pinfo']),1)
        p=merged['tag2pinfo']['decor_001'];self.assertEqual(p['xyxy'],[1,2,4,5]);self.assertLess(p['depth_median'],5)
        with self.assertRaises(ValueError):m.add_layers(d,d)
        with self.assertRaises(ValueError):m.add_layers({'frame_size':(4,4),'tag2pinfo':{}},d)
    def test_fit_letterbox_and_empty(self):
        rgb=np.full((4,2,3),100,np.uint8);t=np.zeros((4,2))
        r,alpha=m.fit_source(rgb,t,(4,4));self.assertEqual(r.shape,(4,4,3));self.assertTrue((alpha[:,0]==1).all());self.assertTrue((alpha[:,1:3]==0).all())
        with self.assertRaises(ValueError):m.extract(rgb,t,np.zeros((4,2)))
if __name__=='__main__':unittest.main()
