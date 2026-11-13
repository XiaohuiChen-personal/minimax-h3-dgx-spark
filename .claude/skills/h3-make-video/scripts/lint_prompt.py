#!/usr/bin/env python3
"""Mechanical checks for an H3 prompt file before anyone spends 85 minutes on it.

Catches format slips: section order, shot markers and timestamps, labels, <d> blocks, word count,
keyframe alignment marks, quoted text that H3 may draw on screen. It does not judge whether the prompt
is good; that is the adversarial review.

usage: lint_prompt.py PROMPT_FILE [--duration 15.08] [--refs 6]
exit 0 = no errors (warnings may remain), 1 = errors, 2 = cannot read the file / bad arguments
"""
import argparse
import re
import sys

REF_SECTIONS = ["subject_definitions", "summary", "retention_analysis", "detailed_description",
                "overall_soundscape", "non_diegetic_music"]
BASE_SECTIONS = ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]
TASK_TYPES = {"keyframe completion", "reference generation", "video editing", "video continuation",
              "audio reuse", "audio reference"}
RETENTION_VISUAL = {"fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"}
RETENTION_AUDIO = {"fully_copy", "partially_copy", "reference", "weak_reference"}
LEGAL_DURATIONS = (4.46, 5.17, 8.00, 10.13, 15.08)
FILLER = ("masterpiece", "best quality", "high quality", "ultra detailed", "8k", "4k", "trending on",
          "award-winning", "stunning", "breathtaking", "beautiful", "epic")
LABEL_RE = re.compile(r"<(Subject|Picture|Video|Audio) (\d+)>")
LOOSE_LABEL_RE = re.compile(r"<\s*(subject|picture|video|audio)\s*(\d+)\s*>", re.I)
DEF_LINE_RE = re.compile(r"(?m)^[ \t]*(?:[-*][ \t]+)?<(Subject|Picture|Video|Audio) (\d+)>")
SHOT_RE = re.compile(r"\[Shot (\d+)\]")
# A shot marker starts the body, a line, or a sentence; "[Shot 2]" mid-sentence is a back-reference.
MARKER_CONTEXT = re.compile(r"(^|\n|[.!?\"”)>]\s+|:\s*)$")   # ">" = right after a </d> block


def sections(text, names):
    """Return ({name: (start_index, body)}, order, duplicates) for 'name:' headers at line starts."""
    found = []
    for name in names:
        for m in re.finditer(rf"(?m)^{re.escape(name)}:[ \t]*", text):
            found.append((m.start(), m.end(), name))
    found.sort()
    out, order, dupes = {}, [], []
    for k, (s, e, name) in enumerate(found):
        end = found[k + 1][0] if k + 1 < len(found) else len(text)
        if name in out:
            dupes.append(name)
        out[name] = (s, text[e:end].strip())
        order.append(name)
    return out, order, dupes


def shot_markers(body):
    """-> (markers [(num, start, end)], references [num]) using position and expected numbering."""
    markers, refs = [], []
    for m in SHOT_RE.finditer(body):
        num = int(m.group(1))
        expected = len(markers) + 1
        at_boundary = bool(MARKER_CONTEXT.search(body[:m.start()]))
        if num == expected and at_boundary:
            markers.append((num, m.start(), m.end()))
        elif at_boundary and num > expected:
            markers.append((num, m.start(), m.end()))     # skipped number: reported by the caller
        else:
            refs.append(num)
    return markers, refs


