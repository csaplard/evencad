"""3D line view for the glasses: a stepped, hidden-line drawing."""

import io

from fastapi.testclient import TestClient
from PIL import Image

from server.core.ops import InterpreterResult
from server.core.spec import Chamfer, Segment, ShaftSpec
from server.draw.glasses3d import YAW_STEPS, _hull, glasses_3d_tiles, render_glasses_3d
from server.main import create_app


def demo():
    return ShaftSpec(id="s_20261123_aaaaaa", segments=[
        Segment(diameter=30, length=40),
        Segment(diameter=45, length=12),
        Segment(diameter=20, length=30, chamfer_right=Chamfer(size=2)),
    ])


def lit(img):
    return sum(1 for b in img.tobytes() if b)


def test_every_view_is_a_black_and_white_line_drawing():
    for yaw in YAW_STEPS:
        img = render_glasses_3d(demo(), yaw)
        assert img.size == (576, 144)
        assert set(img.tobytes()) <= {0, 255}
        assert 0.01 < lit(img) / (576 * 144) < 0.25, yaw


def test_views_differ_from_each_other():
    images = [render_glasses_3d(demo(), yaw).tobytes() for yaw in YAW_STEPS]
    assert len(set(images)) == len(YAW_STEPS)


def test_the_drawing_does_not_touch_the_right_and_bottom_border():
    for yaw in YAW_STEPS:
        img = render_glasses_3d(demo(), yaw)
        assert not img.crop((575, 0, 576, 144)).getbbox(), yaw
        assert not img.crop((0, 143, 576, 144)).getbbox(), yaw


def test_nearer_parts_hide_farther_parts():
    # A big flange with a thin pin. Seen from the pin end, the pin is in front and visible.
    # Seen from the flange end, the flange covers the pin, so fewer lines are drawn.
    part = ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=60, length=10), Segment(diameter=10, length=40)])
    from_flange_end = lit(render_glasses_3d(part, 90, pitch_deg=0))
    from_pin_end = lit(render_glasses_3d(part.model_copy(update={"segments": part.segments[::-1]}), 90, pitch_deg=0))
    assert from_pin_end != from_flange_end
    assert min(from_pin_end, from_flange_end) < max(from_pin_end, from_flange_end)


def test_empty_spec_shows_the_hint():
    assert render_glasses_3d(ShaftSpec(id="s_20261123_aaaaaa"), 30).getbbox()


def test_hull():
    square = [(0, 0), (2, 0), (2, 2), (0, 2), (1, 1), (1, 0.5)]
    assert sorted(_hull(square)) == [(0, 0), (0, 2), (2, 0), (2, 2)]


def test_tiles_and_endpoint(tmp_path):
    tiles = glasses_3d_tiles(demo(), 60)
    assert [Image.open(io.BytesIO(t)).size for t in tiles] == [(288, 144), (288, 144)]

    class Fake:
        def interpret(self, spec, utterance):
            return InterpreterResult.model_validate({"ops": [{"op": "add_segment", "diameter": 30, "length": 40}], "ask": None})

    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=Fake(), drive=None))
    st = client.post("/session").json()
    assert st["views_3d"] == [30, 60, 90, 120, 150]
    sid = st["id"]
    client.post(f"/session/{sid}/utterance", json={"text": "add"})
    flat = client.get(f"/session/{sid}/render", params={"tile": 0}).content
    turned = client.get(f"/session/{sid}/render", params={"tile": 0, "view": 60})
    assert turned.status_code == 200 and turned.content != flat
    assert Image.open(io.BytesIO(turned.content)).size == (288, 144)
    assert Image.open(io.BytesIO(client.get(f"/session/{sid}/render", params={"view": 60}).content)).size == (576, 144)
    assert client.get(f"/session/{sid}/render", params={"view": 999}).status_code == 422
