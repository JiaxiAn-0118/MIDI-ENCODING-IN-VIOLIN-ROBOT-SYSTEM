from .models import FingeringCandidate
from .note_utils import midi_to_note_name


class ViolinPitchMapper:
    def __init__(self) -> None:
        self._candidates = self._build_candidates()

    def get_candidates(self, pitch: int) -> list[FingeringCandidate]:
        return list(self._candidates.get(pitch, []))

    def choose_default(self, pitch: int) -> FingeringCandidate:
        candidates = self.get_candidates(pitch)
        if not candidates:
            raise ValueError(f"Pitch {pitch} is outside supported violin mapping range")
        return sorted(candidates, key=lambda item: (item.priority, item.position, item.finger, item.string))[0]

    def _build_candidates(self) -> dict[int, list[FingeringCandidate]]:
        rows = [
            (55, "G", 1, 0, 1), (57, "G", 1, 1, 2), (59, "G", 1, 2, 3), (60, "G", 1, 3, 4), (62, "G", 1, 4, 5),
            (62, "D", 1, 0, 1), (64, "D", 1, 1, 2), (66, "D", 1, 2, 3), (67, "D", 1, 3, 4), (69, "D", 1, 4, 5),
            (69, "A", 1, 0, 1), (71, "A", 1, 1, 2), (73, "A", 1, 2, 3), (74, "A", 1, 3, 4), (76, "A", 1, 4, 5),
            (76, "E", 1, 0, 1), (78, "E", 1, 1, 2), (80, "E", 1, 2, 3), (81, "E", 1, 3, 4), (83, "E", 1, 4, 5),
            (59, "G", 2, 1, 10), (60, "G", 2, 2, 11), (62, "G", 2, 3, 12), (64, "G", 2, 4, 13),
            (66, "D", 2, 1, 10), (67, "D", 2, 2, 11), (69, "D", 2, 3, 12), (71, "D", 2, 4, 13),
            (73, "A", 2, 1, 10), (74, "A", 2, 2, 11), (76, "A", 2, 3, 12), (78, "A", 2, 4, 13),
            (80, "E", 2, 1, 10), (81, "E", 2, 2, 11), (83, "E", 2, 3, 12), (85, "E", 2, 4, 13),
            (60, "G", 3, 1, 20), (62, "G", 3, 2, 21), (64, "G", 3, 3, 22), (65, "G", 3, 4, 23),
            (67, "D", 3, 1, 20), (69, "D", 3, 2, 21), (71, "D", 3, 3, 22), (72, "D", 3, 4, 23),
            (74, "A", 3, 1, 20), (76, "A", 3, 2, 21), (78, "A", 3, 3, 22), (79, "A", 3, 4, 23),
            (81, "E", 3, 1, 20), (83, "E", 3, 2, 21), (85, "E", 3, 3, 22), (86, "E", 3, 4, 23),
        ]
        mapping: dict[int, list[FingeringCandidate]] = {}
        for pitch, string, position, finger, priority in rows:
            mapping.setdefault(pitch, []).append(
                FingeringCandidate(
                    pitch=pitch,
                    note_name=midi_to_note_name(pitch),
                    string=string,
                    position=position,
                    finger=finger,
                    priority=priority,
                )
            )
        return mapping
