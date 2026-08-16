"""弓向决策模块：基于节拍、时值、连音和弓位规则，返回每个音符的 bow_direction 和 is_legato 标记。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import (
    BOW_DOWN,
    BOW_UP,
    DEFAULT_LEGATO_GAP_SECONDS,
    DEFAULT_LEGATO_MAX_INTERVAL,
    STRING_ORDER,
)
from .models import ConvertedNote


@dataclass(frozen=True)
class BowDecisionOptions:
    """决策器可配置参数。"""
    tempo_bpm: float
    beats_per_bar: int = 4
    beat_unit: int = 4
    legato_gap_seconds: float = DEFAULT_LEGATO_GAP_SECONDS
    legato_max_interval: int = DEFAULT_LEGATO_MAX_INTERVAL
    implicit_legato_detection: bool = True


@dataclass(frozen=True)
class BowDecision:
    """单个音符的弓向决策结果。"""
    bow_direction: int
    is_legato: bool
    is_strong_beat: bool
    needs_reset_bow: bool
    beat_position: float


class BowDecisionEngine:
    """规则化弓向决策器。

    采用层次化规则：
      1) 节拍与强弱律动：强拍倾向下弓，弱拍倾向上弓；
      2) 时值与弓长平衡：长音优先下弓，快音优先交替；
      3) 隐式连音判定：短间隔同弦保留当前弓向；
      4) 机器人物理约束：弓位临界时强制纠偏。
    """

    def __init__(self, options: BowDecisionOptions) -> None:
        self.options = options
        self.current_bow_position = 0.0
        self.previous_note: Optional[ConvertedNote] = None
        self.previous_direction = BOW_DOWN

    def decide(
        self,
        note: ConvertedNote,
        beat_position: float,
        explicit_legato: bool = False,
        is_first_note: bool = False,
    ) -> BowDecision:
        """根据当前音符和拍位，返回应当传给编码器的 BowDecision。"""
        is_strong_beat = self._is_strong_beat(beat_position)
        is_legato = explicit_legato
        if not is_legato and self.options.implicit_legato_detection:
            is_legato = self._detect_legato(note)

        if is_legato:
            direction = self.previous_direction
        else:
            direction = self._decide_direction(note, is_strong_beat, is_first_note)

        needs_reset_bow = self._needs_bow_reset(direction)
        if needs_reset_bow:
            direction = BOW_UP if direction == BOW_DOWN else BOW_DOWN

        self.previous_direction = direction
        self.previous_note = note
        self.current_bow_position = self._update_bow_position(direction, note)

        return BowDecision(
            bow_direction=direction,
            is_legato=is_legato,
            is_strong_beat=is_strong_beat,
            needs_reset_bow=needs_reset_bow,
            beat_position=beat_position,
        )

    def _is_strong_beat(self, beat_position: float) -> bool:
        beat_in_bar = round(beat_position % float(self.options.beats_per_bar), 4)
        if beat_in_bar >= self.options.beats_per_bar:
            beat_in_bar = 0.0
        strong_positions = [0.0]
        if self.options.beats_per_bar >= 4:
            strong_positions.append(2.0)
        return any(abs(beat_in_bar - p) < 1e-4 for p in strong_positions)

    def _detect_legato(self, note: ConvertedNote) -> bool:
        if self.previous_note is None:
            return False

        time_gap = note.start - self.previous_note.end
        interval = abs(note.pitch - self.previous_note.pitch)

        same_string = note.string == self.previous_note.string
        string_diff = 0
        if not same_string:
            prev_index = STRING_ORDER.get(self.previous_note.string)
            curr_index = STRING_ORDER.get(note.string)
            if prev_index is None or curr_index is None:
                return False
            string_diff = abs(curr_index - prev_index)
            if string_diff > 1:
                return False

        return (
            time_gap <= self.options.legato_gap_seconds
            and interval <= self.options.legato_max_interval
            and (same_string or string_diff == 1)
        )

    def _decide_direction(
        self,
        note: ConvertedNote,
        is_strong_beat: bool,
        is_first_note: bool,
    ) -> int:
        if is_first_note and not is_strong_beat:
            return BOW_UP
        if note.duration >= self._long_note_threshold():
            return BOW_DOWN
        if self.previous_note is not None and self._is_strict_fast_alternation(note):
            return BOW_UP if self.previous_direction == BOW_DOWN else BOW_DOWN
        if self._should_force_down_after_rest(note, is_strong_beat):
            return BOW_DOWN
        return BOW_DOWN if is_strong_beat else BOW_UP

    def _long_note_threshold(self) -> float:
        quarter_sec = 60.0 / self.options.tempo_bpm
        return quarter_sec * 1.5

    def _is_strict_fast_alternation(self, note: ConvertedNote) -> bool:
        if self.previous_note is None:
            return False
        time_gap = note.start - self.previous_note.start
        quarter_sec = 60.0 / self.options.tempo_bpm
        return time_gap <= quarter_sec / 4.0 and note.duration <= quarter_sec / 2.0

    def _should_force_down_after_rest(self, note: ConvertedNote, is_strong_beat: bool) -> bool:
        if self.previous_note is None or not is_strong_beat:
            return False
        rest_gap = note.start - self.previous_note.end
        quarter_sec = 60.0 / self.options.tempo_bpm
        return rest_gap >= quarter_sec * 0.75

    def _needs_bow_reset(self, direction: int) -> bool:
        if direction == BOW_DOWN and self.current_bow_position > 0.85:
            return True
        if direction == BOW_UP and self.current_bow_position < 0.15:
            return True
        return False

    def _update_bow_position(self, direction: int, note: ConvertedNote) -> float:
        quarter_sec = 60.0 / self.options.tempo_bpm
        delta = note.duration / quarter_sec
        delta = min(max(delta * 0.25, 0.01), 0.25)
        if direction == BOW_DOWN:
            return min(1.0, self.current_bow_position + delta)
        return max(0.0, self.current_bow_position - delta)
