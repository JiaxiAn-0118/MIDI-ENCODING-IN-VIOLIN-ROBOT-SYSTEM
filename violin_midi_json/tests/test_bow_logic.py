import pytest

from violin_midi_json.bow_decision import BowDecisionEngine, BowDecisionOptions
from violin_midi_json.constants import BOW_DOWN, BOW_UP
from violin_midi_json.models import ConvertedNote


@pytest.fixture
def note_factory():
    def make_note(start, end, pitch, string="G"):
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

    return make_note


def test_bow_constants_are_instrument_correct():
    assert BOW_DOWN == 0
    assert BOW_UP == 1


def test_first_note_weak_start_prefers_up_bow(note_factory):
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0, implicit_legato_detection=True))
    note = note_factory(0.0, 0.2, 60, string="D")
    decision = engine.decide(note, beat_position=0.3, explicit_legato=False, is_first_note=True)
    assert decision.bow_direction == BOW_UP


def test_legato_keeps_previous_direction_for_same_string(note_factory):
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0, implicit_legato_detection=True))
    prev = note_factory(0.0, 0.2, 60, string="D")
    nxt = note_factory(0.22, 0.42, 62, string="D")

    engine.previous_note = prev
    engine.previous_direction = BOW_DOWN
    decision = engine.decide(nxt, beat_position=0.5, explicit_legato=False, is_first_note=False)

    assert decision.bow_direction == BOW_DOWN
    assert decision.is_legato is True


def test_same_direction_run_breaks_after_three_short_non_legato_notes(note_factory):
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0, implicit_legato_detection=True))
    notes = [
        note_factory(0.0, 0.2, 60, string="D"),
        note_factory(0.5, 0.7, 62, string="D"),
        note_factory(0.9, 1.1, 64, string="D"),
        note_factory(1.3, 1.5, 67, string="D"),
    ]

    engine.previous_note = notes[2]
    engine.previous_direction = BOW_DOWN
    engine.direction_history = [BOW_DOWN, BOW_DOWN, BOW_DOWN]
    engine.current_bow_position = 0.5

    decision = engine.decide(notes[3], beat_position=0.75, explicit_legato=False, is_first_note=False)
    assert decision.bow_direction == BOW_UP


def test_strong_beat_handles_float_edge_case(note_factory):
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0))
    assert engine._is_strong_beat(3.9999999999999995) is True


def test_legato_allows_adjacent_string_crossing(note_factory):
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0, implicit_legato_detection=True))
    prev = note_factory(0.0, 0.25, 60, string="G")
    nxt = note_factory(0.27, 0.52, 64, string="D")

    engine.previous_note = prev
    engine.previous_direction = BOW_DOWN
    assert engine._detect_legato(nxt) is True


def test_string_change_without_legato_uses_practical_violin_rule(note_factory):
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0, implicit_legato_detection=True))
    prev = note_factory(0.0, 0.18, 76, string="E")
    nxt = note_factory(0.20, 0.38, 71, string="A")

    engine.previous_note = prev
    engine.previous_direction = BOW_DOWN
    decision = engine.decide(nxt, beat_position=0.5, explicit_legato=False, is_first_note=False)

    assert decision.bow_direction == BOW_UP
    assert decision.is_legato is False


def test_long_note_at_end_of_bow_forces_retake_on_next_strong_beat(note_factory):
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0, implicit_legato_detection=True))
    prev = note_factory(0.0, 0.9, 62, string="D")
    nxt = note_factory(0.95, 1.05, 64, string="D")

    engine.previous_note = prev
    engine.previous_direction = BOW_DOWN
    engine.current_bow_position = 0.9

    decision = engine.decide(nxt, beat_position=0.0, explicit_legato=False, is_first_note=False)

    assert decision.bow_direction == BOW_UP
    assert decision.needs_reset_bow is False


def test_seconds_to_ticks_clamps_negative_small_offset():
    from violin_midi_json.binary_encoder import BinaryViolinEventEncoder

    enc = BinaryViolinEventEncoder()
    assert enc._seconds_to_ticks(-0.001, "start") == 0


def test_converter_sets_final_legato_and_bow_direction(tmp_path):
    import pretty_midi

    from violin_midi_json.converter import MidiToJsonConverter

    midi_path = tmp_path / "mini.mid"
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)
    instrument.notes = [
        pretty_midi.Note(velocity=64, pitch=62, start=0.0, end=0.24),
        pretty_midi.Note(velocity=64, pitch=64, start=0.26, end=0.5),
    ]
    midi.instruments.append(instrument)
    midi.write(midi_path)

    result = MidiToJsonConverter().convert(midi_path, title="mini")
    assert any(note.is_legato for note in result.notes)
    assert all(note.bow_direction in {"down", "up"} for note in result.notes)
