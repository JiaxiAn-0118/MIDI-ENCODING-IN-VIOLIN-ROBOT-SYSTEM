import pytest

from violin_midi_json.fingering_planner import FingeringCostWeights, GlobalFingeringPlanner
from violin_midi_json.mapping import ViolinPitchMapper
from violin_midi_json.models import MidiNote


def make_midi_note(pitch: int, start: float = 0.0, duration: float = 0.5) -> MidiNote:
    return MidiNote(
        start=start,
        end=start + duration,
        duration=duration,
        pitch=pitch,
        velocity=64,
    )


def test_empty_notes_sequence():
    planner = GlobalFingeringPlanner()
    assert planner.plan([]) == []


def test_single_note_planning():
    planner = GlobalFingeringPlanner()
    note = make_midi_note(69)  # A4
    candidates = planner.plan([note])
    assert len(candidates) == 1
    # A4 默认第 1 把位 A 弦 0 指
    assert candidates[0].pitch == 69
    assert candidates[0].string in ("A", "D")


def test_dp_minimizes_string_crossings_in_scale():
    planner = GlobalFingeringPlanner()
    # A 弦上的音阶: A4(69), B4(71), C#5(73), D5(74)
    scale_notes = [
        make_midi_note(69, 0.0),
        make_midi_note(71, 0.5),
        make_midi_note(73, 1.0),
        make_midi_note(74, 1.5),
    ]
    planned = planner.plan(scale_notes)
    assert len(planned) == 4
    # 全局规划应该让同一把位/同一琴弦上的音符保持在同一根弦上
    strings = [p.string for p in planned]
    assert strings == ["A", "A", "A", "A"]
    fingers = [p.finger for p in planned]
    assert fingers == [0, 1, 2, 3]


def test_invalid_pitch_raises_error():
    planner = GlobalFingeringPlanner()
    out_of_range_note = make_midi_note(20)  # 超出小提琴音域
    with pytest.raises(ValueError, match="超出支持的小提琴音高映射范围"):
        planner.plan([out_of_range_note])
