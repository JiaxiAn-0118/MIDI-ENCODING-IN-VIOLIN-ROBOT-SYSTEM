# ROS2 与 Arduino GIGA R1 串口通信实验

## 实验目标

不等待机械完成，先验证下面这条链路：

```text
twinkle_full.bin
→ ROS2 score_player 节点
→ /violin/event_raw
→ arduino_bridge 节点
→ USB 串口
→ Arduino GIGA R1
→ 校验并解码事件
→ ACK 回传 ROS2
```

本实验继续使用现有的 12 字节二进制曲谱协议，不需要 Arduino 解析 JSON 或 CSV。

如果手上暂时没有 Arduino GIGA R1，也可以先运行“无硬件模拟链路”：

```text
twinkle_full.bin
→ ROS2 score_player 节点
→ /violin/event_raw
→ mock_arduino 节点
→ 校验并解码事件
→ /violin/arduino_status 发布模拟 ACK
```

## 文件位置

```text
ros2_ws/src/violin_ros_bridge/                    ROS2 Python 包
firmware/arduino/giga_serial_bridge/              GIGA 串口接收程序
scores/twinkle/twinkle_full.bin                    Ubuntu 推荐使用的英文路径测试曲谱
scores/小星星/小星星完整版.bin                      macOS 原始中文路径测试曲谱
```

## 无硬件测试

没有 GIGA 板时，先在 UTM Ubuntu 中测试 ROS2 包本身。

构建工作区后运行：

```bash
cd ~/violin_robot/ros2_ws
source /opt/ros/$ROS_DISTRO/setup.bash
source install/setup.bash

ros2 launch violin_ros_bridge mock_demo.launch.py \
  score_path:=$HOME/violin_robot/scores/twinkle/twinkle_full.bin
```

成功时应看到类似：

```text
Published event=0 tick=0 pitch=69
ACK count=1 tick=0 pitch=69 duration=50 string=2 finger=0 position=1 bow_dir=0 bow_speed=1 bow_force=90 legato=0 flags=0x00
Published event=1 tick=50 pitch=69
ACK count=2 tick=50 pitch=69 duration=50 string=2 finger=0 position=1 bow_dir=0 bow_speed=1 bow_force=90 legato=1 flags=0x04
```

《小星星完整版》应输出 35 条 ACK。这个测试不需要串口、不需要开发板，只验证 ROS2 曲谱播放和二进制协议解码是否正确。

## 当前运行环境

本项目使用：

```text
macOS：保存项目、使用 Arduino IDE 上传 GIGA 程序
UTM Ubuntu：运行 ROS2 节点
Arduino GIGA R1：通过 USB 串口接收二进制事件
```

先在 Ubuntu 中确认 ROS2 版本：

```bash
echo $ROS_DISTRO
ros2 --help
```

后面的命令把 `jazzy` 替换为实际输出的 ROS2 版本名称。

## UTM 注意事项

### USB 设备转交

ROS2 要直接访问 GIGA 串口时，GIGA 必须连接到 Ubuntu 虚拟机，而不是被 macOS 占用。

1. 在 UTM 虚拟机设置中启用 USB Sharing。
2. 启动 Ubuntu。
3. 将 GIGA 插入 Mac。
4. 点击 UTM 工具栏的 USB 图标，把 GIGA 连接给 Ubuntu。

UTM 官方说明：USB Sharing 只支持 QEMU 后端。如果当前虚拟机使用 Apple Virtualization 后端，建议新建 QEMU Ubuntu 虚拟机，或者后续改用网络通信桥接。

Arduino IDE 串口监视器和 ROS2 串口桥不能同时占用 GIGA 串口。

### 项目文件

推荐把项目复制到 Ubuntu 用户目录后再构建，避免共享文件夹权限影响 `colcon build`：

```bash
mkdir -p ~/violin_robot
cp -r /shared/violin_robot/ros2_ws ~/violin_robot/
cp -r /shared/violin_robot/scores ~/violin_robot/
```

UTM 共享目录的具体路径取决于虚拟机配置。常见挂载点包括 `/mnt/utm` 或 `/media/...`。

## 第一步：上传 GIGA 程序

1. 用 Arduino IDE 打开：

   ```text
   firmware/arduino/giga_serial_bridge/giga_serial_bridge.ino
   ```

2. 开发板选择 `Arduino GIGA R1`。
3. 选择对应 USB 串口。
4. 上传程序。
5. 暂时关闭 Arduino IDE 串口监视器，否则它会占用串口。

GIGA 收到合法事件后会回传：

```text
ACK tick=0 pitch=69 string=2 finger=0 pos=1 bow_dir=0 speed=1 force=90 legato=0
```

## 第二步：在 Ubuntu 中构建 ROS2 工作区

在复制后的工作区运行：

```bash
cd ~/violin_robot/ros2_ws
source /opt/ros/$ROS_DISTRO/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

如果系统没有安装 `pyserial`：

```bash
sudo apt install python3-serial
```

## 第三步：确认串口名

把 GIGA USB 设备转交给 UTM Ubuntu 后运行：

```bash
ls /dev/ttyACM*
lsusb
```

常见结果：

```text
/dev/ttyACM0
```

如果遇到串口权限问题：

```bash
sudo usermod -a -G dialout $USER
```

执行后需要注销并重新登录。

## 第四步：启动通信实验

在 Ubuntu 的 `ros2_ws` 目录中运行：

```bash
cd ~/violin_robot/ros2_ws
source /opt/ros/$ROS_DISTRO/setup.bash
source install/setup.bash

ros2 launch violin_ros_bridge serial_demo.launch.py \
  score_path:=$HOME/violin_robot/scores/twinkle/twinkle_full.bin \
  port:=/dev/ttyACM0
```

启动后：

- `score_player` 按曲谱中的 tick 发布时间。
- `arduino_bridge` 将每个 12 字节事件写入 USB 串口。
- GIGA 校验并解码事件，然后回传 ACK。

成功时终端会依次出现类似信息：

```text
Published event=0 tick=0 pitch=69
Arduino: ACK tick=0 pitch=69 string=2 finger=0 pos=1 bow_dir=0 speed=1 force=90 legato=0
Published event=1 tick=50 pitch=69
Arduino: ACK tick=50 pitch=69 string=2 finger=0 pos=1 bow_dir=0 speed=1 force=90 legato=1
```

《小星星完整版》应发送并确认 35 个事件。

如果 UTM Ubuntu 中找不到 `/dev/ttyACM0`，先不要调 ROS2 节点。此时问题位于 USB 透传层，应先确认：

```text
UTM 是否使用 QEMU 后端
USB Sharing 是否启用
GIGA 是否已从 UTM 工具栏连接给 Ubuntu
lsusb 是否能看到 Arduino
dmesg 是否显示 ttyACM 设备
```

## ROS2 节点和话题

节点：

```text
/violin_score_player
/violin_arduino_bridge
```

话题：

```text
/violin/event_raw       std_msgs/UInt8MultiArray，12 字节演奏事件
/violin/arduino_status  std_msgs/String，GIGA 回传状态
```

可以在另一个终端观察 GIGA 回传：

```bash
ros2 topic echo /violin/arduino_status
```

## 下一步扩展

通信跑通后，在 GIGA 程序中把：

```cpp
// Future integration point: playEvent(event);
```

替换为实际动作调用：

```cpp
playEvent(event);
```

后续可以增加：

- ACK 超时和重发
- STOP / PAUSE / RESUME 命令
- GIGA 状态和故障信息回传
- 左手、右手和传感器独立 ROS2 话题
- 将串口桥替换为 micro-ROS