def check(text, duration=None, refs=None):
    errors, warnings, notes = [], [], []
    text = text.replace("\r\n", "\n")
    if "subject_definitions:" in text:
        family, names = "Ref2VA", REF_SECTIONS
    elif "integrated_multimodal_description:" in text:
        family, names = "FL2VA", BASE_SECTIONS
    else:
        return ["no section headers found (need subject_definitions: ... or integrated_multimodal_description: ...)"], [], []
    secs, order, dupes = sections(text, names)
    notes.append(f"family: {family}")
    for d in sorted(set(dupes)):
        errors.append(f"section '{d}:' appears more than once")
    missing = [n for n in names if n not in secs]
    for m in missing:
        errors.append(f"missing section '{m}:'")
    present = [n for n in order if n in names]
    if not missing and present != names:
        errors.append("sections out of order: " + " > ".join(present) + " (expected " + " > ".join(names) + ")")
    first_header = min((s for s, _ in secs.values()), default=0)
    preamble = text[:first_header].strip()
    if family == "Ref2VA" and preamble:
        errors.append("text before 'subject_definitions:' (Ref2VA prompts start with the section header)")
    if family == "FL2VA" and preamble and not preamble.startswith(("For the target video", "How the reference pictures")):
        errors.append("text before 'integrated_multimodal_description:' that is not a keyframe alignment line")

    for field in ("overall_soundscape", "non_diegetic_music"):
        if field in secs:
            if not secs[field][1]:
                errors.append(f"'{field}:' is empty (write it, or N/A on purpose)")
            if "<d>" in secs[field][1]:
                errors.append(f"<d> dialogue inside '{field}:'; dialogue and lyrics belong in the description")

    body_name = "detailed_description" if family == "Ref2VA" else "integrated_multimodal_description"
    body = secs.get(body_name, (0, ""))[1]

    # Shots and timestamps.
    shots, shot_refs = shot_markers(body)
    if not shots:
        errors.append(f"no [Shot 1] at the start of a line or sentence in {body_name}")
    else:
        nums = [s[0] for s in shots]
        if nums != list(range(1, len(nums) + 1)):
            errors.append(f"shot numbers are not 1..N in order: {nums}")
        if family == "Ref2VA" and not body[:shots[0][1]].strip():
            errors.append("detailed_description has no style sentence before [Shot 1]")
        times = []
        for num, s, e in shots:
            m = re.match(r"\s*At (\d{2}):(\d{2})\.(\d{3})\b", body[e:e + 40])
            if num == 1:
                if m:
                    errors.append("[Shot 1] must not carry a timestamp")
                continue
            if not m:
                errors.append(f"[Shot {num}] must start 'At MM:SS.mmm, the camera cuts to ...'")
                continue
            if int(m.group(2)) >= 60:
                errors.append(f"[Shot {num}] timestamp {m.group(1)}:{m.group(2)}.{m.group(3)} has seconds >= 60")
            times.append((num, int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 1000.0))
        prev = 0.0
        for num, t in times:
            if t <= prev:
                errors.append(f"[Shot {num}] at {t:.3f} s is not after the previous cut ({prev:.3f} s)")
            if duration and t >= duration:
                errors.append(f"[Shot {num}] at {t:.3f} s is not inside the {duration:.2f} s clip")
            prev = t
        if duration:
            bounds = [0.0] + [t for _, t in times] + [duration]
            lens = [b - a for a, b in zip(bounds, bounds[1:])]
            notes.append("shot lengths: " + ", ".join(f"{x:.2f} s" for x in lens))
            for k, x in enumerate(lens, 1):
                if 0 < x < 1.5:
                    warnings.append(f"shot {k} lasts {x:.2f} s; very short shots rarely land")
    n_shots = len(shots)
    for r in shot_refs:
        if r > n_shots:
            errors.append(f"[Shot {r}] is referenced but the prompt has only {n_shots} shot(s)")

    if duration and not any(abs(duration - d) < 0.006 for d in LEGAL_DURATIONS):
        warnings.append(f"duration {duration} is not one of the legal lengths {LEGAL_DURATIONS}")

    # Keyframe alignment lines (FL2VA keyframe tasks).
    if family == "FL2VA" and preamble:
        marks = [float(x) for x in re.findall(r"(\d+\.\d{2})-second mark", preamble)]
        marks += [float(x) for x in re.findall(r"at (\d+\.\d{2}) seconds into the target video", preamble)]
        for mk in marks:
            if duration and mk > duration + 0.005:
                errors.append(f"keyframe aligned at {mk:.2f} s, beyond the {duration:.2f} s clip")
        later = [mk for mk in marks if mk > 0]
        if duration and later and abs(max(later) - duration) > 0.005:
            warnings.append(f"last keyframe aligns at {max(later):.2f} s but the clip is {duration:.2f} s; "
                            "a last frame normally aligns with the clip end")

    words = len(body.split())
    notes.append(f"{body_name}: {words} words (whitespace count)")
    if family == "Ref2VA" and not 350 <= words <= 500:
        warnings.append(f"detailed_description has {words} words; generation prompts are normally 350-500")

    # Labels.
    for m in LOOSE_LABEL_RE.finditer(text):
        if not LABEL_RE.fullmatch(m.group(0)):
            errors.append(f"malformed label {m.group(0)!r}: write <{m.group(1).capitalize()} {m.group(2)}>")
    used = {(k, int(n)) for k, n in LABEL_RE.findall(text)}
    for k, n in sorted(used):
        if n == 0:
            errors.append(f"<{k} 0>: labels are 1-based")
    pics = sorted(n for k, n in used if k == "Picture")
    if family == "Ref2VA":
        sd = secs.get("subject_definitions", (0, ""))[1]
        own_line = {(k, int(n)) for k, n in DEF_LINE_RE.findall(sd)}
        cited_in_defs = {(k, int(n)) for k, n in LABEL_RE.findall(sd)}
        for k, n in sorted(used):
            if k == "Subject" and (k, n) not in own_line:
                errors.append(f"<Subject {n}> is used but has no definition line in subject_definitions")
            elif k in ("Video", "Audio") and (k, n) not in cited_in_defs:
                errors.append(f"<{k} {n}> is used but never defined or cited in subject_definitions")
        def_lines = {}
        for ln in sd.splitlines():
            m = DEF_LINE_RE.match(ln)
            if m:
                def_lines[(m.group(1), int(m.group(2)))] = ln
        for (k, n), ln in sorted(def_lines.items()):
            if k == "Subject" and f"<Subject {n}>" not in body:
                if "<Picture" in ln:
                    errors.append(f"<Subject {n}> has stills but never appears in detailed_description")
                else:
                    warnings.append(f"<Subject {n}> is defined but never appears in detailed_description")
        summ = secs.get("summary", (0, ""))[1]
        m = re.match(r"\[([^\]]+)\]", summ)
        if not m:
            errors.append("summary must start with a task tag such as [reference generation]")
        else:
            bad = [t.strip() for t in m.group(1).split("+") if t.strip() not in TASK_TYPES]
            if bad:
                errors.append(f"unknown task type(s) in summary tag: {bad}")
        for k, n in sorted({(k, int(n)) for k, n in LABEL_RE.findall(summ)} - cited_in_defs):
            errors.append(f"summary introduces <{k} {n}>, which subject_definitions never mentions")
        ra = secs.get("retention_analysis", (0, ""))[1]
        for k, n in sorted(own_line):
            line = next((ln for ln in ra.splitlines()
                         if re.match(rf"^[ \t]*(?:[-*][ \t]+)?<{k} {n}>", ln)), None)
            if line is None:
                errors.append(f"retention_analysis has no line for <{k} {n}>")
                continue
            markers = RETENTION_AUDIO if k == "Audio" else RETENTION_VISUAL
            mk = re.search(r":\s*([a-z_]+)\s*-", line)
            if not mk or mk.group(1) not in markers:
                errors.append(f"retention_analysis line for <{k} {n}> needs ': <marker> - ...' with one of {sorted(markers)}")
            if re.search(r"\(S\d+\)", line):
                errors.append(f"retention_analysis line for <{k} {n}> carries a speaker ID; speaker IDs belong in detailed_description")
            if k == "Subject":
                claimed = {int(x) for x in re.findall(r"\[Shot (\d+)\]", line)}
                for c in sorted(claimed):
                    if c < 1 or c > n_shots:
                        errors.append(f"retention_analysis says <Subject {n}> appears in [Shot {c}], "
                                      f"but there are {n_shots} shot(s)")
                actual = set()
                for j, (num, s, e) in enumerate(shots):
                    end = shots[j + 1][1] if j + 1 < len(shots) else len(body)
                    if f"<Subject {n}>" in body[s:end]:
                        actual.add(num)
                if claimed and actual and claimed != actual:
                    warnings.append(f"<Subject {n}>: retention_analysis says shots {sorted(claimed)}, "
                                    f"detailed_description names it in shots {sorted(actual)} (an off-screen "
                                    "mention also counts; fine if it is not visible there)")
    elif pics and not preamble:
        errors.append("<Picture N> on a text-only FL2VA prompt (no keyframe alignment line)")
    if refs is not None:
        for n in pics:
            if n > refs:
                errors.append(f"<Picture {n}> but only {refs} still(s) will be attached")
        if family == "Ref2VA":
            for n in range(1, refs + 1):
                if n not in pics:
                    warnings.append(f"still {n} is attached but <Picture {n}> is never cited")

    # Speech.
    opens, closes = text.count("<d>"), text.count("</d>")
    if opens != closes:
        errors.append(f"unbalanced <d> blocks: {opens} <d> vs {closes} </d>")
    for m in re.finditer(r"<d>(.*?)</d>", text, re.S):
        if not re.match(r"\[[^\]]+\]\s", m.group(1)):
            errors.append(f"<d> block without a [Language] tag: <d>{m.group(1)[:40]}")
        before = text[max(0, m.start() - 200):m.start()]
        if not re.search(r"\(S\d+(,S\d+)*\)", before):
            warnings.append(f"<d> block with no (Sx) speaker ID shortly before it: <d>{m.group(1)[:40]}")
    notes.append("speech: " + (f"{opens} <d> block(s)" if opens else "none (no <d> block = no intended speech)"))

    # Things H3 may take literally. Dialogue inside <d> is the user's own words: skip it.
    no_dialogue = re.sub(r"<d>.*?</d>", " ", text, flags=re.S)
    nd_secs, _, _ = sections(no_dialogue, names)
    for name, (_, sbody) in nd_secs.items():
        if name in ("overall_soundscape", "non_diegetic_music"):
            continue
        for m in re.finditer(r"[\"“]([^\"”\n]{1,60})[\"”]", sbody):
            warnings.append(f'quoted text "{m.group(1)}" in {name}: quotes mark visible on-screen text. '
                            "Keep them only if it should be drawn in the frame")
    low = no_dialogue.lower()
    for word in FILLER:
        if re.search(rf"\b{re.escape(word)}\b", low):
            warnings.append(f"filler word '{word}': say what is visible instead")
    if re.search(r"negative prompt|guidance[_ ]scale|\bcfg\b", low):
        errors.append("mentions a negative prompt / CFG; H3 is CFG-distilled and has one prompt only")

    dedupe = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    return dedupe(errors), dedupe(warnings), notes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt_file")
    p.add_argument("--duration", type=float, help="clip length in seconds (graph length / 24)")
    p.add_argument("--refs", type=int, help="number of stills that will be attached")
    a = p.parse_args(argv)
    try:
        text = open(a.prompt_file, encoding="utf-8").read()
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    errors, warnings, notes = check(text, a.duration, a.refs)
    for n in notes:
        print(f"note: {n}")
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
