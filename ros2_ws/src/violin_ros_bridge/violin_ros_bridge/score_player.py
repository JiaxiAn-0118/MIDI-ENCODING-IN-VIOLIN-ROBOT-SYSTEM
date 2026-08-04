"""曲谱播放节点（按时序，把曲子里的音符一个一个发布出去）。

【一句话】读取 .bin 二进制曲谱，到了哪个音该响的时间，就把它发出去。

【在系统里的位置】
    .bin 曲谱文件 ──> 本节点 score_player ──> /violin/event_raw 话题
                                                      │
                                          ┌───────────┴────────────┐
                                   arduino_bridge(→真硬件)     mock_arduino(软件回显)

【时间是怎么控制的】
    每个"事件"里带一个 tick（触发时刻，1 tick = 10 ms）。
    本节点记录开始时间，然后每隔 2ms 检查一次：
    "现在过去多久了？有没有哪个事件到了它该触发的 tick？" 有就发出去。
    这样整首曲子就能按真实节奏播放。

ROS2 基础概念见 arduino_bridge.py 顶部的"小白速成"，这里不再重复。
"""

from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray

from .protocol import packet_pitch, packet_tick, split_score


class ScorePlayer(Node):
    """曲谱播放器：加载 .bin，按 tick 时间逐个发布演奏事件。"""

    def __init__(self) -> None:
        super().__init__("violin_score_player")
        # 两个参数：曲谱文件路径、tick 与毫秒的换算（默认 1 tick = 10 ms）。
        self.declare_parameter("score_path", "")
        self.declare_parameter("tick_ms", 10.0)

        # 读取曲谱路径参数。
        score_path = self.get_parameter("score_path").value
        if not score_path:
            # 没给曲谱就没法播放，直接报错退出。
            raise ValueError("Set the score_path parameter to a .bin score file")

        self.tick_ms = float(self.get_parameter("tick_ms").value)
        # 把整个 .bin 文件读进来，切成一个个 12 字节数据包（顺带校验合法性）。
        self.packets = split_score(Path(score_path).expanduser().read_bytes())
        # 演奏事件就发到这个话题（arduino_bridge / mock_arduino 都在听它）。
        self.publisher = self.create_publisher(UInt8MultiArray, "/violin/event_raw", 10)
        self.next_index = 0                                # 下一个该播的事件序号
        self.start_ns = self.get_clock().now().nanoseconds # 记下"开始播放"的时刻（纳秒）
        # 每 0.002 秒(2ms)检查一次"有没有事件到点了"。
        self.timer = self.create_timer(0.002, self.publish_due_events)

        self.get_logger().info(
            f"Loaded {len(self.packets)} events from {score_path}; tick={self.tick_ms} ms"
        )

    def publish_due_events(self) -> None:
        """定时器回调：把所有"已到点"的事件依次发出去。"""
        # 从开始到现在过去了多少毫秒。
        elapsed_ms = (self.get_clock().now().nanoseconds - self.start_ns) / 1_000_000

        # 只要还有事件没播，就循环判断。
        while self.next_index < len(self.packets):
            packet = self.packets[self.next_index]
            # 这个事件该在第几毫秒触发 = 它的 tick 数 × 每个 tick 的毫秒数。
            target_ms = packet_tick(packet) * self.tick_ms
            if elapsed_ms < target_ms:
                # 还没到这个事件的时间，先不播，等下一次定时器再检查。
                return

            # 到点了！把它包装成消息发布出去。
            message = UInt8MultiArray()
            message.data = list(packet)
            self.publisher.publish(message)
            self.get_logger().info(
                f"Published event={self.next_index} tick={packet_tick(packet)} "
                f"pitch={packet_pitch(packet)}"
            )
            self.next_index += 1  # 前进到下一个事件

        # 走到这里说明所有事件都播完了：停掉定时器，曲子结束。
        self.timer.cancel()
        self.get_logger().info("Score playback complete")


def main(args=None) -> None:
    """启动入口（详见 arduino_bridge.py 里同名的 main）。"""
    rclpy.init(args=args)
    node = ScorePlayer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
