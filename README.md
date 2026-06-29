# 登辉-小提琴项目目录说明

这是一个面向小提琴机器人前期开发的项目，当前重点是：

```text
MIDI / 曲谱数据 -> 小提琴演奏事件 -> 二进制曲谱 -> Arduino 解码
```

## 目录结构

```text
.
├── docs/                  项目文档、协议、映射表、计划
├── firmware/arduino/      Arduino 测试程序
├── scores/小星星/          小星星曲谱、MIDI、JSON、BIN 等数据文件
├── scores/twinkle/         小星星英文路径副本，推荐 Ubuntu/ROS2 使用
├── simulation/            MATLAB 机械/运弓仿真
├── ros2_ws/               ROS2 曲谱播放与 GIGA 串口桥
├── violin_midi_json/      MIDI 转 JSON / BIN 的 Python 工具
├── .venv/                 Python 虚拟环境
└── .idea/                 IDE 配置
```

## 常用命令

进入项目根目录：

```bash
cd /Users/mirong/Documents/登辉-小提琴
```

由 MIDI 生成 JSON 调试文件：

```bash
PYTHONPATH=violin_midi_json/src .venv/bin/python -m violin_midi_json.cli scores/小星星/小星星完整版.mid scores/小星星/小星星完整版_from_midi.json --format json --title "小星星完整版"
```

由 MIDI 生成单片机使用的二进制文件：

```bash
PYTHONPATH=violin_midi_json/src .venv/bin/python -m violin_midi_json.cli scores/小星星/小星星完整版.mid scores/小星星/小星星完整版.bin --format bin --title "小星星完整版"
```

检查二进制曲谱大小：

```bash
ls -l scores/小星星/小星星完整版.bin
```

《小星星完整版》当前有 35 个事件，每个事件 12 字节，所以 `.bin` 文件应为 420 字节。

Ubuntu / ROS2 中推荐使用英文路径副本：

```text
scores/twinkle/twinkle_full.bin
```

## Arduino 测试

Arduino 测试程序在：

```text
firmware/arduino/test1/test1.ino
```

打开 Arduino IDE 时，直接打开这个 `.ino` 文件。`littlestar.h` 必须和 `test1.ino` 保持在同一个文件夹内。

串口监视器波特率设为：

```text
115200
```

## ROS2 与 GIGA 通信

ROS2 串口通信实验说明：

```text
docs/ROS2_Arduino通信实验.md
```

GIGA R1 串口接收程序：

```text
firmware/arduino/giga_serial_bridge/giga_serial_bridge.ino
```
