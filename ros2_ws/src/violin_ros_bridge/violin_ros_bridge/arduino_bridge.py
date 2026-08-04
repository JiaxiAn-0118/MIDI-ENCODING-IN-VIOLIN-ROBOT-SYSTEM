"""ROS2 ↔ Arduino 串口桥（连接电脑软件和单片机硬件的关键节点）。

【一句话】把电脑上算好的演奏指令，经 USB 串口转发给 Arduino 开发板。

【在系统里的位置】
        score_player 节点                      Arduino 开发板
              │ (按时序发布事件)                     ▲ (收到后控制电机)
              ▼                                       │
    ┌─────────────────────┐    ┌─── USB 串口 ───┐    │
    │  本节点 arduino_bridge│ ──>──────────────────>──┘
    └─────────────────────┘    └──────────────────┘
              ▲
              │ (同时读 Arduino 回传的状态文本，发布出去给人看)


【给小白的 ROS2 速成（看懂下面代码只需记住 5 个词）】
    节点 Node      —— 一个独立运行的小程序（本文件就是一个节点）。
    话题 Topic     —— 节点之间传消息的"频道"，有名字（如 /violin/event_raw）。
    发布 Publisher —— 往某个话题里"发消息"。
    订阅 Subscription —— 盯着某个话题，一有新消息就自动调用你写的回调函数。
    定时器 Timer   —— 每隔固定时间自动调用一次你写的函数（这里用来轮询串口）。

依赖：需要安装 pyserial（pip install pyserial）才能操作串口。
"""

import serial

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

from .protocol import validate_packet


class ArduinoSerialBridge(Node):
    """串口桥节点：订阅演奏事件→校验→串口发给 Arduino；并读 Arduino 回传状态。"""

    def __init__(self) -> None:
        # 给这个节点起个名字叫 "violin_arduino_bridge"（其它节点/工具靠这个名字找它）。
        super().__init__("violin_arduino_bridge")

        # 声明两个"参数"：串口设备名 和 波特率（通信速度）。
        # 参数的好处是：启动时可以从外部覆盖，不必改代码。
        self.declare_parameter("port", "/dev/ttyACM0")  # 默认串口设备名（Mac/Linux 多为这个）
        self.declare_parameter("baud", 115200)          # 默认波特率（必须和 Arduino 端一致！）

        port = str(self.get_parameter("port").value)
        baud = int(self.get_parameter("baud").value)
        # 打开串口。timeout=0 表示"读的时候不阻塞"（没数据就立刻返回），适合轮询。
        self.serial = serial.Serial(port=port, baudrate=baud, timeout=0)
        # 接收缓冲区：串口数据可能一次只来半个，先攒在这里，攒够一行再处理。
        self.rx_buffer = bytearray()

        # 订阅 /violin/event_raw 话题：score_player 发来的演奏事件（一串字节）。
        # 一有消息，就自动调用下面的 send_event。最后的 10 是"历史消息保留队列长度"。
        self.subscription = self.create_subscription(
            UInt8MultiArray,
            "/violin/event_raw",
            self.send_event,
            10,
        )
        # 发布 /violin/arduino_status 话题：把 Arduino 回传的文本（如 ACK）转发出去。
        self.status_publisher = self.create_publisher(String, "/violin/arduino_status", 10)
        # 每 0.01 秒(10ms)检查一次串口有没有 Arduino 回传的数据。
        self.timer = self.create_timer(0.01, self.read_status)
        self.get_logger().info(f"Opened Arduino serial port {port} at {baud} baud")

    def send_event(self, message: UInt8MultiArray) -> None:
        """收到一个演奏事件后：先校验合法性，通过才真正发给 Arduino。"""
        packet = bytes(message.data)
        try:
            validate_packet(packet)
        except ValueError as exc:
            # 数据包不合法（长度/包头/校验和不对），拒绝发送，记一条错误日志。
            self.get_logger().error(f"Not sending invalid packet: {exc}")
            return

        # 校验通过，写入串口发给 Arduino；flush 确保立刻发出去而不是留在缓冲区。
        self.serial.write(packet)
        self.serial.flush()

    def read_status(self) -> None:
        """定时器回调：把 Arduino 回传的字节攒成一行行文本，再发布出去。

        Arduino 回传的是文本（如 "ACK tick=0 pitch=69 ..."），以换行符 \\n 分隔。
        """
        # 先看串口里攒了多少字节没读。
        waiting = self.serial.in_waiting
        if waiting:
            # 全读出来，追加到接收缓冲区。
            self.rx_buffer.extend(self.serial.read(waiting))

        # 只要有完整的"一行"（包含换行符），就处理一行；可能一次处理多行。
        while b"\n" in self.rx_buffer:
            # 以第一个换行符为界，切成"这一行"和"剩下的"。
            line, _, remainder = self.rx_buffer.partition(b"\n")
            self.rx_buffer = bytearray(remainder)
            # 把字节翻译成文字（utf-8），去掉首尾空白。
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue  # 空行跳过

            # 把这一行文本作为一条状态消息发布出去，并打印到日志。
            message = String()
            message.data = text
            self.status_publisher.publish(message)
            self.get_logger().info(f"Arduino: {text}")

    def destroy_node(self) -> bool:
        """节点退出前，记得把串口关掉，释放资源。"""
        if self.serial.is_open:
            self.serial.close()
        return super().destroy_node()


def main(args=None) -> None:
    """节点的启动入口（setup.py 里登记的可执行命令就指向这里）。"""
    rclpy.init(args=args)          # 初始化 ROS2 运行环境
    node = ArduinoSerialBridge()   # 创建节点
    try:
        rclpy.spin(node)           # 让节点"转起来"：持续等待并处理消息/定时器
    finally:
        node.destroy_node()        # 无论是否出错，都清理资源
        rclpy.shutdown()           # 关闭 ROS2 环境


if __name__ == "__main__":
    main()
