import serial

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, UInt8MultiArray

from .protocol import validate_packet


class ArduinoSerialBridge(Node):
    def __init__(self) -> None:
        super().__init__("violin_arduino_bridge")
        self.declare_parameter("port", "/dev/ttyACM0")
        self.declare_parameter("baud", 115200)

        port = str(self.get_parameter("port").value)
        baud = int(self.get_parameter("baud").value)
        self.serial = serial.Serial(port=port, baudrate=baud, timeout=0)
        self.rx_buffer = bytearray()

        self.subscription = self.create_subscription(
            UInt8MultiArray,
            "/violin/event_raw",
            self.send_event,
            10,
        )
        self.status_publisher = self.create_publisher(String, "/violin/arduino_status", 10)
        self.timer = self.create_timer(0.01, self.read_status)
        self.get_logger().info(f"Opened Arduino serial port {port} at {baud} baud")

    def send_event(self, message: UInt8MultiArray) -> None:
        packet = bytes(message.data)
        try:
            validate_packet(packet)
        except ValueError as exc:
            self.get_logger().error(f"Not sending invalid packet: {exc}")
            return

        self.serial.write(packet)
        self.serial.flush()

    def read_status(self) -> None:
        waiting = self.serial.in_waiting
        if waiting:
            self.rx_buffer.extend(self.serial.read(waiting))

        while b"\n" in self.rx_buffer:
            line, _, remainder = self.rx_buffer.partition(b"\n")
            self.rx_buffer = bytearray(remainder)
            text = line.decode("utf-8", errors="replace").strip()
            if not text:
                continue

            message = String()
            message.data = text
            self.status_publisher.publish(message)
            self.get_logger().info(f"Arduino: {text}")

    def destroy_node(self) -> bool:
        if self.serial.is_open:
            self.serial.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ArduinoSerialBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
