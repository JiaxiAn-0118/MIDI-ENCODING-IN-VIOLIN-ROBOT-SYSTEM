from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MidiNote:
    start: float
    end: float
    duration: float
    pitch: int
    velocity: int


@dataclass(frozen=True)
class FingeringCandidate:
    pitch: int
    note_name: str
    string: str
    position: int
    finger: int
    priority: int


@dataclass(frozen=True)
class ConvertedNote:
    start: float
    end: float
    duration: float
    pitch: int
    note_name: str
    string: str
    position: int
    finger: int
    velocity: int
    is_string_change: bool
    is_position_change: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversionMeta:
    title: str
    tempo: float
    source_midi: str
    note_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversionResult:
    meta: ConversionMeta
    notes: list[ConvertedNote]

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "notes": [note.to_dict() for note in self.notes],
        }
