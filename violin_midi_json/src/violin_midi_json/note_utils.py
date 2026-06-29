NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note_name(pitch: int) -> str:
    octave = pitch // 12 - 1
    note_name = NOTE_NAMES[pitch % 12]
    return f"{note_name}{octave}"
