/*
 * ============================================================================
 *  GIGA R1 串口桥固件（烧进 Arduino GIGA R1 开发板的程序）
 * ============================================================================
 *  【一句话】从串口接收电脑发来的 12 字节"演奏指令"，解码后回一句确认。
 *
 *  【在系统里的位置】
 *      电脑(ROS2 arduino_bridge) ──USB串口──> 本程序(Arduino)
 *                                                    │ 解码出 拍点/音高/弦/指法/弓法
 *                                                    ▼
 *                                          (将来在这里驱动电机拉弓、按弦)
 *
 *  【Arduino 程序的基本结构（只有两个函数）】
 *      setup() —— 上电后只跑一次，做初始化（这里：打开串口）。
 *      loop()  —— 跑完 setup() 后被无限反复调用（这里：不停收数据、解码）。
 *
 *  【12 字节数据包格式】（和电脑端 binary_encoder.py / protocol.py 完全一致）
 *      字节0   = 包头 0xA5      字节1-2 = 拍点 tick(低字节在前)
 *      字节3   = 音高           字节4-5 = 时长 duration(低字节在前)
 *      字节6   = 弦/手指/把位    字节7   = 弓方向/弓速
 *      字节8   = 弓压           字节9   = 演奏法标记
 *      字节10  = 预留           字节11  = 校验和
 *
 *  串口监视器波特率请设为 115200。
 * ============================================================================
 */

#include <Arduino.h>

const uint8_t HEADER = 0xA5;     // 包头：每个数据包都以它开头（uint8_t = 8位无符号整数，范围 0~255）
const size_t PACKET_SIZE = 12;   // 每个数据包固定 12 字节

const uint8_t BOW_UP = 0;        // 弓方向：拉弓
const uint8_t BOW_DOWN = 1;      // 弓方向：推弓
const uint8_t LEGATO_FLAG = 0x04; // Flags 中的 legato 标志

// 结构体(struct)：把"一个演奏事件"的各个字段打包在一起，方便在程序里整体传递。
struct ViolinEvent {
  uint16_t tick;        // 拍点（触发时刻）。uint16_t = 16位无符号整数（0~65535）
  uint8_t pitch;        // 音高（MIDI 编号 0~127）
  uint16_t duration;    // 时长（单位 tick）
  uint8_t stringId;     // 弦编号：0=G 1=D 2=A 3=E
  uint8_t finger;       // 手指：0=空弦 1=食指 2=中指 3=无名 4=小指
  uint8_t position;     // 把位
  uint8_t bowDirection; // 弓方向：0=拉弓 1=推弓
  uint8_t bowSpeed;     // 弓速（0~127）
  uint8_t bowForce;     // 弓压（0~255）
  uint8_t flags;        // 演奏法标记
};

// 解码一个 12 字节数据包；成功返回 true 并把结果写进 event，失败返回 false。
// （位运算和电脑端 protocol.py 的 decode_packet 完全是同一套算法）
bool decodePacket(const uint8_t *packet, ViolinEvent &event) {
  // 第1步：检查包头。
  if (packet[0] != HEADER) {
    return false;
  }

  // 第2步：校验和——前 11 字节相加取低 8 位，应等于第 12 字节(packet[11])。
  uint8_t checksum = 0;
  for (size_t i = 0; i < 11; ++i) {
    checksum += packet[i];
  }
  if (checksum != packet[11]) {
    return false;
  }

  // 第3步：把字节拆成字段。
  event.tick = packet[1] | (packet[2] << 8);          // 小端还原 16 位：低字节 + 高字节左移8位
  event.pitch = packet[3];
  event.duration = packet[4] | (packet[5] << 8);      // 同上，小端还原
  event.stringId = (packet[6] >> 6) & 0x03;           // 字节6最高2位 = 弦（>>6 右移6位，&0x03 取2位）
  event.finger = (packet[6] >> 3) & 0x07;             // 字节6中间3位 = 手指
  event.position = packet[6] & 0x07;                  // 字节6最低3位 = 把位
  event.bowDirection = (packet[7] >> 7) & 0x01;       // 字节7最高1位 = 弓方向
  event.bowSpeed = packet[7] & 0x7F;                  // 字节7低7位 = 弓速
  event.bowForce = packet[8];
  event.flags = packet[9];
  return true;
}

