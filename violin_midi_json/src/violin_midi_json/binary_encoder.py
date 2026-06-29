from pathlib import Path
from typing import Union

from .models import ConversionResult, ConvertedNote


HEADER = 0xA5
TICK_SECONDS = 0.01
PACKET_SIZE = 12

STRING_IDS = {
    "G": 0,
    "D": 1,
    "A": 2,
    "E": 3,
}

BOW_UP = 0
BOW_DOWN = 1


class BinaryViolinEventEncoder:
    """Encode converted violin notes into Binary Violin Event Protocol V1 packets."""

    def __init__(
        self,
        tick_seconds: float = TICK_SECONDS,
        default_bow_speed: int = 5,
        default_bow_force: int = 4,
    ) -> None:
        self.tick_seconds = tick_seconds
        self.default_bow_speed = default_bow_speed
        self.default_bow_force = default_bow_force

    def encode_result(self, result: ConversionResult) -> bytes:
        packets = [
            self.encode_note(note=note, note_index=index)
            for index, note in enumerate(result.notes)
        ]
        return b"".join(packets)

    def write_result(self, result: ConversionResult, output_path: Union[str, Path]) -> None:
        Path(output_path).write_bytes(self.encode_result(result))

    def encode_note(self, note: ConvertedNote, note_index: int) -> bytes:
        tick = self._seconds_to_ticks(note.start, "start")
        duration = self._seconds_to_ticks(note.duration, "duration")
        midi_pitch = self._uint8(note.pitch, "pitch")

        string_finger = (
            (self._string_id(note.string) << 6)
            | (self._uint3(note.finger, "finger") << 3)
            | self._uint3(note.position, "position")
        )
        bow_direction = BOW_DOWN if note_index % 2 == 0 else BOW_UP
        bow = (bow_direction << 7) | self._uint7(self.default_bow_speed, "bow_speed")
        bow_force = self._uint8(self.default_bow_force, "bow_force")
        flags = 0
        reserved = 0

        body = bytes(
            [
                HEADER,
                tick & 0xFF,
                (tick >> 8) & 0xFF,
                midi_pitch,
                duration & 0xFF,
                (duration >> 8) & 0xFF,
                string_finger,
                bow,
                bow_force,
                flags,
                reserved,
            ]
        )
        checksum = sum(body) & 0xFF
        return body + bytes([checksum])

    def _seconds_to_ticks(self, seconds: float, field_name: str) -> int:
        value = round(seconds / self.tick_seconds)
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"{field_name} {seconds} s is outside uint16 tick range")
        return value

    def _string_id(self, string: str) -> int:
        try:
            return STRING_IDS[string]
        except KeyError as exc:
            raise ValueError(f"Unsupported violin string: {string}") from exc

    def _uint3(self, value: int, field_name: str) -> int:
        if not 0 <= value <= 0x07:
            raise ValueError(f"{field_name} {value} is outside 3-bit range")
        return value

    def _uint7(self, value: int, field_name: str) -> int:
        if not 0 <= value <= 0x7F:
            raise ValueError(f"{field_name} {value} is outside 7-bit range")
        return value

    def _uint8(self, value: int, field_name: str) -> int:
        if not 0 <= value <= 0xFF:
            raise ValueError(f"{field_name} {value} is outside uint8 range")
        return value
