"""violin_midi_json 工具包的"对外菜单"。

这个包负责把 MIDI 乐曲文件，转换成小提琴机器人能用的两种格式：
    .json → 给人看、调试用（每个音符的字段一目了然）
    .bin  → 给单片机(Arduino)执行的紧凑二进制曲谱

本文件（__init__.py）的作用是：当别的代码写
    import violin_midi_json
时，能直接拿到下面这些常用类，而不必关心它们具体放在哪个子模块里。
"""

# 把内部各模块里实现的核心类汇总到这里，对外只暴露这一份"菜单"。
from .binary_encoder import BinaryViolinEventEncoder   # 把音符编码成 12 字节二进制包
from .converter import MidiToJsonConverter             # 转换总指挥：串起 解析→映射→编码
from .models import ConvertedNote, ConversionMeta, ConversionResult, FingeringCandidate, MidiNote  # 各类数据容器

# __all__ 列出了"import *"时会导出的名字，相当于这份菜单的正式目录。
__all__ = [
    "BinaryViolinEventEncoder",
    "MidiToJsonConverter",
    "MidiNote",
    "FingeringCandidate",
    "ConvertedNote",
    "ConversionMeta",
    "ConversionResult",
]
