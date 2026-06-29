from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument("score_path"),
            Node(
                package="violin_ros_bridge",
                executable="mock_arduino",
            ),
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
