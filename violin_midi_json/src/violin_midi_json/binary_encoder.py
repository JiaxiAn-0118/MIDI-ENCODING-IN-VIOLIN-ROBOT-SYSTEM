"""二进制编码器（工具链的最后一道工序：把音符打包成 12 字节的二进制包）。

为什么要转成二进制？
    Arduino 这类单片机内存小、算力弱，解析 JSON（文本格式）既慢又占空间。
    所以我们把每个音符压缩成一个固定 12 字节的"数据包"，
    通过串口发给 Arduino，它拆开就能直接控制电机。
    这套格式叫「Binary Violin Event Protocol V1」，详见
    docs/Binary_Violin_Event_Protocol_V1.md。

一个包（packet）的 12 个字节布局：
    字节0   Header(0xA5)   固定包头，用来"对齐"——单片机看到它就知道新包开始了
    字节1-2 Tick           事件触发时刻（uint16，低字节在前；1 tick = 10 ms）
    字节3   Pitch          MIDI 音高（0~127）
    字节4-5 Duration       持续时长（uint16，单位 tick，低字节在前）
    字节6   String/Finger  一个字节里塞了 3 个信息：弦/手指/把位（见下方位运算）
    字节7   Bow            一个字节里塞了 2 个信息：弓方向/弓速
    字节8   Force          弓的压力力度
    字节9   Flags          演奏/控制标记（如连奏、reset_bow、断奏等）
    字节10  Reserved       预留（目前固定为 0，留给将来扩展）
    字节11  Checksum       校验和：前 11 个字节相加取低 8 位，用来检查传输有没有出错

关于"位运算"（机械组同学重点看这里）：
    一个字节有 8 个比特（bit）。为了省空间，我们常把几个小数字塞进同一个字节。
    涉及两个基本操作：
      << (左移)：把数字的二进制往高位挪，腾出低位给别人。如 1 << 6 = 64。
      |  (按位或)：把两部分的二进制"合并"到一起。
      &  (按位与，常跟 0xFF/0x07 等掩码)：只保留我们想要的几位。
    解码时（在 Arduino/protocol.py 里）则是反过来：右移 >> + 掩码 & 把各部分取出来。
"""

from pathlib import Path
from typing import Optional, Union

from .bow_decision import BowDecisionEngine, BowDecisionOptions
from .constants import BOW_DOWN, BOW_UP
from .models import ConversionResult, ConvertedNote


HEADER = 0xA5            # 固定包头：每个数据包都以它开头，方便接收方"找齐"
TICK_SECONDS = 0.01      # 时间精度：1 个 tick = 0.01 秒 = 10 毫秒
PACKET_SIZE = 12         # 每个数据包固定 12 字节

# 弦名 → 数字编号（从粗到细：G 弦最低，E 弦最高）。
STRING_IDS = {
    "G": 0,
    "D": 1,
    "A": 2,
    "E": 3,
}

# Flags 字节中的标志位。
LEGATO_FLAG = 0x04
RESET_BOW_FLAG = 0x08
# staccato 已迁移到 bit6（0x40），当前编码器尚未主动写入该位，预留给后续扩展。
STACCATO_FLAG = 0x40