// 回一句 ACK（确认收到），并把关键字段打印出来，方便在串口监视器里观察。
void sendAck(const ViolinEvent &event) {
  bool legato = (event.flags & LEGATO_FLAG) != 0;
  Serial.print("ACK tick=");
  Serial.print(event.tick);
  Serial.print(" pitch=");
  Serial.print(event.pitch);
  Serial.print(" string=");
  Serial.print(event.stringId);
  Serial.print(" finger=");
  Serial.print(event.finger);
  Serial.print(" position=");
  Serial.print(event.position);
  Serial.print(" bow_dir=");
  Serial.print(event.bowDirection);
  Serial.print(" bow_speed=");
  Serial.print(event.bowSpeed);
  Serial.print(" bow_force=");
  Serial.print(event.bowForce);
  Serial.print(" legato=");
  Serial.print(legato ? "1" : "0");
  Serial.print(" flags=0x");
  if (event.flags < 16) {
    Serial.print('0');
  }
  Serial.println(event.flags, HEX);
}

void setBowDirection(uint8_t direction) {
  // 这里是弓方向控制入口，实际方案可替换为电机或伺服控制。
  Serial.print("SET_BOW_DIR ");
  Serial.println(direction);
}

void setBowSpeed(uint8_t speed) {
  // 这里是弓速控制入口，实际方案可替换为电机速度输出。
  Serial.print("SET_BOW_SPEED ");
  Serial.println(speed);
}

void setBowForce(uint8_t force) {
  // 这里是弓压控制入口，实际方案可替换为压力控制输出。
  Serial.print("SET_BOW_FORCE ");
  Serial.println(force);
}

void playEvent(const ViolinEvent &event, bool previous_legato) {
  bool legato = (event.flags & LEGATO_FLAG) != 0;
  if (legato && previous_legato) {
    // 连奏：保持当前弓段方向，更新弓速与弓压即可。
    Serial.println("PLAY_EVENT legato continuation");
    setBowSpeed(event.bowSpeed);
    setBowForce(event.bowForce);
  } else {
    // 非连奏或连奏断开时：重置弓段方向与弓参数。
    Serial.println("PLAY_EVENT new bow stroke");
    setBowDirection(event.bowDirection);
    setBowSpeed(event.bowSpeed);
    setBowForce(event.bowForce);
  }

  // 这里可以增加实际按弦、移动把位、等待 tick 等动作。
}

// —— 上电后只跑一次 ——
void setup() {
  Serial.begin(115200);     // 打开串口，波特率 115200（必须和电脑端一致）
  while (!Serial) {
  }                         // 等串口就绪（GIGA 的 USB 串口需要这一步）
  Serial.println("READY giga_serial_bridge");  // 喊一句"我准备好了"
}

// —— 无限循环 ——
void loop() {
  static uint8_t packet[PACKET_SIZE];  // static：只初始化一次，跨多次 loop() 保留内容
  static size_t index = 0;             // 当前已收到本包的第几个字节

  // 只要串口里还有数据，就逐字节读取。
  while (Serial.available() > 0) {
    uint8_t value = Serial.read();

    // 关键：找包头对齐。如果还在等第一个字节(index==0)却读到的不是 0xA5，
    // 就丢弃它继续等，直到对上包头为止（避免数据错位）。
    if (index == 0 && value != HEADER) {
      continue;
    }

    packet[index++] = value;            // 把这一字节存进缓冲区
    if (index < PACKET_SIZE) {
      continue;                         // 还没凑够 12 字节，继续收
    }

    // 凑够 12 字节，尝试解码。
    ViolinEvent event;
    if (decodePacket(packet, event)) {
      sendAck(event);
      static bool previous_legato = false;
      playEvent(event, previous_legato);
      previous_legato = (event.flags & LEGATO_FLAG) != 0;
    } else {
      Serial.println("NACK invalid_packet");   // 校验失败：回 NACK（有问题）
    }
    index = 0;                          // 复位，准备收下一个包
  }
}
