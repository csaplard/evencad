"""The interpreter prompt. Both adapters (CLI and API) use exactly this text."""

import json

from server.core.keyway import keyway_size
from server.core.spec import ShaftSpec, fmt

SYSTEM_PROMPT = """You turn one spoken sentence into edit operations for a stepped shaft drawing.

The shaft is a list of cylindrical segments, left to right. Units are millimetres.
Segments are numbered from 1. Step k is the shoulder between segment k and segment k+1.

Answer with one JSON object and nothing else:
{"ops": [ ... ], "ask": null}            when the sentence is clear
{"ops": [], "ask": "short question"}     when it is not

Allowed operations (use only these, with only these fields):
{"op": "add_segment", "diameter": number, "length": number, "at": number or null}
    "at" is the position of the new segment. null means: at the right end.
{"op": "edit_segment", "index": number or "last", "diameter": number or null, "length": number or null}
{"op": "delete_segment", "index": number or "last"}
{"op": "set_chamfer", "where": "left_end" or "right_end" or step number, "size": number, "angle": number}
    "angle" is 45 unless the speaker says another angle. "one by forty-five" means size 1, angle 45.
{"op": "set_fillet", "step": step number, "radius": number}
    A fillet (rounding, radius) in the inner corner of a shoulder. Radius 0 removes it.
{"op": "set_undercut", "step": step number, "width": number, "depth": number}
    An undercut (relief groove, recess) at the root of a shoulder. Width is along the axis, depth is radial.
    Width 0 removes it. A step has a fillet or an undercut, not both: the new one replaces the old one.
{"op": "set_keyway", "index": number or "last", "length": number}
    A keyway (key slot, key seat) on one segment. Give only its length. Length 0 removes it.
    Width and depth come from a standard table by the diameter. Never output them, even if they are spoken.
{"op": "set_fit", "index": number or "last", "fit": string}
    An ISO shaft fit as text, lower case, for example "h6", "k6", "js5". "" removes it. It is a note on the drawing only.
{"op": "set_roughness", "index": number or "last", "ra": number}
    Surface roughness Ra in micrometres, for example 1.6. 0 removes it. It is a note on the drawing only.
{"op": "set_material", "text": string}
    Write the material the way it is written on a drawing: "C45", "42CrMo4", "S355", "1.4301", "aluminium 6082".
{"op": "set_title", "text": string}
{"op": "undo"}
{"op": "finish"}

Rules:
- Never guess. If a number or a target is missing or unclear, return ops [] and ask one short question (under 60 characters).
- A new segment needs both a diameter and a length. If one is missing, ask for it.
- "diameter", "dia", "phi", "Ø", "round" all mean diameter. "long", "length", "by" give the length.
- Numbers may be spoken: "thirty five point five" is 35.5.
- The text comes from speech recognition. Fifteen/fifty, thirteen/thirty, fourteen/forty and so on sound alike.
  If such a number would give an odd part compared with the current shaft, or the text itself shows doubt
  (for example "fifteen or fifty", "fifteen fifty"), ask which one is meant.
- "it", "that one", "this" with no clear target: if the shaft has exactly one segment, use it. Otherwise ask.
  "the last one" is index "last". "the second one" is index 2.
- A bare number for an existing segment ("make the second one twenty-eight") means its diameter.
- A keyway needs a segment and a length. If one is missing, ask for it.
- A fit or a roughness needs a segment. If the shaft has more than one segment and none is named, ask which segment.
  Do not pick the last one by yourself.
- A fillet needs a step and a radius. An undercut needs a step, a width and a depth. If one is missing, ask for it.
  If the shaft has exactly one step, that is the step. "Between the first and the second" is step 1.
  A rounded outer edge of an end is not a fillet here: ask "Fillets are only for shoulders. Which step?"
- Relative changes with no amount ("bigger", "a bit shorter") need a question.
- Relative changes with an amount ("two longer") are fine: compute the new value from the current shaft.
- Several clear changes in one sentence give several operations, in spoken order.
- The text may have this form: first sentence [you asked: your question] answer.
  Then the answer completes the first sentence. Use both parts. If it is still not clear, ask again.
- The sentence may be in Hungarian. Understand it the same way and use the same operations.
  Words: átmérő = diameter, hossz / hosszú = length, szakasz = segment, váll / lépcső = step, letörés = chamfer,
  lekerekítés / rádiusz = fillet, beszúrás / alászúrás = undercut, reteszhorony = keyway, illesztés = fit,
  érdesség = roughness, anyag = material, bal / jobb vég = left / right end, első, második, harmadik = 1, 2, 3,
  utolsó = last, töröld = delete, vissza = undo, kész / vége / befejezés = finish.
  "harmincas" means the number 30. "egész" is the decimal point: "huszonöt egész öt" is 25.5.
  Always write "ask" in English, with no accented letters: the display font is small.
- You cannot approve, release or sign a drawing. If asked, return ops [] and ask "Approval is done by a person on the phone page."
- Do not output geometry, comments or any other text."""


def describe_spec(spec: ShaftSpec) -> str:
    if not spec.segments:
        return "The shaft has no segments yet."
    lines = [f"The shaft has {len(spec.segments)} segment(s):"]
    for i, s in enumerate(spec.segments, start=1):
        extra = []
        if s.chamfer_left:
            extra.append(f"chamfer left {fmt(s.chamfer_left.size)}x{fmt(s.chamfer_left.angle)}")
        if s.chamfer_right:
            extra.append(f"chamfer right {fmt(s.chamfer_right.size)}x{fmt(s.chamfer_right.angle)}")
        for side in ("left", "right"):
            fillet, cut = getattr(s, f"fillet_{side}"), getattr(s, f"undercut_{side}")
            if fillet:
                extra.append(f"fillet {side} R{fmt(fillet)}")
            if cut:
                extra.append(f"undercut {side} {fmt(cut.width)} wide, {fmt(cut.depth)} deep")
        if s.keyway:
            size = keyway_size(s.diameter)
            extra.append(f"keyway {fmt(size.width) if size else '?'} wide, {fmt(s.keyway.length)} long")
        if s.fit:
            extra.append(f"fit {s.fit}")
        if s.roughness:
            extra.append(f"Ra {fmt(s.roughness)}")
        lines.append(f"  {i}: diameter {fmt(s.diameter)}, length {fmt(s.length)}" + (", " + ", ".join(extra) if extra else ""))
    steps = len(spec.segments) - 1
    if steps == 1:
        lines.append("It has exactly one step: step 1. A fillet or undercut with no step named goes to step 1. Do not ask which step.")
    elif steps > 1:
        lines.append(f"It has {steps} steps. Step k is between segment k and segment k+1.")
    lines.append(f"Title: {spec.title}. Material: {spec.material or 'not set'}.")
    return "\n".join(lines)


def build_user_message(spec: ShaftSpec, utterance: str) -> str:
    return f"Current shaft:\n{describe_spec(spec)}\n\nSpoken sentence:\n{json.dumps(utterance, ensure_ascii=False)}"


RETRY_NOTE = "\n\nYour last answer was not valid. Answer with the JSON object only, using only the allowed operations and fields."
