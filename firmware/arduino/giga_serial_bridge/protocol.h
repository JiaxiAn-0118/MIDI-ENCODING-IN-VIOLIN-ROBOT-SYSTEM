#ifndef VIOLIN_PROTOCOL_H
#define VIOLIN_PROTOCOL_H

#include <Arduino.h>

/*
 * ============================================================================
 *  12 字节二进制协议层 (Protocol Layer)
 * ============================================================================
 *  定义小提琴机器人标准 12 字节通讯协议的数据结构与解码逻辑。
 *  与上位机 Python (binary_encoder.py / protocol.py) 严格一一对应。
 * ============================================================================
 */

constexpr uint8_t PROTOCOL_HEADER = 0xA5;
constexpr size_t PACKET_SIZE = 12;

constexpr uint8_t BOW_DIR_PULL = 0; // 0 = 拉弓 (Down-bow)
constexpr uint8_t BOW_DIR_PUSH = 1; // 1 = 推弓 (Up-bow)

constexpr uint8_t FLAG_VIBRATO = 0x01; // 揉弦
constexpr uint8_t FLAG_STACCATO = 0x02; // 断奏
constexpr uint8_t FLAG_LEGATO = 0x04;  // 连奏
constexpr uint8_t FLAG_ACCENT = 0x08;  // 重音

struct ViolinEvent {
  uint16_t tick;        // 触发时刻 (1 tick = 10ms, 低字节在前)
  uint8_t pitch;        // MIDI 音高 (0~127, 如 69 = A4)
  uint16_t duration;    // 持续时长 (单位: tick)
  uint8_t stringId;     // 弦编号: 0=G, 1=D, 2=A, 3=E
  uint8_t finger;       // 手指: 0=空弦, 1=食指, 2=中指, 3=无名指, 4=小指
  uint8_t position;     // 把位: 1=第1把位, 2=第2把位...
  uint8_t bowDirection; // 弓方向: 0=拉弓, 1=推弓
  uint8_t bowSpeed;     // 弓速: 0~127
  uint8_t bowForce;     // 弓压: 0~255
  uint8_t flags;        // 演奏法标记位

  bool isLegato() const {
    return (flags & FLAG_LEGATO) != 0;
  }
};

class ProtocolDecoder {
public:
  // 解码 12 字节数据包，成功返回 true 并赋值 event，校验失败返回 false
  static bool decode(const uint8_t *packet, ViolinEvent &event) {
    if (packet[0] != PROTOCOL_HEADER) {
      return false;
    }

    uint8_t checksum = 0;
    for (size_t i = 0; i < 11; ++i) {
      checksum += packet[i];
    }
    if (checksum != packet[11]) {
      return false;
    }

    event.tick = packet[1] | (static_cast<uint16_t>(packet[2]) << 8);
    event.pitch = packet[3];
    event.duration = packet[4] | (static_cast<uint16_t>(packet[5]) << 8);
    event.stringId = (packet[6] >> 6) & 0x03;
    event.finger = (packet[6] >> 3) & 0x07;
    event.position = packet[6] & 0x07;
    event.bowDirection = (packet[7] >> 7) & 0x01;
    event.bowSpeed = packet[7] & 0x7F;
    event.bowForce = packet[8];
    event.flags = packet[9];

    return true;
  }
};

#endif // VIOLIN_PROTOCOL_H
