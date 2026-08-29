# violin_midi_json

一个面向“小提琴机器人”前期软件开发的 Python 项目，用于完成：

```text
MIDI → 音乐语义解析 → 小提琴左手映射 → JSON / Binary
```

当前阶段只关注“音乐到结构化动作描述 / MCU 事件流”的转换，不涉及机械控制、电机、轨迹规划和弓法物理建模。JSON 用于电脑端调试；单片机运行建议直接读取二进制 `.bin` 文件。

## 项目结构

```text
violin_midi_json/
├── requirements.txt
├── README.md
├── mapping_algorithm.md
├── examples/
│   └── example_output.json
├── tests/
└── src/
    └── violin_midi_json/
        ├── __init__.py
        ├── binary_encoder.py
        ├── bow_decision.py
        ├── cli.py
        ├── constants.py
        ├── converter.py
        ├── fingering_planner.py
        ├── mapping.py
        ├── midi_parser.py
        ├── models.py
        ├── note_utils.py
        ├── scheduler.py
        └── streaming.py
```

## 功能

- 读取单旋律 MIDI 文件
- 提取音符开始时间、结束时间、持续时间、力度、音高
- 根据小提琴左手音高对照表映射：
  - string
  - position
  - finger
- 检测：
  - 是否换弦
  - 是否换把
- 输出结构化 JSON，便于人眼检查
- 输出 Binary Violin Event Protocol V1 `.bin`，便于 MCU 直接读取

## 安装

```bash
pip install -r requirements.txt
```

## 使用方式

输出 JSON 调试文件：

```bash
PYTHONPATH=src python -m violin_midi_json.cli input.mid output.json --format json --title "example"
```

输出 MCU 使用的二进制事件流：

```bash
PYTHONPATH=src python -m violin_midi_json.cli input.mid output.bin --format bin --title "example"
```

也可以省略 `--format`，程序会根据扩展名自动判断：`.bin` 输出二进制，其它扩展名输出 JSON。

```bash
PYTHONPATH=src python -m violin_midi_json.cli input.mid output.bin
```

## 输出 JSON 结构

```json
{
  "meta": {
    "title": "example",
    "tempo": 120.0,
    "source_midi": "examples/example.mid",
    "note_count": 3
  },
  "notes": [
    {
      "start": 0.0,
      "end": 0.5,
      "duration": 0.5,
      "pitch": 69,
      "note_name": "A4",
      "string": "A",
      "position": 1,
      "finger": 0,
      "velocity": 80,
      "is_string_change": false,
      "is_position_change": false
    }
  ]
}
```

## 输出 Binary 结构

二进制输出遵循 `Binary Violin Event Protocol V1`，每个音符固定 12 字节：

```text
Byte 0     Header = 0xA5
Byte 1-2   Tick，uint16，小端，默认 1 tick = 10 ms
Byte 3     MIDI Pitch
Byte 4-5   Duration，uint16，小端，默认 1 tick = 10 ms
Byte 6     String/Finger/Position bitfield
Byte 7     Bow Direction/Speed bitfield
Byte 8     Bow Force
Byte 9     Flags
Byte 10    Reserved
Byte 11    Checksum = sum(Byte 0..10) & 0xFF
```

当前二进制编码的弓法策略（由 `bow_decision.py` 决策，非固定规则）：

- 弓向、连奏、弓速由 `BowDecisionEngine` 批量决策（最多 2 个未来音符的有限前瞻）
- `bow_speed`：决策器逐音计算（1~10，长音慢、短音快、连奏偏慢）
- `bow_force`：直接承载该音符的 MIDI velocity
- `flags`：按音符设置（连奏 `0x04`、`reset_bow` `0x08` 等）

## 当前映射策略

当前阶段采用：

- 全局动态规划（DP）指法规划器 `fingering_planner.py`，全局搜索最低物理代价（换弦/换把）的指法路径
- 保留 `mapping.py` 的局部默认映射（优先低把位、低手指、自然空弦）作为降级回退

## 后续可扩展方向

- 接入机器人控制层事件编码（实时执行端）
- 基于听觉反馈的指法/弓法闭环优化
