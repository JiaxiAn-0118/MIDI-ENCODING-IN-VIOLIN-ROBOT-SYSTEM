# Binary Violin Event Protocol V1

## 1. 协议背景

该协议用于 **MIDI 驱动的小提琴机器人系统**  
系统链路如下：

```text
MIDI / 简谱
→ Music Parser
→ Violin Event Generator
→ Binary Encoding
→ Arduino
```

设计目标：

- 每个 event 对应一个音符演奏动作
- 使用固定长度 packet
- 尽量节省字节数
- 适合 Arduino 实时解析
- 支持未来扩展（vibrato、glissando、legato）

---

## 2. Packet Structure

V1 采用 **12 字节固定长度 packet**。

优点：

- 长度固定，MCU 易解析
- 适合串口流同步
- 字节数较小
- 便于后续扩展

### 2.1 字节布局

| Byte |            字段 | 字节数 | 类型       | 说明                  |
|------|--------------:|----:|----------|---------------------|
| 0    |        Header |   1 | uint8    | 固定包头，建议 `0xA5`      |
| 1-2  |          Tick |   2 | uint16   | 事件触发时间戳             |
| 3    |    MIDI Pitch |   1 | uint8    | MIDI 音高 0~127       |
| 4-5  |      Duration |   2 | uint16   | 持续时间，单位 tick        |
| 6    | String/Finger |   1 | bitfield | 弦选择 + 手指编号 + 把位     |
| 7    |           Bow |   1 | bitfield | 弓方向 + 弓速            |
| 8    |         Force |   1 | uint8    | 弓压力度                |
| 9    |         Flags |   1 | bitfield | articulation / 扩展标志 |
| 10   |      Reserved |   1 | uint8    | 预留扩展                |
| 11   |      Checksum |   1 | uint8    | 校验和                 |

总长度：

```text
12 bytes / event
```

---

### 2.2 字段范围

#### Header

固定值：

```text
0xA5
```

#### Tick

- 类型：`uint16`
- 范围：`0 ~ 65535`
- 建议单位：`1 tick = 10 ms`

最大时间范围：

```text
65535 * 10 ms ≈ 655.35 s
```

#### MIDI Pitch

- 类型：`uint8`
- 范围：`0 ~ 127`

示例：

- G3 = 55
- D4 = 62
- A5 = 69
- E5 = 76
- F#5 = 78
- A6 = 81

#### Duration

- 类型：`uint16`
- 范围：`0 ~ 65535 ticks`
- 建议单位：`1 tick = 10 ms`

例如：

- `0.5 s = 50 ticks`
- `1.0 s = 100 ticks`

---

## 3. 字段编码定义

### 3.1 String/Finger 字节布局

Byte 6 采用位编码：

| bit | 含义       |
|-----|----------|
| 7-6 | string   |
| 5-3 | finger   |
| 2-0 | position |

编码方式：

```text
bits 7-6: string   (2 bits)
bits 5-3: finger   (3 bits)
bits 2-0: position (3 bits)
```

### 3.2 string 定义

```text
0 = G
1 = D
2 = A
3 = E
```

### 3.3 finger 定义

```text
0 = open string
1 = index
2 = middle
3 = ring
4 = little
5~7 = reserved
```

### 3.4 position 定义

```text
0 = open / undefined
1 = 1st position
2 = 2nd position
3 = 3rd position
4 = 4th position
5 = 5th position
6 = reserved
7 = reserved
```

---

### 3.5 Bow 字节布局

Byte 7 采用位编码：

| bit | 含义 |
|---|---|
| 7 | bow_direction |
| 6-0 | bow_speed |

编码方式：

```text
bit 7   : bow_direction
bits 6-0: bow_speed
```

### 3.6 bow_direction 定义

```text
0 = up bow
1 = down bow
```

### 3.7 bow_speed 定义

- 范围：`0 ~ 127`

建议工程约定：

```text
0 = stop
1~10 = 常用演奏速度等级
11~127 = 预留扩展
```

