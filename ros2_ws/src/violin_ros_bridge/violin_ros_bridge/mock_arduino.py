"""模拟 Arduino 节点（不接真硬件时，用来测试整条链路能不能跑通）。

【为什么需要它】
    真正的 Arduino 要插硬件、烧程序，调试不方便。
    这个节点"假装"自己是 Arduino：
      - 同样订阅 /violin/event_raw（接收演奏事件）
      - 收到后解码、打印出每个字段，并回一句 ACK（"已收到"）
    这样不接硬件也能验证 score_player 发的事件对不对。

【在系统里的位置】（对比 arduino_bridge.py）
        score_player ──> /violin/event_raw ──>  mock_arduino（软件模拟）
                                              或 arduino_bridge（→真硬件）

ROS2 基础概念见 arduino_bridge.py 顶部的"小白速成"，这里不再重复。
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

from .protocol import decode_packet


class MockArduino(Node):
    """假的 Arduino：收到事件就解码并回显，方便无硬件调试。"""

    def __init__(self) -> None:
        super().__init__("violin_mock_arduino")
        # 订阅演奏事件话题，收到就调用 receive_event。
        self.subscription = self.create_subscription(
            UInt8MultiArray,
            "/violin/event_raw",
            self.receive_event,
            10,
        )
        # 同时发布一个状态话题（和真 arduino_bridge 用同一个话题，行为一致）。
        self.status_publisher = self.create_publisher(String, "/violin/arduino_status", 10)
        self.event_count = 0  # 收到了多少个事件（计数，方便观察）
        self.get_logger().info("Mock Arduino ready")

    def receive_event(self, message: UInt8MultiArray) -> None:
        """收到一个事件：解码出各字段，回显 ACK；数据非法则回 NACK。"""
        try:
            event = decode_packet(bytes(message.data))
        except ValueError as exc:
            # 解码失败：回一句 "NACK"（Not Acknowledged，未确认/有错）。
            self.publish_status(f"NACK invalid_packet {exc}")
            return

        # 解码成功：计数 +1，回一句 "ACK"（Acknowledged，已确认）并带上各字段值。
        self.event_count += 1
        self.publish_status(
            "ACK "
            f"count={self.event_count} "
            f"tick={event['tick']} "
            f"pitch={event['pitch']} "
            f"duration={event['duration']} "
            f"string={event['string_id']} "
            f"finger={event['finger']} "
            f"position={event['position']} "
            f"bow_dir={event['bow_direction']} "
            f"bow_speed={event['bow_speed']} "
            f"bow_force={event['bow_force']}"
        )

    def publish_status(self, text: str) -> None:
        """把一段文本作为状态消息发布出去，并打印到日志。"""
        message = String()
        message.data = text
        self.status_publisher.publish(message)
        self.get_logger().info(text)


def main(args=None) -> None:
    """启动入口（详见 arduino_bridge.py 里同名的 main）。"""
    rclpy.init(args=args)
    node = MockArduino()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
