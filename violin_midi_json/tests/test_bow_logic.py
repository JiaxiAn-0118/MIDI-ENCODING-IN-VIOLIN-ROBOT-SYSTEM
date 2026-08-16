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
