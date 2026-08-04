"""「模拟演示」启动脚本：一键拉起 score_player + mock_arduino（不接硬件，纯软件测试）。

和 serial_demo.launch.py 几乎一样，唯一区别是把 arduino_bridge 换成了 mock_arduino
（软件模拟的 Arduino）：不需要插硬件、也不需要串口，任何电脑都能跑通整条链路，
非常适合先在电脑上验证曲谱对不对。

用法：
    ros2 launch violin_ros_bridge mock_demo.launch.py score_path:=/path/to/曲谱.bin

启动顺序：先起 mock_arduino，延迟 1 秒后再起 score_player。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """ROS2 调用这个函数，拿到"要启动哪些节点、怎么配参数"的描述。"""
    return LaunchDescription(
        [
            DeclareLaunchArgument("score_path"),
            # 节点1：模拟 Arduino，立即启动（无需串口/硬件）。
            Node(
                package="violin_ros_bridge",
                executable="mock_arduino",
            ),
            # 节点2：曲谱播放器，延迟 1 秒再启动。
            TimerAction(
                period=1.0,
                actions=[
                    Node(
                        package="violin_ros_bridge",
                        executable="score_player",
                        parameters=[
                            {
                                "score_path": LaunchConfiguration("score_path"),
                                "tick_ms": 10.0,
                            }
                        ],
                    )
                ],
            ),
        ]
    )
