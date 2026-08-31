"""转换总指挥（把前面几个零件串起来：解析 MIDI → 选指法 → 编码输出）。

数据在这一个文件里走完整条流水线：

    .mid 文件
        │  ① MidiParser 解析
        ▼
    原始音符列表(只有音高/时间/力度)
        │  ② ViolinPitchMapper 给每个音选指法(弦/手指/把位)
        ▼
    带指法的音符列表(ConvertedNote)
        │  ③ 汇总成 ConversionResult
        ▼
    .json（给人看）/ .bin（给 Arduino）

对外的三个方法就是这条流水线的入口，CLI(cli.py) 调用的就是它们。
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Optional, Union

from .binary_encoder import BinaryViolinEventEncoder
from .bow_decision import BowDecisionEngine, BowDecisionOptions
from .constants import BOW_DOWN
from .fingering_planner import GlobalFingeringPlanner
from .mapping import ViolinPitchMapper
from .midi_parser import MidiParser
from .models import ConversionMeta, ConversionResult, ConvertedNote, build_converted_note
from .scheduler import LeadTimeScheduler


class MidiToJsonConverter:
    """MIDI 转换器：协调 解析器 / 指法规划 / 二进制编码 / 时序调度 多个模块。"""

    def __init__(
        self,
        parser: Optional[MidiParser] = None,
        mapper: Optional[ViolinPitchMapper] = None,
        binary_encoder: Optional[BinaryViolinEventEncoder] = None,
        fingering_planner: Optional[GlobalFingeringPlanner] = None,
        scheduler: Optional[LeadTimeScheduler] = None,
        use_global_planning: bool = True,
    ) -> None:
        # 如果调用方没指定零件，就用默认实现。这样既能"开箱即用"，
        # 也方便测试时替换成假对象。
        self.parser = parser or MidiParser()
        self.mapper = mapper or ViolinPitchMapper()
        self.binary_encoder = binary_encoder or BinaryViolinEventEncoder()
        self.fingering_planner = fingering_planner or GlobalFingeringPlanner(self.mapper)
        self.scheduler = scheduler or LeadTimeScheduler()
        self.use_global_planning = use_global_planning

    def convert(self, midi_path: Union[str, Path], title: Optional[str] = None) -> ConversionResult:
        """把一个 MIDI 文件转换成完整的 ConversionResult（含全部带指法的音符）。

        参数:
            midi_path: 输入的 .mid 文件路径。
            title:     曲名；不填则用文件名（去掉扩展名）。
        """
        # ① 解析 MIDI：拿到原始音符 + 速度。
        notes, tempo = self.parser.parse(midi_path)
        converted_notes: list[ConvertedNote] = []
        previous_note: Optional[ConvertedNote] = None

        # ② 指法选择：优先使用 DP 全局指法规划，也可降级为局部默认映射。
        if self.use_global_planning and notes:
            planned_fingerings = self.fingering_planner.plan(notes)
        else:
            planned_fingerings = [self.mapper.choose_default(n.pitch) for n in notes]

        for note, fingering in zip(notes, planned_fingerings):
            # 用共用的组装工序把「原始音符 + 选定指法」合成 ConvertedNote（实时链路也复用此函数）。
            converted = build_converted_note(note, fingering, previous_note)
            converted_notes.append(converted)
            previous_note = converted  # 记住本音，供下一个音做比较

        # ③ 用与二进制编码一致的弓向决策器批量计算最终的 legato / bow_direction。
        bow_engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=tempo))
        decisions = bow_engine.decide_all(converted_notes, lookahead_size=2)
        for index, (note, decision) in enumerate(zip(converted_notes, decisions)):
            converted_notes[index] = replace(
                note,
                is_legato=decision.is_legato,
                bow_direction="down" if decision.bow_direction == BOW_DOWN else "up",
            )

        # ④ 汇总曲子元信息（曲名/速度/来源/音符数）。
        meta = ConversionMeta(
            title=title or Path(midi_path).stem,  # 没给曲名就用文件名
            tempo=round(tempo, 3),
            source_midi=str(midi_path),
            note_count=len(converted_notes),
        )
        return ConversionResult(meta=meta, notes=converted_notes)

    def convert_to_json_file(self, midi_path: Union[str, Path], output_path: Union[str, Path], title: Optional[
    str] = None) -> None:
        """转换后写成 .json 文件（每个音符的字段一目了然，适合人看和调试）。"""
        result = self.convert(midi_path=midi_path, title=title)
        output = Path(output_path)
        # ensure_ascii=False 保证中文曲名等不会被转成 \uXXXX 乱码。
        output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def convert_to_binary_file(
        self,
        midi_path: Union[str, Path],
        output_path: Union[str, Path],
        title: Optional[str] = None,
    ) -> None:
        """转换后写成 .bin 文件（紧凑二进制曲谱，直接喂给 Arduino）。"""
        result = self.convert(midi_path=midi_path, title=title)
        self.binary_encoder.write_result(result=result, output_path=output_path)
