from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument("score_path"),
            DeclareLaunchArgument("port", default_value="/dev/ttyACM0"),
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
