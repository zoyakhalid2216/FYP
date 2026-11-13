import numpy as np

from src.vision.engine import VisionEngine


def test_frame_changed_detects_difference():
    vis = VisionEngine({})
    a = np.zeros((40, 40, 3), dtype=np.uint8)
    b = np.zeros((40, 40, 3), dtype=np.uint8)
    b[:] = 255
    hit = vis.frame_changed(a, b, threshold=0.01)
    assert hit["changed"] is True
    same = vis.frame_changed(a, a, threshold=0.01)
    assert same["changed"] is False


def test_ocr_scale_maps_coords_back():
    vis = VisionEngine({})
    words = [{"x": 170, "y": 280, "w": 40, "h": 20, "label": "Login"}]
    scaled = vis._ocr_scale_words(words, 1.7)
    assert scaled[0]["x"] == round(170 / 1.7)
    assert scaled[0]["label"] == "Login"
    same = vis._ocr_scale_words(words, 1.0)
    assert same[0]["x"] == 170
    vis = VisionEngine({})
    a = np.zeros((40, 40, 3), dtype=np.uint8)
    b = np.zeros((40, 40, 3), dtype=np.uint8)
    b[:] = 255
    hit = vis.frame_changed(a, b, threshold=0.01)
    assert hit["changed"] is True
    same = vis.frame_changed(a, a, threshold=0.01)
    assert same["changed"] is False