class BinaryViolinEventEncoder:
    """把转换好的音符，编码成「Binary Violin Event Protocol V1」数据包。"""

    def __init__(
        self,
        tick_seconds: float = TICK_SECONDS,
        default_bow_speed: int = 5,
        default_bow_force: int = 4,
    ) -> None:
        # tick_seconds: 秒→tick 的换算精度（默认 0.01 秒/tick）。
        self.tick_seconds = tick_seconds
        # 以下两个是"默认运弓参数"，目前对所有音符统一使用（将来可按音符细调）：
        #   bow_speed 弓速等级（0~127，常用 1~10）
        #   bow_force  弓压等级（0~255，常用 1~10）
        self.default_bow_speed = default_bow_speed
        self.default_bow_force = default_bow_force

    def encode_result(self, result: ConversionResult) -> bytes:
        """把一整首曲子（含多个音符）编码成连续的二进制流。"""
        packets: list[bytes] = []
        bow_engine = BowDecisionEngine(BowDecisionOptions(tempo_bpm=result.meta.tempo))

        # 先对整首曲子运行弓向决策器，得到每个音符的决策，
        # 这样编码时可以做前向/后向看位（例如把 legato 标记放到前一个包上，
        # 告知接收端“当前包之后不要回到弓头”）。
        decisions = []
        for index, note in enumerate(result.notes):
            beat_position = self._compute_beat_position(note.start, result.meta.tempo)
            decision = bow_engine.decide(
                note=note,
                beat_position=beat_position,
                explicit_legato=note.is_legato,
                is_first_note=(index == 0),
            )
            decisions.append(decision)

        for index, note in enumerate(result.notes):
            decision = decisions[index]
            # 如果下一个音符被判为连奏且弓向相同，则在当前包上也设置 legato 标记，
            # 告知接收端不要在两个包之间回到弓头。
            next_is_legato = False
            if index + 1 < len(decisions):
                nxt = decisions[index + 1]
                if nxt.is_legato and nxt.bow_direction == decision.bow_direction:
                    next_is_legato = True

            is_legato_for_packet = decision.is_legato or next_is_legato

            packets.append(
                self.encode_note(
                    note=note,
                    bow_direction=decision.bow_direction,
                    is_legato=is_legato_for_packet,
                    needs_reset_bow=decision.needs_reset_bow,
                    bow_speed=decision.bow_speed,
                )
            )

        # 把每个音符的 12 字节首尾拼接，得到整首曲子的 .bin 内容。
        return b"".join(packets)

    def write_result(self, result: ConversionResult, output_path: Union[str, Path]) -> None:
        """编码后直接写入 .bin 文件（这个文件就是给 Arduino 用的曲谱）。"""
        Path(output_path).write_bytes(self.encode_result(result))

    def encode_note(
        self,
        note: ConvertedNote,
        bow_direction: int,
        is_legato: bool,
        needs_reset_bow: bool = False,
        bow_speed: int | None = None,
    ) -> bytes:
        """把单个音符编码成一个 12 字节数据包。

        参数:
            note:           选好指法的音符（ConvertedNote）。
            bow_direction: 当前音符应使用的弓向（0=下弓/拉弓，1=上弓/推弓）。
            is_legato:      这个音符是否判定为连奏。
            needs_reset_bow: 是否需要强制离弓重置。
        """
        # —— 先把"人能理解的值"换算成"协议需要的数字" ——
        tick = self._seconds_to_ticks(note.start, "start")           # 开始时间（秒→tick）
        duration = self._seconds_to_ticks(note.duration, "duration") # 持续时长（秒→tick）
        midi_pitch = self._uint8(note.pitch, "pitch")                # 音高（本身就是 0~127）

        # 字节6：把 弦(2bit) + 手指(3bit) + 把位(3bit) 三个信息塞进同一个字节。
        #   bits 7-6 = string   bits 5-3 = finger   bits 2-0 = position
        string_finger = (
            (self._string_id(note.string) << 6)         # 弦编号左移 6 位，放到最高 2 位
            | (self._uint3(note.finger, "finger") << 3) # 手指左移 3 位，放到中间 3 位
            | self._uint3(note.position, "position")    # 把位放在最低 3 位
        )
        # 字节7：最高 1 位放弓方向，低 7 位放弓速。优先使用传入的 per-note 值，否则退回到默认。
        use_speed = self.default_bow_speed if bow_speed is None else bow_speed
        bow = (bow_direction << 7) | self._uint7(use_speed, "bow_speed")
        # 字节8：弓压（整字节）。
        bow_force = self._uint8(self.default_bow_force, "bow_force")
        # 字节9/10：标记位和预留位。
        flags = 0
        if is_legato:
            flags |= LEGATO_FLAG
        if needs_reset_bow:
            flags |= RESET_BOW_FLAG
        reserved = 0

        # —— 按 12 字节布局拼装数据包正文（前 11 字节）——
        body = bytes(
            [
                HEADER,                # 字节0  包头
                tick & 0xFF,           # 字节1  Tick 低 8 位（& 0xFF = 只取最低 8 位）
                (tick >> 8) & 0xFF,    # 字节2  Tick 高 8 位（先右移 8 位再取低 8 位）
                midi_pitch,            # 字节3  音高
                duration & 0xFF,       # 字节4  Duration 低 8 位
                (duration >> 8) & 0xFF,# 字节5  Duration 高 8 位
                string_finger,         # 字节6  弦/手指/把位
                bow,                   # 字节7  弓方向/弓速
                bow_force,             # 字节8  弓压
                flags,                 # 字节9  演奏法标记
                reserved,              # 字节10 预留
            ]
        )
        # 字节11：校验和 = 前 11 字节逐字节相加，只保留最低 8 位。
        # 接收方用同样的算法重算一遍，对不上就说明传输出错，丢弃这个包。
        checksum = sum(body) & 0xFF
        return body + bytes([checksum])

    def _seconds_to_ticks(self, seconds: float, field_name: str) -> int:
        """把秒数换算成 tick 数（除以 0.01 并四舍五入），并检查是否超出 16 位范围。"""
        safe_seconds = max(0.0, seconds)
        value = round(safe_seconds / self.tick_seconds)
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"{field_name} {seconds} s is outside uint16 tick range")
        return value

    def _compute_beat_position(self, start_seconds: float, tempo_bpm: float) -> float:
        """把音符开始时间转成小节内拍位（quarter beats）。"""
        seconds_per_quarter = 60.0 / tempo_bpm
        return start_seconds / seconds_per_quarter

    def _string_id(self, string: str) -> int:
        """把弦名(G/D/A/E)转成协议编号(0~3)。"""
        try:
            return STRING_IDS[string]
        except KeyError as exc:
            raise ValueError(f"Unsupported violin string: {string}") from exc

    def _uint3(self, value: int, field_name: str) -> int:
        """检查数值在 3 位范围(0~7)内，否则报错。"""
        if not 0 <= value <= 0x07:
            raise ValueError(f"{field_name} {value} is outside 3-bit range")
        return value

    def _uint7(self, value: int, field_name: str) -> int:
        """检查数值在 7 位范围(0~127)内，否则报错。"""
        if not 0 <= value <= 0x7F:
            raise ValueError(f"{field_name} {value} is outside 7-bit range")
        return value

    def _uint8(self, value: int, field_name: str) -> int:
        """检查数值在 8 位范围(0~255)内，否则报错。"""
        if not 0 <= value <= 0xFF:
            raise ValueError(f"{field_name} {value} is outside uint8 range")
        return value
