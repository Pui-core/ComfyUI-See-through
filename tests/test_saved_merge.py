import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image

spec = importlib.util.spec_from_file_location('parts_io', Path(__file__).resolve().parents[1]/'extras/ComfyUI-Revenant-Merge/parts_io.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(color, depth=1):
    return {'frame_size': (8, 8), 'tag2pinfo': {name: {'img': np.full((2, 2, 4), color, np.uint8), 'xyxy': [1, 2, 3, 4], 'depth_median': depth} for name in ['face', 'neck', 'topwear']}}


class SavedMergeTests(unittest.TestCase):
    def test_selective_replace_keeps_original_pixels_and_order(self):
        a,b=fixture(10, .2),fixture(200, .9)
        out=m.merge_parts(a,b,'neck\ntopwear',offset_x=2,offset_y=-1)
        np.testing.assert_array_equal(out['tag2pinfo']['face']['img'], a['tag2pinfo']['face']['img'])
        np.testing.assert_array_equal(out['tag2pinfo']['neck']['img'], b['tag2pinfo']['neck']['img'])
        self.assertEqual(out['tag2pinfo']['neck']['depth_median'], .2)
        self.assertEqual(out['tag2pinfo']['neck']['xyxy'], [3,1,5,3])
        self.assertEqual(b['tag2pinfo']['neck']['xyxy'], [1,2,3,4])
        self.assertEqual(a['tag2pinfo']['neck']['img'][0,0,0],10)

    def test_validation(self):
        a,b=fixture(1),fixture(2)
        for replacement, removal in [('missing',''),('neck','neck'),('','missing'),('','face,neck,topwear')]:
            with self.assertRaises(ValueError): m.merge_parts(a,b,replacement,removal)
        b['frame_size']=(9,8)
        with self.assertRaises(ValueError): m.merge_parts(a,b,'neck')

    def test_manifest_and_path_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            Image.new('RGBA',(2,3),(1,2,3,255)).save(root/'part.png')
            doc={'width':8,'height':8,'layers':[{'name':'neck','filename':'part.png','left':2,'top':1,'depth_median':.4}]}
            p=root/'layers.json';p.write_text(json.dumps(doc))
            part=m.read_parts(p)['tag2pinfo']['neck']
            self.assertEqual(part['xyxy'],[2,1,4,4])
            self.assertEqual(tuple(part['img'][0,0]),(1,2,3,255))
            doc['layers'][0]['filename']='../escape.png';p.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):m.read_parts(p)
            doc['layers'][0]['filename']='part.png';doc['layers'].append(dict(doc['layers'][0]));p.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):m.read_parts(p)

    def test_transparent_preview_order_and_clipping(self):
        a=fixture(0)
        a['tag2pinfo']['face']['img'][:]=[255,0,0,255]
        a['tag2pinfo']['face']['depth_median']=0
        self.assertTrue(np.allclose(m.preview(a)[2,1],[1,0,0]))
        a['tag2pinfo']['face']['xyxy']=[-1,-1,1,1]
        self.assertEqual(m.preview(a).shape,(8,8,3))

if __name__=='__main__':unittest.main()
