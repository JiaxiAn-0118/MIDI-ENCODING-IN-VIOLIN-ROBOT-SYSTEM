/*
 * ============================================================================
 *  解码测试程序（不接电脑，验证"解码逻辑"对不对）
 * ============================================================================
 *  【一句话】把烧进板子的小星星曲谱(littlestar.h)逐个解码，打印到串口监视器。
 *
 *  【和 giga_serial_bridge.ino 的区别】
 *      giga_serial_bridge：从串口"接收"电脑发来的指令，实时解码（联机用）。
 *      本程序 test1：       解码"内置"的曲谱数组，一次性全部打印（脱机自测用）。
 *      两者共用同一套解码算法，本程序用来确认解码没错，再拿到联机版去用。
 *
 *  【用法】
 *      用 Arduino IDE 打开本 .ino（littlestar.h 必须和它在同一文件夹），
 *      上传到板子，打开串口监视器（波特率 115200），即可看到逐个音符的解码结果。
 * ============================================================================
 */

#include "littlestar.h"

const uint8_t HEADER = 0xA5;   // 包头
const int PACKET_SIZE = 12;    // 每个数据包固定 12 字节

// 演奏事件结构体（字段含义同 giga_serial_bridge.ino）。
struct ViolinEvent {
  uint16_t tick;
  uint8_t pitch;
  uint16_t duration;
  uint8_t string_id;
  uint8_t finger;
  uint8_t position;
  uint8_t bow_direction;
  uint8_t bow_speed;
  uint8_t bow_force;
  uint8_t flags;
};

// 解码一个 12 字节数据包；成功返回 true，失败返回 false。
bool decodePacket(const uint8_t *buf, ViolinEvent &evt) {
  if (buf[0] != HEADER) return false;       // 包头不对

  // 校验和：前 11 字节相加，低 8 位应等于第 12 字节。
  uint8_t sum = 0;
  for (int i = 0; i < 11; i++) {
    sum += buf[i];
  }
  if (sum != buf[11]) return false;

  // 拆字段（位运算含义见 giga_serial_bridge.ino）。
  evt.tick = buf[1] | (buf[2] << 8);
  evt.pitch = buf[3];
  evt.duration = buf[4] | (buf[5] << 8);

  evt.string_id = (buf[6] >> 6) & 0x03;
  evt.finger = (buf[6] >> 3) & 0x07;
  evt.position = buf[6] & 0x07;

  evt.bow_direction = (buf[7] >> 7) & 0x01;
  evt.bow_speed = buf[7] & 0x7F;
  evt.bow_force = buf[8];
  evt.flags = buf[9];

  return true;
}

// 把一个事件的全部字段打印成一行（前缀 "OK"）。
void printEvent(const ViolinEvent &evt) {
  Serial.print("OK tick=");
  Serial.print(evt.tick);
  Serial.print(" pitch=");
  Serial.print(evt.pitch);
  Serial.print(" duration=");
  Serial.print(evt.duration);
  Serial.print(" string=");
  Serial.print(evt.string_id);
  Serial.print(" finger=");
  Serial.print(evt.finger);
  Serial.print(" position=");
  Serial.print(evt.position);
  Serial.print(" bow_dir=");
  Serial.print(evt.bow_direction);
  Serial.print(" bow_speed=");
  Serial.print(evt.bow_speed);
  Serial.print(" bow_force=");
  Serial.println(evt.bow_force);
}

void setup() {
  Serial.begin(115200);       // 打开串口（波特率 115200）
  while (!Serial) {}

  Serial.println("Start decoding score...");

  // 每 12 字节切一个包，逐个解码打印。i 每次加 PACKET_SIZE(12)。
  for (unsigned int i = 0; i < twinkle_score_len; i += PACKET_SIZE) {
    ViolinEvent evt;

    if (decodePacket(&twinkle_score[i], evt)) {
      printEvent(evt);            // 解码成功：打印字段
    } else {
      Serial.print("BAD PACKET at byte ");  // 解码失败：报告出错位置
      Serial.println(i);
    }
  }

  Serial.println("Done.");
}

void loop() {
}   // 空的：本程序只在上电时跑一次解码，不需要循环做任何事。
