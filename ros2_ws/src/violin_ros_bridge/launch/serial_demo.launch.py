"""「串口演示」启动脚本：一键拉起 score_player + arduino_bridge（接真硬件用）。

什么是 launch 文件？
    就是一份"启动剧本"：一条命令就能按预设把多个节点配好参数同时跑起来，
    省得手动开好几个终端、敲一堆 ros2 run。

用法（Ubuntu/ROS2 环境）：
    ros2 launch violin_ros_bridge serial_demo.launch.py score_path:=/path/to/曲谱.bin

启动顺序：
    1) 先起 arduino_bridge（打开串口，准备收发）；
    2) 延迟 2 秒后再起 score_player（开始播放）——
       留出时间让串口稳定，避免一上来就丢包。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """ROS2 调用这个函数，拿到"要启动哪些节点、怎么配参数"的描述。"""
    return LaunchDescription(
        [
            # 声明两个启动参数（命令行可用 score_path:=xxx 传入）。
            DeclareLaunchArgument("score_path"),                              # 曲谱文件路径（必填）
            DeclareLaunchArgument("port", default_value="/dev/ttyACM0"),     # 串口设备名（有默认值）

            # 节点1：串口桥，立即启动；把上面的参数传给它。
            Node(
                package="violin_ros_bridge",
                executable="arduino_bridge",
                parameters=[
                    {
                        "port": LaunchConfiguration("port"),
                        "baud": 115200,
                    }
                ],
            ),
            # 节点2：曲谱播放器，延迟 2 秒再启动（TimerAction = 延时启动动作）。
            TimerAction(
                period=2.0,
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
