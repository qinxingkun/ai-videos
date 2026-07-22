"""LTX 对话 prompt 构建（Python 版，供测试脚本使用）。"""

from __future__ import annotations

import re
from typing import Any

SPEAKER_LINE_RE = re.compile(r'^([^:：]+)\s*[:：]\s*["「『]?(.+?)["」』]?\s*$')


def parse_dialogue_lines(text: str | None) -> list[dict[str, str]]:
    if not text or not text.strip():
        return []
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = SPEAKER_LINE_RE.match(line)
        if not m:
            out.append({"speaker": "", "line": line.strip('"「『」』')})
        else:
            out.append({"speaker": m.group(1).strip(), "line": m.group(2).strip()})
    return out


def find_character(characters: list[dict], speaker_name: str) -> dict | None:
    if not speaker_name:
        return None
    for c in characters:
        if c.get("name") == speaker_name:
            return c
    for c in characters:
        name = c.get("name") or ""
        if speaker_name in name or name in speaker_name:
            return c
    return None


def build_cast_block(characters: list[dict] | None = None) -> str:
    characters = characters or []
    if not characters:
        return ""
    descs = []
    for c in characters:
        parts = [c.get("name") or ""]
        age_gender = " ".join(
            x for x in [f"{c['age']} years old" if c.get("age") else "", c.get("gender") or ""] if x
        )
        if age_gender.strip():
            parts.append(age_gender.strip())
        for key in ("face", "hair", "clothing"):
            if c.get(key):
                parts.append(c[key])
        descs.append(", ".join(p for p in parts if p))
    return f" Characters in scene: {'; '.join(descs)}."


def build_speech_block(dialogue_text: str | None, characters: list[dict] | None = None) -> str:
    characters = characters or []
    lines = parse_dialogue_lines(dialogue_text)
    if not lines:
        return ""
    parts = []
    for idx, item in enumerate(lines):
        speaker = item["speaker"]
        quote = item["line"].strip('"「『」』')
        char = find_character(characters, speaker)
        label = (char or {}).get("name") or speaker or "The character"
        voice = (char or {}).get("voice") or (
            "soft female voice" if (char or {}).get("gender") == "female" else "calm male voice"
        )
        if idx == 0:
            parts.append(f'{label} speaks in a {voice} in Mandarin: "{quote}"')
        else:
            parts.append(f'then {label} replies in a {voice} in Mandarin: "{quote}"')
    return " " + ". ".join(parts) + "."


def build_continuity_context(
    *,
    segment_index: int,
    shots: list[dict],
    scene_bible: str = "",
    chained: bool = False,
) -> tuple[str, str]:
    beat = ""
    if 0 <= segment_index < len(shots) and shots[segment_index].get("storyBeat"):
        beat = f" Story beat: {shots[segment_index]['storyBeat']}."

    bridge = ""
    if segment_index > 0 and shots:
        prev = shots[segment_index - 1]
        prev_summary = prev.get("storyBeat") or (prev.get("prompt") or "")[:100]
        total = len(shots) or 6
        parts = [
            f"Continuity: Shot {segment_index + 1} of {total} in one uninterrupted scene.",
            f"Immediately continues from the previous moment: {prev_summary}.",
            "Same characters, same costumes, same weather and lighting as previous shot.",
        ]
        if chained:
            parts.append(
                "The clip starts mid-action with immediate visible motion — no frozen opening."
            )
        bridge = " " + " ".join(parts)
    return bridge, beat


def build_ltx_dialogue_prompt(
    *,
    shot_prompt: str,
    dialogue_text: str = "",
    characters: list[dict] | None = None,
    style_suffix: str = "",
    ambient_sound: str = "soft ambient room tone, rain on roof tiles, natural foley",
    scene_bible: str = "",
    continuity_block: str = "",
    story_beat_block: str = "",
) -> str:
    characters = characters or []
    visual = (shot_prompt or "").strip()
    cast = build_cast_block(characters)
    scene = (
        f" Setting: {scene_bible.strip()} Same location, continuous timeline, no scene jump."
        if scene_bible.strip()
        else ""
    )
    speech = build_speech_block(dialogue_text, characters)
    style = ""
    if style_suffix.strip():
        style = style_suffix if style_suffix.startswith(",") else f", {style_suffix}"

    if not visual.lower().startswith("style:"):
        prompt = f"Style: cinematic realistic.{scene}{(' ' + cast.strip()) if cast else ''} {continuity_block}{story_beat_block} {visual}"
    else:
        prompt = f"{visual}{scene}{cast}{continuity_block}{story_beat_block}"

    if ambient_sound and "ambient" not in speech.lower():
        prompt += f" Ambient sound: {ambient_sound}."
    if speech:
        prompt += speech
    return re.sub(r"\s+", " ", f"{prompt.strip()}{style}").strip()


def build_shot_prompt_with_dialogue(
    *,
    shot_prompt: str,
    dialogue_text: str = "",
    characters: list[dict] | None = None,
    style_suffix: str = "",
    dialogue_mode: bool = True,
    engine: str = "ltx",
    segment_index: int = 0,
    all_shots: list[dict] | None = None,
    scene_bible: str = "",
    chained: bool = False,
) -> str:
    cast = characters or []
    all_shots = all_shots or []
    bridge, beat = build_continuity_context(
        segment_index=segment_index,
        shots=all_shots,
        scene_bible=scene_bible,
        chained=chained or segment_index > 0,
    )
    return build_ltx_dialogue_prompt(
        shot_prompt=shot_prompt,
        dialogue_text=dialogue_text if dialogue_mode and engine == "ltx" else "",
        characters=cast,
        style_suffix=style_suffix,
        scene_bible=scene_bible,
        continuity_block=bridge,
        story_beat_block=beat,
    )
