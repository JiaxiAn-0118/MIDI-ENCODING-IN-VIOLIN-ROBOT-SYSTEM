"""二进制协议的"解码 + 校验"工具（给 ROS2 节点用）。

这个文件是 violin_midi_json/binary_encoder.py 的"逆操作"：
    binary_encoder.py：音符 → 12 字节数据包（编码，在电脑上做）
    本文件 protocol.py：12 字节数据包 → 可读的字段（解码，ROS2 节点收到后用）

它不依赖任何 ROS2 组件，纯粹处理字节，所以也方便单独测试。

12 字节数据包布局（和编码端完全对应）：
    字节0   Header(0xA5)   包头
    字节1-2 Tick           触发时刻（低字节在前）
    字节3   Pitch          音高
    字节4-5 Duration       时长（低字节在前）
    字节6   弦/手指/把位    位编码：bit7-6=弦 bit5-3=手指 bit2-0=把位
    字节7   弓方向/弓速     位编码：bit7=方向 bit6-0=弓速
    字节8   弓压
    字节9   演奏法标记
    字节10  预留
    字节11  校验和
"""

HEADER = 0xA5            # 固定包头（和编码端一致）
PACKET_SIZE = 12         # 每个数据包固定 12 字节


def validate_packet(packet: bytes) -> None:
    """检查一个数据包是否合法（长度、包头、校验和三项）。

    只要有任何一项不对，就抛出 ValueError；
    调用方通常会捕获后丢弃这个包，避免把错误数据发给硬件。
    """
    # 1) 长度必须是 12 字节。
    if len(packet) != PACKET_SIZE:
        raise ValueError(f"Packet must be {PACKET_SIZE} bytes, got {len(packet)}")
    # 2) 第一个字节必须是包头 0xA5，否则说明数据"没对齐"。
    if packet[0] != HEADER:
        raise ValueError(f"Bad header: 0x{packet[0]:02X}")
    # 3) 校验和：前 11 字节相加取低 8 位，应等于第 12 字节(packet[11])。
    expected = sum(packet[:11]) & 0xFF
    if packet[11] != expected:
        raise ValueError(
            f"Bad checksum: got 0x{packet[11]:02X}, expected 0x{expected:02X}"
        )


def packet_tick(packet: bytes) -> int:
    """只取出"触发时刻"（tick）这一项，常用于按时序播放。"""
    validate_packet(packet)
    # 小端还原：低字节(packet[1]) + 高字节左移8位(packet[2]) = 16 位整数。
    return packet[1] | (packet[2] << 8)


def packet_pitch(packet: bytes) -> int:
    """只取出"音高"这一项。"""
    validate_packet(packet)
    return packet[3]


def decode_packet(packet: bytes) -> dict[str, int]:
    """把一个 12 字节数据包完整解码成字典（人就能读懂每个字段了）。

    这里大量使用"右移 >> + 掩码 &"把一个字节里挤在一起的几个信息拆开，
    正好是 binary_encoder.py 里"左移 << + 或 |"的反向操作。
    """
    validate_packet(packet)
    return {
        "tick": packet[1] | (packet[2] << 8),       # 触发时刻（16位，小端）
        "pitch": packet[3],                          # 音高
        "duration": packet[4] | (packet[5] << 8),   # 时长（16位，小端）
        # 字节6 拆三段：
        "string_id": (packet[6] >> 6) & 0x03,       #   弦：右移6位，取最高2位（0~3）
        "finger": (packet[6] >> 3) & 0x07,          #   手指：右移3位，取中间3位（0~7）
        "position": packet[6] & 0x07,               #   把位：取最低3位（0~7）
        # 字节7 拆两段：
        "bow_direction": (packet[7] >> 7) & 0x01,   #   弓方向：取最高1位（0拉/1推）
        "bow_speed": packet[7] & 0x7F,              #   弓速：取低7位（0~127）
        "bow_force": packet[8],                      # 弓压（整字节）
        "flags": packet[9],                          # 演奏法标记（整字节）
    }


def split_score(data: bytes) -> list[bytes]:
    """把一整首曲子的 .bin 内容，按 12 字节一切，拆成数据包列表。

    用在 score_player.py：它要先加载整首曲子，再按时序逐个发送。
    拆分的同时会逐个校验，任何一个包不合法都会立刻报错（避免带病播放）。
    """
    if len(data) % PACKET_SIZE != 0:
        # 正确的曲谱文件字节数一定是 12 的整数倍，否则说明文件损坏。
        raise ValueError(
            f"Score size {len(data)} is not divisible by packet size {PACKET_SIZE}"
        )

    # 每 12 字节切一段，组成列表。
    packets = [
        data[offset : offset + PACKET_SIZE]
        for offset in range(0, len(data), PACKET_SIZE)
    ]
    # 逐个校验合法性。
    for index, packet in enumerate(packets):
        try:
            validate_packet(packet)
        except ValueError as exc:
            raise ValueError(f"Invalid packet {index}: {exc}") from exc
    return packets