### 3.8 bow_force 定义

- 范围：`0 ~ 255`

建议工程约定：

```text
0 = no pressure
1~10 = 常用力度等级
11~255 = 扩展
```

---

## 4. Flags 位设计

Byte 9 = Flags

| bit | 名称        | 含义            |
|-----|-----------|---------------|
| 0   | vibrato   | 1 = 启用揉弦      |
| 1   | glissando | 1 = 启用滑音      |
| 2   | legato    | 1 = 连奏        |
| 3   | staccato  | 1 = 断奏        |
| 4   | accent    | 1 = 重音        |
| 5   | tremolo   | 1 = 震弓 / 快速重复 |
| 6   | reserved  | 保留            |
| 7   | reserved  | 保留            |

### 4.1 Flags 示例

普通音：

```text
00000000 = 0x00
```

vibrato：

```text
00000001 = 0x01
```

glissando：

```text
00000010 = 0x02
```

legato：

```text
00000100 = 0x04
```

staccato：

```text
00001000 = 0x08
```

vibrato + legato：

```text
00000101 = 0x05
```

---

## 5. Checksum 设计

V1 推荐使用 **8-bit sum checksum**：

```text
checksum = (Byte0 + Byte1 + ... + Byte10) & 0xFF
```

优点：

- Arduino 上实现简单
- 计算开销低
- 比 XOR 更稳妥

---

## 6. Arduino / MCU 解析结构

### 6.1 原始 Packet 结构

```cpp
typedef struct __attribute__((packed)) {
    uint8_t  header;
    uint16_t tick;
    uint8_t  midi_pitch;
    uint16_t duration;
    uint8_t  string_finger;
    uint8_t  bow;
    uint8_t  bow_force;
    uint8_t  flags;
    uint8_t  reserved;
    uint8_t  checksum;
} ViolinEventPacket;
```

### 6.2 解码后的事件结构

```cpp
typedef struct {
    uint16_t tick;
    uint8_t midi_pitch;
    uint16_t duration;

    uint8_t string_id;
    uint8_t finger;
    uint8_t position;

    uint8_t bow_direction;
    uint8_t bow_speed;
    uint8_t bow_force;

    uint8_t vibrato;
    uint8_t glissando;
    uint8_t legato;
    uint8_t staccato;
    uint8_t accent;
    uint8_t tremolo;
} ViolinEvent;
```

### 6.3 解码函数示例

```cpp
bool decodeViolinEvent(const ViolinEventPacket* pkt, ViolinEvent* evt) {
    if (pkt->header != 0xA5) {
        return false;
    }

    uint8_t sum = 0;
    const uint8_t* raw = (const uint8_t*)pkt;
    for (int i = 0; i < 11; i++) {
        sum += raw[i];
    }
    if (sum != pkt->checksum) {
        return false;
    }

    evt->tick = pkt->tick;
    evt->midi_pitch = pkt->midi_pitch;
    evt->duration = pkt->duration;

    evt->string_id = (pkt->string_finger >> 6) & 0x03;
    evt->finger    = (pkt->string_finger >> 3) & 0x07;
    evt->position  = pkt->string_finger & 0x07;

    evt->bow_direction = (pkt->bow >> 7) & 0x01;
    evt->bow_speed     = pkt->bow & 0x7F;

    evt->bow_force = pkt->bow_force;

    evt->vibrato   = (pkt->flags >> 0) & 0x01;
    evt->glissando = (pkt->flags >> 1) & 0x01;
    evt->legato    = (pkt->flags >> 2) & 0x01;
    evt->staccato  = (pkt->flags >> 3) & 0x01;
    evt->accent    = (pkt->flags >> 4) & 0x01;
    evt->tremolo   = (pkt->flags >> 5) & 0x01;

    return true;
}
```

---

## 7. 通信协议建议

### 7.1 Packet Delimiter

建议：

- Header = `0xA5`
- 固定长度 = `12 bytes`
- 不额外设置尾字节

