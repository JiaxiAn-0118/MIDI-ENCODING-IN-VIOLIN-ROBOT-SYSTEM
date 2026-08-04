"""音高 → 指法 映射表（决定"每个音在哪根弦、用哪根手指、第几把位拉"）。

为什么需要这张表？
    小提琴有 4 根弦（G/D/A/E，从低到高），同一个音往往能在不同弦、不同把位上拉出来。
    比如 A4 这个音，既能在 D 弦上拉，也能在 A 弦上拉（不同把位）。
    不同选择会影响：换弦频率、左手滑动距离、音色……
    所以我们预先把"每个 MIDI 音高有哪些可行指法"列成一张表，
    再用一个优先级规则挑出默认方案（详见下方 priority 说明）。

什么是"把位（position）"？
    左手沿着琴颈上下滑动，停在不同的位置就叫不同的"把位"。
    第 1 把位最靠近琴头（初学者最常用的位置），把位越高，音越高、手越往琴马方向移。
    低把位更容易、更稳，所以默认优先选低把位（见 priority 设计）。

priority（优先级）的编码约定：
    priority 越小，越优先被选中。本表用"把位×10 + 手指"来构造：
        1~5     → 第 1 把位（最常用，最优先）
        10~13   → 第 2 把位
        20~23   → 第 3 把位
    choose_default() 会优先选 priority 小的，也就是"尽量用低把位、尽量少动"，
    这对机械臂来说最省力、换弦/换把也最少。
"""

from .models import FingeringCandidate
from .note_utils import midi_to_note_name


class ViolinPitchMapper:
    """根据 MIDI 音高，给出推荐的指法方案。"""

    def __init__(self) -> None:
        # 启动时就把整张映射表建好，存进 self._candidates。
        self._candidates = self._build_candidates()

    def get_candidates(self, pitch: int) -> list[FingeringCandidate]:
        """返回某个音高的全部可行指法（可能有多个，也可能没有）。"""
        return list(self._candidates.get(pitch, []))

    def choose_default(self, pitch: int) -> FingeringCandidate:
        """为某个音高挑出"默认推荐"的那一种指法。

        规则：先按 priority 升序排（优先级高的在前），priority 相同时再依次看
              position、finger、string，取最靠前的一个。
        简单说就是"优先低把位、优先省力的手指"。
        """
        candidates = self.get_candidates(pitch)
        if not candidates:
            raise ValueError(f"Pitch {pitch} is outside supported violin mapping range")
        return sorted(candidates, key=lambda item: (item.priority, item.position, item.finger, item.string))[0]

    def _build_candidates(self) -> dict[int, list[FingeringCandidate]]:
        """构造音高 → 指法方案列表 的映射表。

        每行 5 个数字含义是：
            (pitch, 弦名, 把位, 手指, priority)
        """
        rows = [
            # —— 第 1 把位（最常用，priority 1~5）——
            (55, "G", 1, 0, 1), (57, "G", 1, 1, 2), (59, "G", 1, 2, 3), (60, "G", 1, 3, 4), (62, "G", 1, 4, 5),
            (62, "D", 1, 0, 1), (64, "D", 1, 1, 2), (66, "D", 1, 2, 3), (67, "D", 1, 3, 4), (69, "D", 1, 4, 5),
            (69, "A", 1, 0, 1), (71, "A", 1, 1, 2), (73, "A", 1, 2, 3), (74, "A", 1, 3, 4), (76, "A", 1, 4, 5),
            (76, "E", 1, 0, 1), (78, "E", 1, 1, 2), (80, "E", 1, 2, 3), (81, "E", 1, 3, 4), (83, "E", 1, 4, 5),
            # —— 第 2 把位（priority 10~13）——
            (59, "G", 2, 1, 10), (60, "G", 2, 2, 11), (62, "G", 2, 3, 12), (64, "G", 2, 4, 13),
            (66, "D", 2, 1, 10), (67, "D", 2, 2, 11), (69, "D", 2, 3, 12), (71, "D", 2, 4, 13),
            (73, "A", 2, 1, 10), (74, "A", 2, 2, 11), (76, "A", 2, 3, 12), (78, "A", 2, 4, 13),
            (80, "E", 2, 1, 10), (81, "E", 2, 2, 11), (83, "E", 2, 3, 12), (85, "E", 2, 4, 13),
            # —— 第 3 把位（priority 20~23）——
            (60, "G", 3, 1, 20), (62, "G", 3, 2, 21), (64, "G", 3, 3, 22), (65, "G", 3, 4, 23),
            (67, "D", 3, 1, 20), (69, "D", 3, 2, 21), (71, "D", 3, 3, 22), (72, "D", 3, 4, 23),
            (74, "A", 3, 1, 20), (76, "A", 3, 2, 21), (78, "A", 3, 3, 22), (79, "A", 3, 4, 23),
            (81, "E", 3, 1, 20), (83, "E", 3, 2, 21), (85, "E", 3, 3, 22), (86, "E", 3, 4, 23),
        ]
        # 把上面的"扁平表格"整理成 {音高: [各种指法方案]} 的字典。
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
