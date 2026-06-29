import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

from .protocol import decode_packet


class MockArduino(Node):
    def __init__(self) -> None:
        super().__init__("violin_mock_arduino")
        self.subscription = self.create_subscription(
            UInt8MultiArray,
            "/violin/event_raw",
            self.receive_event,
            10,
        )
        self.status_publisher = self.create_publisher(String, "/violin/arduino_status", 10)
        self.event_count = 0
        self.get_logger().info("Mock Arduino ready")

    def receive_event(self, message: UInt8MultiArray) -> None:
        try:
            event = decode_packet(bytes(message.data))
        except ValueError as exc:
            self.publish_status(f"NACK invalid_packet {exc}")
            return

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
        message = String()
        message.data = text
        self.status_publisher.publish(message)
        self.get_logger().info(text)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MockArduino()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
