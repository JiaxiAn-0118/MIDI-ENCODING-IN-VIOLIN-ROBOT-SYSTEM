from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray

from .protocol import packet_pitch, packet_tick, split_score


class ScorePlayer(Node):
    def __init__(self) -> None:
        super().__init__("violin_score_player")
        self.declare_parameter("score_path", "")
        self.declare_parameter("tick_ms", 10.0)

        score_path = self.get_parameter("score_path").value
        if not score_path:
            raise ValueError("Set the score_path parameter to a .bin score file")

        self.tick_ms = float(self.get_parameter("tick_ms").value)
        self.packets = split_score(Path(score_path).expanduser().read_bytes())
        self.publisher = self.create_publisher(UInt8MultiArray, "/violin/event_raw", 10)
        self.next_index = 0
        self.start_ns = self.get_clock().now().nanoseconds
        self.timer = self.create_timer(0.002, self.publish_due_events)

        self.get_logger().info(
            f"Loaded {len(self.packets)} events from {score_path}; tick={self.tick_ms} ms"
        )

    def publish_due_events(self) -> None:
        elapsed_ms = (self.get_clock().now().nanoseconds - self.start_ns) / 1_000_000

        while self.next_index < len(self.packets):
            packet = self.packets[self.next_index]
            target_ms = packet_tick(packet) * self.tick_ms
            if elapsed_ms < target_ms:
                return

            message = UInt8MultiArray()
            message.data = list(packet)
            self.publisher.publish(message)
            self.get_logger().info(
                f"Published event={self.next_index} tick={packet_tick(packet)} "
                f"pitch={packet_pitch(packet)}"
            )
            self.next_index += 1

        self.timer.cancel()
        self.get_logger().info("Score playback complete")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScorePlayer()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
