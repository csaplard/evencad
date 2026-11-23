"""The segment that the last sentence changed is drawn with thicker lines."""

from fastapi.testclient import TestClient

from server.core.ops import InterpreterResult, active_after, parse_op
from server.core.spec import Segment, ShaftSpec
from server.draw.glasses import render_glasses, segment_span
from server.draw.glasses3d import render_glasses_3d
from server.main import create_app


def shaft(*dims):
    return ShaftSpec(id="s_20261123_aaaaaa", segments=[Segment(diameter=d, length=l) for d, l in dims])


def ops(*items):
    return [parse_op(i) for i in items]


def lit(img):
    return sum(1 for b in img.tobytes() if b)


def test_active_after():
    three = shaft((30, 40), (25, 60), (20, 30))
    assert active_after(three, ops({"op": "add_segment", "diameter": 10, "length": 5}), None) == 4
    assert active_after(three, ops({"op": "add_segment", "diameter": 10, "length": 5, "at": 2}), None) == 2
    assert active_after(three, ops({"op": "edit_segment", "index": 2, "diameter": 28}), 3) == 2
    assert active_after(three, ops({"op": "edit_segment", "index": "last", "length": 28}), 1) == 3
    assert active_after(three, ops({"op": "set_chamfer", "where": "left_end", "size": 1}), None) == 1
    assert active_after(three, ops({"op": "set_chamfer", "where": "right_end", "size": 1}), None) == 3
    # Step 1 is between Ø30 and Ø25. The chamfer goes on the larger one.
    assert active_after(three, ops({"op": "set_chamfer", "where": 1, "size": 1}), None) == 1
    assert active_after(three, ops({"op": "delete_segment", "index": 2}), 2) is None
    # Title and material do not move the mark.
    assert active_after(three, ops({"op": "set_material", "text": "C45"}), 2) == 2
    # Several operations: the last touched segment wins.
    assert active_after(three, ops(
        {"op": "edit_segment", "index": 1, "diameter": 32},
        {"op": "add_segment", "diameter": 10, "length": 5},
    ), None) == 4


def test_segment_span():
    assert segment_span(shaft((30, 40), (25, 60)), 2) == (40, 100, 12.5)
    assert segment_span(shaft((30, 40)), 5) is None


def test_2d_marks_the_active_segment_with_more_pixels():
    part = shaft((30, 40), (25, 60), (20, 30))
    plain = render_glasses(part)
    marked = render_glasses(part, active_segment=2, highlight=True)
    assert set(marked.tobytes()) <= {0, 255}
    assert lit(marked) > lit(plain)
    assert marked.tobytes() != render_glasses(part, active_segment=3, highlight=True).tobytes()


def test_3d_marks_the_active_segment():
    part = shaft((30, 40), (45, 12), (20, 30))
    for yaw in (30, 150):
        plain = render_glasses_3d(part, yaw)
        marked = render_glasses_3d(part, yaw, active_segment=2)
        assert set(marked.tobytes()) <= {0, 255}
        assert lit(marked) > lit(plain), yaw


def test_one_segment_is_never_marked():
    one = shaft((30, 40))
    assert render_glasses(one, active_segment=1, highlight=True).tobytes() == render_glasses(one).tobytes()
    assert render_glasses_3d(one, 30, active_segment=1).tobytes() == render_glasses_3d(one, 30).tobytes()


class Fake:
    def interpret(self, spec, utterance):
        answers = {
            "second 28": {"ops": [{"op": "edit_segment", "index": 2, "diameter": 28}]},
            "first 32": {"ops": [{"op": "edit_segment", "index": 1, "diameter": 32}]},
        }
        return InterpreterResult.model_validate({"ask": None, **answers[utterance]})


def test_the_api_follows_the_last_change(tmp_path):
    client = TestClient(create_app(auth=False, data_dir=tmp_path, interpreter=Fake(), drive=None))
    sid = client.post("/session").json()["id"]

    def say(text):
        return client.post(f"/session/{sid}/utterance", json={"text": text}).json()

    for number in ("30", "40", "25", "60"):
        st = say(number)
    assert st["active_segment"] == 2
    last = client.get(f"/session/{sid}/render").content
    assert say("first 32")["active_segment"] == 1
    first = client.get(f"/session/{sid}/render").content
    assert first != last
    assert client.get(f"/session/{sid}/render", params={"view": 30}).status_code == 200
    # Undo goes back to the mark that was there before the change.
    assert client.post(f"/session/{sid}/undo").json()["active_segment"] == 2
    assert client.get(f"/session/{sid}/render").content == last
