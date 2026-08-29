import pytest

from violin_midi_json.models import ConvertedNote
from violin_midi_json.scheduler import ActionType, LeadTimeScheduler, SchedulerConfig


def make_converted_note(
    start: float,
    end: float,
    pitch: int = 69,
    string: str = "A",
    position: int = 1,
    finger: int = 1,
    is_string_change: bool = False,
    is_legato: bool = False,
) -> ConvertedNote:
    return ConvertedNote(
        start=start,
        end=end,
        duration=end - start,
        pitch=pitch,
        note_name="A4",
        string=string,
        position=position,
        finger=finger,
        velocity=80,
        is_string_change=is_string_change,
        is_position_change=False,
        is_legato=is_legato,
        bow_direction="down",
    )


def test_lead_time_scheduling():
    scheduler = LeadTimeScheduler(
        SchedulerConfig(finger_lead_seconds=0.030, string_tilt_lead_seconds=0.050)
    )
    notes = [
        make_converted_note(start=1.0, end=1.5, finger=1, is_string_change=True),
        make_converted_note(start=1.6, end=2.0, finger=2, is_string_change=False),
    ]

    schedules = scheduler.schedule_notes(notes)
    assert len(schedules) == 2

    # 音符 1 (带换弦): 换弦提前 50ms (0.95s), 按弦提前 30ms (0.97s), 起弓 1.0s
    assert schedules[0].string_tilt_time == 0.95
    assert schedules[0].finger_press_time == 0.97
    assert schedules[0].bow_start_time == 1.0
    assert schedules[0].bow_end_time == 1.5

    # 音符 2 (无换弦): 换弦时刻与开始一致 1.6s, 按弦提前 30ms (1.57s), 起弓 1.6s
    assert schedules[1].string_tilt_time == 1.6
    assert schedules[1].finger_press_time == 1.57
    assert schedules[1].bow_start_time == 1.6


def test_timeline_action_generation_order():
    scheduler = LeadTimeScheduler(
        SchedulerConfig(finger_lead_seconds=0.030, string_tilt_lead_seconds=0.050)
    )
    note = make_converted_note(start=1.0, end=1.5, finger=1, is_string_change=True)
    timeline = scheduler.generate_action_timeline([note])

    # 动作顺序应当是: 换弦 (0.95s) -> 按弦 (0.97s) -> 起弓 (1.0s) -> 停弓 (1.5s)
    types = [a.action_type for a in timeline]
    assert types == [
        ActionType.STRING_TILT,
        ActionType.FINGER_PRESS,
        ActionType.BOW_START,
        ActionType.BOW_STOP,
    ]
