from violin_midi_json.bow_decision import BowDecisionEngine, BowDecisionOptions
from violin_midi_json.models import ConvertedNote
from violin_midi_json.constants import BOW_DOWN


def make_note(start, end, pitch=60, string="G"):
    return ConvertedNote(
        start=start,
        end=end,
        duration=end - start,
        pitch=pitch,
        note_name="C4",
        string=string,
        position=1,
        finger=1,
        velocity=64,
        is_string_change=False,
        is_position_change=False,
        is_legato=False,
    )


def test_per_note_bow_speed_mapping():
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0))
    short = make_note(0.0, 0.1)
    long = make_note(0.0, 1.0)

    d_short = engine.decide(short, beat_position=0.0, explicit_legato=False, is_first_note=True)
    # reset engine state for independent long note computation
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0))
    d_long = engine.decide(long, beat_position=0.0, explicit_legato=False, is_first_note=True)

    assert 1 <= d_short.bow_speed <= 10
    assert 1 <= d_long.bow_speed <= 10
    assert d_short.bow_speed >= d_long.bow_speed


def test_legato_preserves_direction_and_reduces_speed():
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0))
    first = make_note(0.0, 0.1)
    second = make_note(0.12, 0.22)

    # first note decide
    d1 = engine.decide(first, beat_position=0.0, explicit_legato=False, is_first_note=True)
    # second note: force explicit legato so direction should be preserved
    d2 = engine.decide(second, beat_position=0.24, explicit_legato=True, is_first_note=False)

    assert d1.bow_direction == d2.bow_direction
    assert d1.needs_reset_bow is False
    assert d2.needs_reset_bow is False
    # legato path reduces speed by 1 at minimum
    assert d2.bow_speed <= d1.bow_speed
