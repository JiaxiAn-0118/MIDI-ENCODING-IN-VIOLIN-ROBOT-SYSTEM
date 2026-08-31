from violin_midi_json.bow_decision import BowDecisionEngine, BowDecisionOptions
from violin_midi_json.fingering_planner import GlobalFingeringPlanner, OnlineFingeringPlanner
from violin_midi_json.models import MidiNote, build_converted_note
from violin_midi_json.streaming import ListActionSink, MidiMeasureSource, RealtimePipeline


class FakeMeasureSource:
    """按给定批次产出的假 NoteSource，避免测试依赖真实 MIDI 文件。"""

    def __init__(self, measures):
        self.measures = measures

    def iter_measures(self):
        for measure in self.measures:
            yield list(measure)


def make_midi_note(pitch: int, start: float = 0.0, duration: float = 0.5) -> MidiNote:
    return MidiNote(start=start, end=start + duration, duration=duration, pitch=pitch, velocity=64)


def make_scale() -> list[MidiNote]:
    pitches = [69, 71, 73, 74, 76, 78, 80, 81]
    return [make_midi_note(p, i * 0.5) for i, p in enumerate(pitches)]


def _converted_from_fingerings(notes, fingerings):
    converted = []
    previous = None
    for note, fingering in zip(notes, fingerings):
        c = build_converted_note(note, fingering, previous)
        converted.append(c)
        previous = c
    return converted


def test_pipeline_end_to_end_with_online_fingering():
    notes = make_scale()
    source = FakeMeasureSource([notes[:3], notes[3:6], notes[6:]])
    fingering = OnlineFingeringPlanner(window_size=4, lookahead_size=2)
    engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0))
    sink = ListActionSink()

    pipeline = RealtimePipeline(source, fingering, engine, sink, bow_lookahead_size=2)
    pipeline.start()
    pipeline.join()

    assert len(sink.actions) == len(notes)
    for action, note in zip(sink.actions, notes):
        assert action.note.pitch == note.pitch
        assert action.note.string in ("G", "D", "A", "E")
        assert action.note.position in (1, 2, 3)
        assert action.note.finger in (0, 1, 2, 3, 4)
        assert action.decision.bow_direction in (0, 1)


def test_decide_streaming_equivalent_to_decide_all():
    notes = make_scale()
    fingerings = GlobalFingeringPlanner().plan(notes)
    converted = _converted_from_fingerings(notes, fingerings)

    engine_batch = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0))
    batch = engine_batch.decide_all(converted, lookahead_size=2)

    engine_stream = BowDecisionEngine(BowDecisionOptions(tempo_bpm=120.0))
    stream = []
    for i, note in enumerate(converted):
        lookahead = converted[i + 1:i + 3]
        stream.append(engine_stream.decide_streaming(note, lookahead_notes=lookahead))

    assert stream == batch


def test_midi_measure_source_groups_notes_into_measures():
    class FakeParser:
        def parse(self, path):
            notes = [
                make_midi_note(69, 0.0),
                make_midi_note(71, 0.5),
                make_midi_note(73, 2.5),  # 120 BPM -> 一小节 2.0s，此音落入第 2 小节
            ]
            return notes, 120.0

    source = MidiMeasureSource(beats_per_bar=4, parser=FakeParser())
    source.load("dummy.mid")
    measures = list(source.iter_measures())

    assert len(measures) == 2
    assert [n.pitch for n in measures[0]] == [69, 71]
    assert [n.pitch for n in measures[1]] == [73]
    assert source.tempo == 120.0
