"""ROS2 包的"安装清单"（告诉 ROS2 怎么安装、怎么找到本包里的节点）。

这个文件是 Python 打包工具(setuptools)的标准做法，ROS2 在上面加了一些约定。
执行 `colcon build` 时，ROS2 会读这个文件，把包安装到工作空间里。

关键看两处：
    entry_points —— 把三个 main() 注册成可以直接 `ros2 run` 的命令：
        ros2 run violin_ros_bridge score_player
        ros2 run violin_ros_bridge arduino_bridge
        ros2 run violin_ros_bridge mock_arduino
    data_files   —— 把 launch 启动脚本等资源文件，安装到 ROS2 能找到的位置。
"""

from glob import glob
from setuptools import find_packages, setup


package_name = "violin_ros_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        # 下面三行是 ROS2 的约定：注册包资源、安装 package.xml、安装 launch 脚本。
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "pyserial"],  # pyserial：操作串口的库（arduino_bridge 用）
    zip_safe=True,
    maintainer="Violin Robot Team",
    maintainer_email="student@example.com",
    description="ROS2 score player and serial bridge for the violin robot.",
    license="MIT",
    entry_points={
        "console_scripts": [
            # 注册三条命令，格式为：命令名 = 模块:函数
            "score_player = violin_ros_bridge.score_player:main",
            "arduino_bridge = violin_ros_bridge.arduino_bridge:main",
            "mock_arduino = violin_ros_bridge.mock_arduino:main",
        ],
    },
)
