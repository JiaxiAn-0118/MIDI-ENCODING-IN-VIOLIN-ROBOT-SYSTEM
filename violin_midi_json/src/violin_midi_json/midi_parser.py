from pathlib import Path
from typing import Union

import pretty_midi

from .models import MidiNote


class MidiParser:
    def parse(self, midi_path: Union[str, Path]) -> tuple[list[MidiNote], float]:
        midi_file = pretty_midi.PrettyMIDI(str(midi_path))
        notes: list[MidiNote] = []

        for instrument in midi_file.instruments:
            if instrument.is_drum:
                continue
            for note in instrument.notes:
                notes.append(
                    MidiNote(
                        start=round(note.start, 6),
                        end=round(note.end, 6),
                        duration=round(note.end - note.start, 6),
                        pitch=note.pitch,
                        velocity=note.velocity,
                    )
                )

        notes.sort(key=lambda item: (item.start, item.pitch, item.end))
        tempo = 120.0
        tempo_changes, tempi = midi_file.get_tempo_changes()
        if len(tempi) > 0:
            tempo = float(tempi[0])
        return notes, tempo
