"""MIDI 文件解析器（工具链的第一道工序：把 .mid 文件读成音符列表）。

它依赖一个第三方库 pretty_midi——专门用来读取/分析 MIDI 文件的 Python 库。
（运行前需要先安装：pip install pretty_midi）

输出：
    (音符列表, 速度 BPM)
交给下游的 converter.py 去挑选指法、再编码。
"""

from pathlib import Path
from typing import Union

import pretty_midi

from .models import MidiNote


class MidiParser:
    def parse(self, midi_path: Union[str, Path]) -> tuple[list[MidiNote], float]:
        """读取一个 MIDI 文件，返回 (全部音符, 速度)。

        参数:
            midi_path: .mid 文件路径。
        返回:
            notes: 按时间排好序的 MidiNote 列表；
            tempo: 曲子速度（BPM，每分钟多少拍），默认 120。
        """
        # 用 pretty_midi 把整个 MIDI 文件加载进来。
        midi_file = pretty_midi.PrettyMIDI(str(midi_path))
        notes: list[MidiNote] = []

        # 一个 MIDI 文件里可能有多条音轨（instruments，比如钢琴轨、鼓轨）。
        # 我们逐条音轨、逐个音符地收集。
        for instrument in midi_file.instruments:
            if instrument.is_drum:
                # 鼓轨对小提琴没意义，直接跳过。
                continue
            for note in instrument.notes:
                notes.append(
                    MidiNote(
                        start=round(note.start, 6),                       # 开始时间（秒），保留 6 位小数
                        end=round(note.end, 6),                           # 结束时间（秒）
                        duration=round(note.end - note.start, 6),         # 时长 = 结束 - 开始
                        pitch=note.pitch,                                 # MIDI 音高
                        velocity=note.velocity,                           # 力度
                    )
                )

        # 把所有音符按"先开始时间、再音高、再结束时间"排好序，
        # 这样下游按顺序处理时，时间线就是对的。
        notes.sort(key=lambda item: (item.start, item.pitch, item.end))
        # 读取曲子的速度（BPM）。MIDI 里速度可能中途变化，这里取第一个速度段。
        tempo = 120.0
        tempo_changes, tempi = midi_file.get_tempo_changes()
        if len(tempi) > 0:
            tempo = float(tempi[0])
        return notes, tempo
