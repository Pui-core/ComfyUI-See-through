import unittest
import numpy as np
from detail_parts import refine_parts, extract_mask, hair_masks, highlight_masks


def fixture(tag="hair", h=80, w=90):
    rng = np.random.default_rng(7)
    img = rng.integers(0, 256, (h, w, 4), dtype=np.uint8)
    img[..., 3] = 0
    img[5:-5, 5:-5, 3] = 255
    return {"frame_size": (h+20, w+30), "tag2pinfo": {tag: {
        "img": img, "xyxy": [11, 9, 11+w, 9+h], "tag": tag,
        "depth": np.full((h, w), 103, np.uint8), "depth_median": .4}}}


def reconstruct(data):
    h, w = data["frame_size"]
    rgba = np.zeros((h, w, 4), np.uint8)
    coverage = np.zeros((h, w), np.uint16)
    for p in data["tag2pinfo"].values():
        img = p["img"]
        x, y, x1, y1 = p["xyxy"]
        visible = img[..., 3] > 0
        rgba[y:y1, x:x1][visible] = img[visible]
        coverage[y:y1, x:x1] += visible
        assert p["depth"].shape == img.shape[:2]
    return rgba, coverage


class DetailTests(unittest.TestCase):
    def assertPartition(self, before, after):
        a, ac = reconstruct(before)
        b, bc = reconstruct(after)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(ac, bc)

    def test_manual_offsets_alpha_and_input_unchanged(self):
        data = fixture("face")
        original = data["tag2pinfo"]["face"]["img"].copy()
        data["tag2pinfo"]["face"]["img"][25, 30, 3] = 71
        original = data["tag2pinfo"]["face"]["img"].copy()
        mask = np.zeros(data["frame_size"], np.float32)
        mask[30:44, 35:55] = 1
        out = extract_mask(data, "face", "nose", mask)
        self.assertIn("nose", out["tag2pinfo"])
        self.assertPartition(data, out)
        np.testing.assert_array_equal(original, data["tag2pinfo"]["face"]["img"])

    def test_mask_errors(self):
        data = fixture()
        mask = np.ones(data["frame_size"], np.float32)
        for source, name, m in [("missing", "nose", mask), ("hair", "../bad", mask),
                                ("hair", "hair", mask), ("hair", "nose", mask[:3]),
                                ("hair", "nose", mask*0), ("hair", "nose", mask*np.nan)]:
            with self.assertRaises(ValueError):
                extract_mask(data, source, name, m)

    def test_full_mask(self):
        data = fixture()
        out = extract_mask(data, "hair", "lock_01", np.ones(data["frame_size"]))
        self.assertNotIn("hair", out["tag2pinfo"])
        self.assertPartition(data, out)

    def test_accessory_islands_and_tiny_residue(self):
        data = fixture("headwear")
        img = data["tag2pinfo"]["headwear"]["img"]
        img[..., 3] = 0
        img[8:22, 5:17, 3] = 255
        img[38:54, 55:75, 3] = 128
        img[65, 80, 3] = 10
        out = refine_parts(data)
        self.assertIn("headwear_accessory_02", out["tag2pinfo"])
        self.assertPartition(data, out)

    def test_bright_island_and_white_hair(self):
        img = np.full((100, 100, 4), 255, np.uint8)
        self.assertEqual(highlight_masks(img), [])
        img[..., :3] = 45
        img[44:50, 43:49, :3] = 255
        self.assertTrue(highlight_masks(img, 3, .08))

    def test_automatic_conserves_pixels(self):
        for tag in ["hair", "front hair", "iridesl", "irides-l", "irides-r", "eyes", "nose"]:
            data = fixture(tag)
            out = refine_parts(data, minimum_area=2)
            self.assertPartition(data, out)

    def test_hair_two_lobes(self):
        img = np.zeros((120, 100, 4), np.uint8)
        img[10:100, 10:35] = [80, 60, 40, 255]
        img[10:100, 60:90] = [80, 60, 40, 255]
        self.assertGreaterEqual(len(hair_masks(img)), 2)

    def test_empty_and_disabled(self):
        self.assertEqual(refine_parts({"frame_size": (10, 10), "tag2pinfo": {}})["tag2pinfo"], {})
        data = fixture()
        out = refine_parts(data, False, False, False, False)
        self.assertPartition(data, out)


if __name__ == "__main__":
    unittest.main()