原因：

- 固定长度 + header 已足够同步
- 节省带宽
- MCU 解析更简单

### 7.2 Synchronization

串口接收状态机建议：

1. 持续读取字节流
2. 找到 `0xA5`
3. 再读取后续 11 字节
4. 校验 checksum
5. 成功则入队
6. 失败则丢弃并继续寻找下一个 `0xA5`

伪代码：

```cpp
if (byte == 0xA5) {
    buffer[0] = byte;
    read next 11 bytes;
    if checksum ok:
        parse packet;
    else:
        resync;
}
```

### 7.3 丢包处理

V1 建议采用轻量方案：

- 校验失败：直接丢弃当前包
- 继续寻找下一个 header
- 上位机周期性发送后续事件

后续 V2 可扩展：

- ACK
- NACK
- STOP
- PAUSE
- RESYNC

### 7.4 实时调度建议

推荐方式：

- 上位机提前发送未来 1~2 秒的事件队列
- MCU 本地按 tick 调度执行
- 不建议每个音符到点才发送

原因：

- 串口有抖动
- PC 调度不稳定
- MCU 本地定时更准确

缓冲建议：

- Arduino: `16~32 events`
- STM32: `64~128 events`

---

## 8. 示例 Packet

示例事件：

```text
time = 0.0 s
tick = 0
pitch = 81 (A5)
duration = 50 ticks
string = E = 3
finger = 0
position = 1
bow_direction = down = 1
bow_speed = 5
bow_force = 4
flags = 0
reserved = 0
```

### 8.1 编码结果

- Header = `0xA5`
- Tick = `0x00 0x00`
- MIDI Pitch = `0x51`
- Duration = `0x32 0x00`
- String/Finger = `0xD9`
- Bow = `0x85`
- Force = `0x04`
- Flags = `0x00`
- Reserved = `0x00`
- Checksum = `0x8A`

完整 packet：

```text
A5 00 00 51 32 00 D9 85 04 00 00 8A
```

---

## 9. 《小星星》前两小节示例

这里采用 A 大调一句：

```text
A5 A5 E5 E5 F#5 F#5 E5
```

假设：

- `1 tick = 10 ms`
- 普通音符时值 = `50 ticks`
- 最后一个音 = `100 ticks`
- bow 方向交替
- bow_speed = `5`
- bow_force = `4`
- flags = `0`

### 9.1 事件表

| 音符  | tick | pitch | string | finger | position | duration |  bow |
|-----|-----:|------:|-------:|-------:|---------:|---------:|-----:|
| A5  |    0 |    69 |   2(A) |      0 |        1 |       50 | down |
| A5  |   50 |    69 |   2(A) |      0 |        1 |       50 |   up |
| E5  |  100 |    76 |   3(E) |      0 |        1 |       50 | down |
| E5  |  150 |    76 |   3(E) |      0 |        1 |       50 |   up |
| F#5 |  200 |    78 |   3(E) |      1 |        1 |       50 | down |
| F#5 |  250 |    78 |   3(E) |      1 |        1 |       50 |   up |
| E5  |  300 |    76 |   3(E) |      0 |        1 |      100 | down |

### 9.2 二进制 Packet 示例

#### Event 1: A5

```text
A5 00 00 45 32 00 D9 85 04 00 00 8A
```

#### Event 2: A5

```text
A5 32 00 45 32 00 D9 05 04 00 00 3C
```

#### Event 3: E5

```text
A5 64 00 4C 32 00 C1 85 04 00 00 D1
```

#### Event 4: E5

```text
A5 96 00 4C 32 00 C1 05 04 00 00 83
```

#### Event 5: F#5

```text
A5 C8 00 4E 32 00 C9 85 04 00 00 07
```

#### Event 6: F#5

```text
A5 FA 00 4E 32 00 C9 05 04 00 00 B9
```

#### Event 7: E5

```text
A5 2C 01 4C 64 00 C1 85 04 00 00 CC
```

----
