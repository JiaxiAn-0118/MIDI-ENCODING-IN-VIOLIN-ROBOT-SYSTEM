HEADER = 0xA5
PACKET_SIZE = 12


def validate_packet(packet: bytes) -> None:
    if len(packet) != PACKET_SIZE:
        raise ValueError(f"Packet must be {PACKET_SIZE} bytes, got {len(packet)}")
    if packet[0] != HEADER:
        raise ValueError(f"Bad header: 0x{packet[0]:02X}")
    expected = sum(packet[:11]) & 0xFF
    if packet[11] != expected:
        raise ValueError(
            f"Bad checksum: got 0x{packet[11]:02X}, expected 0x{expected:02X}"
        )


def packet_tick(packet: bytes) -> int:
    validate_packet(packet)
    return packet[1] | (packet[2] << 8)


def packet_pitch(packet: bytes) -> int:
    validate_packet(packet)
    return packet[3]


def decode_packet(packet: bytes) -> dict[str, int]:
    validate_packet(packet)
    return {
        "tick": packet[1] | (packet[2] << 8),
        "pitch": packet[3],
        "duration": packet[4] | (packet[5] << 8),
        "string_id": (packet[6] >> 6) & 0x03,
        "finger": (packet[6] >> 3) & 0x07,
        "position": packet[6] & 0x07,
        "bow_direction": (packet[7] >> 7) & 0x01,
        "bow_speed": packet[7] & 0x7F,
        "bow_force": packet[8],
        "flags": packet[9],
    }


def split_score(data: bytes) -> list[bytes]:
    if len(data) % PACKET_SIZE != 0:
        raise ValueError(
            f"Score size {len(data)} is not divisible by packet size {PACKET_SIZE}"
        )

    packets = [
        data[offset : offset + PACKET_SIZE]
        for offset in range(0, len(data), PACKET_SIZE)
    ]
    for index, packet in enumerate(packets):
        try:
            validate_packet(packet)
        except ValueError as exc:
            raise ValueError(f"Invalid packet {index}: {exc}") from exc
    return packets
