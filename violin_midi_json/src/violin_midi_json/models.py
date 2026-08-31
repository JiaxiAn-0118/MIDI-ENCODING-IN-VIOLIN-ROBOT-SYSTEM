"""数据模型（整个工具链里用来"装数据"的容器）。

为什么有这么多 class？
    从 MIDI 读进来的是一串音符，转换过程中要经过几道工序：
        原始 MIDI 音符 → 选好指法的音符 → 最终结果
    每一道都用一个"数据类"把相关字段打包在一起，方便传递、也方便最后导出 JSON。

什么是 @dataclass？
    这是 Python 的一个语法糖：只要写出字段，Python 就会自动帮我们生成
    构造函数（不用手写 __init__）、比较、打印等常用功能，代码更简洁。
    frozen=True 表示"不可变"——创建后不能再改字段值，相当于一个只读的常量结构，
    这样多人/多函数传递时不会被意外改坏，更安全。

本文件里的四个类，从"原始"到"成品"依次是：
    MidiNote           ① 从 MIDI 文件读出来的原始音符（只有音高、时间、力度）
    FingeringCandidate ② 某个音的"一种指法方案"（哪个音、在哪根弦、哪根手指、第几把位）
    ConvertedNote      ③ 选定指法后的最终音符（给机械臂用的完整信息）
    ConversionMeta / ConversionResult ④ 一整首曲子的元信息 + 全部音符的汇总
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MidiNote:
    """① 原始 MIDI 音符（直接从 .mid 文件里读出来的）。"""

    start: float       # 开始时间（秒）
    end: float         # 结束时间（秒）
    duration: float    # 持续时长（秒）= end - start
    pitch: int         # MIDI 音高编号（如 69 = A4），详见 note_utils.py
    velocity: int      # 力度（0~127，按键按得多重；后面会换算成弓的压力）


@dataclass(frozen=True)
class FingeringCandidate:
    """② 某个音的"一种指法方案"。

    同一个音在小提琴上往往有不止一种拉法（可以在不同弦、不同把位上拉），
    所以一个 pitch 会对应多个 FingeringCandidate，再按 priority 挑一个最合适的。
    """

    pitch: int        # 这个方案对应的 MIDI 音高
    note_name: str    # 可读音名，如 "A4"（方便人看，不参与控制）
    string: str       # 用哪根弦："G" / "D" / "A" / "E"（从低到高）
    position: int     # 第几把位（左手在琴颈上的上下位置，1=第一把位…）
    finger: int       # 用哪根手指按弦：0=空弦(不按) 1=食指 2=中指 3=无名指 4=小指
    priority: int     # 优先级（数字越小越优先选；详见 mapping.py）


@dataclass(frozen=True)
class ConvertedNote:
    """③ 选定指法后的最终音符（包含机械臂需要的全部信息）。"""

    start: float              # 开始时间（秒）
    end: float                # 结束时间（秒）
    duration: float           # 持续时长（秒）
    pitch: int                # MIDI 音高
    note_name: str            # 可读音名
    string: str               # 用哪根弦
    position: int             # 第几把位
    finger: int               # 用哪根手指
    velocity: int             # 原始力度（来自 MIDI）
    is_string_change: bool    # 相对上一个音是否需要"换弦"（机械臂要提前准备）
    is_position_change: bool  # 相对上一个音是否需要"换把位"（左手要滑动）
    is_legato: bool            # 是否可连奏（同一弓段继续，不必换弓向）
    bow_direction: str | None = None  # 最终决策出的弓向："down" / "up"（调试和 JSON 输出使用）

    def to_dict(self) -> dict[str, Any]:
        """把自己转成字典，方便最终写成 JSON 文件。"""
        data = {
            "start": self.start,
            "end": self.end,
            "duration": self.duration,
            "pitch": self.pitch,
            "note_name": self.note_name,
            "string": self.string,
            "position": self.position,
            "finger": self.finger,
            "velocity": self.velocity,
            "is_string_change": bool(self.is_string_change),
            "is_position_change": bool(self.is_position_change),
            "is_legato": bool(self.is_legato),
        }
        if self.bow_direction is not None:
            data["bow_direction"] = self.bow_direction
        return data


@dataclass(frozen=True)
class ConversionMeta:
    """④a 曲子的"元信息"（概况，不是逐个音符）。"""

    title: str        # 曲名
    tempo: float      # 速度（BPM，每分钟多少拍）
    source_midi: str  # 源 MIDI 文件路径
    note_count: int   # 一共多少个音符

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversionResult:
    """④b 一次转换的最终成果 = 元信息 + 全部音符。

    这个对象会同时喂给两条出路：
      - 写成 .json  → 给人/调试看
      - 编码成 .bin → 给单片机(Arduino)执行
    """

    meta: ConversionMeta          # 曲子概况
    notes: list[ConvertedNote]    # 逐个音符的完整列表

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "notes": [note.to_dict() for note in self.notes],
        }


def build_converted_note(
    note: MidiNote,
    fingering: FingeringCandidate,
    previous: ConvertedNote | None = None,
) -> ConvertedNote:
    """把「原始音符 + 选定指法」组装成带指法的最终音符。

    这是离线和实时两条链路共用的组装工序：给定上一个已确定音符（用于判断是否换弦/换把），
    把指法（弦/把位/手指）与原始音符的时间/力度信息合成为一个 ConvertedNote。
    is_legato 此处固定为 False，弓法决策（legato / bow_direction）由下游 BowDecisionEngine 统一填写。
    """
    is_string_change = previous is not None and previous.string != fingering.string
    is_position_change = previous is not None and previous.position != fingering.position
    return ConvertedNote(
        start=note.start,
        end=note.end,
        duration=note.duration,
        pitch=note.pitch,
        note_name=fingering.note_name,
        string=fingering.string,
        position=fingering.position,
        finger=fingering.finger,
        velocity=note.velocity,
        is_string_change=is_string_change,
        is_position_change=is_position_change,
        is_legato=False,
    )
