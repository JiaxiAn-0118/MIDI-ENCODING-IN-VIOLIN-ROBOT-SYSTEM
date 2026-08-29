/*
 * ============================================================================
 *  GIGA R1 串口桥固件 (主程序入口)
 * ============================================================================
 *  分层架构：
 *    1. protocol.h          - 12 字节二进制协议解码
 *    2. drivers.h           - 硬件抽象层 (IBowDriver, IFingerDriver...) & Mock
 *    3. motion_controller.h - 动作调度与双手协同状态机
 * ============================================================================
 */

#include <Arduino.h>
#include "protocol.h"
#include "drivers.h"
#include "motion_controller.h"

// 实例化驱动层 (当前无实体硬件，使用 MockDrivers)
static MockBowDriver bowDriver;
static MockStringDriver stringDriver;
static MockFingerDriver fingerDriver;
static MockPressureDriver pressureDriver;

// 实例化动作控制器
static MotionController motionController(bowDriver, stringDriver, fingerDriver, pressureDriver);

// 发送确认 ACK
void sendAck(const ViolinEvent &event) {
  Serial.print("ACK tick=");
  Serial.print(event.tick);
  Serial.print(" pitch=");
  Serial.print(event.pitch);
  Serial.print(" string=");
  Serial.print(event.stringId);
  Serial.print(" finger=");
  Serial.print(event.finger);
  Serial.print(" pos=");
  Serial.print(event.position);
  Serial.print(" bow_dir=");
  Serial.print(event.bowDirection);
  Serial.print(" speed=");
  Serial.print(event.bowSpeed);
  Serial.print(" force=");
  Serial.print(event.bowForce);
  Serial.print(" legato=");
  Serial.println(event.isLegato() ? "1" : "0");
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    // 等待 USB 串口就绪 (GIGA R1 USB CDC)
  }

  Serial.println("=========================================");
  Serial.println("  VIOLIN ROBOT FIRMWARE (GIGA R1) READY  ");
  Serial.println("=========================================");

  // 初始化动作控制子系统
  motionController.init();
}

void loop() {
  static uint8_t rxBuffer[PACKET_SIZE];
  static size_t rxIndex = 0;

  // 非阻塞逐字节接收串口数据流
  while (Serial.available() > 0) {
    uint8_t byteIn = Serial.read();

    // 帧头同步：等待 0xA5
    if (rxIndex == 0 && byteIn != PROTOCOL_HEADER) {
      continue;
    }

    rxBuffer[rxIndex++] = byteIn;

    // 收集满 12 字节进行解码
    if (rxIndex >= PACKET_SIZE) {
      ViolinEvent event;
      if (ProtocolDecoder::decode(rxBuffer, event)) {
        sendAck(event);
        motionController.executeEvent(event);
      } else {
        Serial.println("NACK checksum_or_header_error");
      }
      rxIndex = 0; // 复位缓冲区索引
    }
  }
}
