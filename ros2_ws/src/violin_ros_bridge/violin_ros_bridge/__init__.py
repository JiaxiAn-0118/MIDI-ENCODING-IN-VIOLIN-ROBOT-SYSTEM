"""violin_ros_bridge —— ROS2 工作空间里的一个 Python 包。

这个包里有三个"节点"（ROS2 里独立运行的小程序，互不干扰、能同时跑）：
    score_player   读二进制曲谱，按时序逐个发布演奏事件
    arduino_bridge 把事件通过串口转发给 Arduino（接真硬件时用）
    mock_arduino   假装是 Arduino，回显收到的事件（没硬件时测试用）

这个 __init__.py 本身没有实际代码——它的存在只是告诉 Python：
"这个文件夹是一个包，里面的 .py 模块可以被 import"。
"""
