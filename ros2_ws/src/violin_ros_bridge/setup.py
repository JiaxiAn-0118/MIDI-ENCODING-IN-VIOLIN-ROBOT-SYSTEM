from glob import glob
from setuptools import find_packages, setup


package_name = "violin_ros_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "pyserial"],
    zip_safe=True,
    maintainer="Violin Robot Team",
    maintainer_email="student@example.com",
    description="ROS2 score player and serial bridge for the violin robot.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "score_player = violin_ros_bridge.score_player:main",
            "arduino_bridge = violin_ros_bridge.arduino_bridge:main",
            "mock_arduino = violin_ros_bridge.mock_arduino:main",
        ],
    },
)
