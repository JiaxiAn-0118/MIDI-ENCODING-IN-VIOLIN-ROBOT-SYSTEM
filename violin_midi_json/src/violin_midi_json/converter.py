import json
from pathlib import Path
from typing import Optional, Union

from .binary_encoder import BinaryViolinEventEncoder
from .mapping import ViolinPitchMapper
from .midi_parser import MidiParser
from .models import ConversionMeta, ConversionResult, ConvertedNote


class MidiToJsonConverter:
    def __init__(
        self,
        parser: Optional[MidiParser] = None,
        mapper: Optional[ViolinPitchMapper] = None,
        binary_encoder: Optional[BinaryViolinEventEncoder] = None,
    ) -> None:
        self.parser = parser or MidiParser()
        self.mapper = mapper or ViolinPitchMapper()
        self.binary_encoder = binary_encoder or BinaryViolinEventEncoder()

    def convert(self, midi_path: Union[str, Path], title: Optional[str] = None) -> ConversionResult:
        notes, tempo = self.parser.parse(midi_path)
        converted_notes: list[ConvertedNote] = []
        previous_note: Optional[ConvertedNote] = None

        for note in notes:
            fingering = self.mapper.choose_default(note.pitch)
            converted = ConvertedNote(
                start=note.start,
                end=note.end,
                duration=note.duration,
                pitch=note.pitch,
                note_name=fingering.note_name,
                string=fingering.string,
                position=fingering.position,
                finger=fingering.finger,
                velocity=note.velocity,
                is_string_change=previous_note is not None and previous_note.string != fingering.string,
                is_position_change=previous_note is not None and previous_note.position != fingering.position,
            )
            converted_notes.append(converted)
            previous_note = converted

        meta = ConversionMeta(
            title=title or Path(midi_path).stem,
            tempo=round(tempo, 3),
            source_midi=str(midi_path),
            note_count=len(converted_notes),
        )
        return ConversionResult(meta=meta, notes=converted_notes)

    def convert_to_json_file(self, midi_path: Union[str, Path], output_path: Union[str, Path], title: Optional[
        str] = None) -> None:
        result = self.convert(midi_path=midi_path, title=title)
        output = Path(output_path)
        output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def convert_to_binary_file(
        self,
        midi_path: Union[str, Path],
        output_path: Union[str, Path],
        title: Optional[str] = None,
    ) -> None:
        result = self.convert(midi_path=midi_path, title=title)
        self.binary_encoder.write_result(result=result, output_path=output_path)
