#!/usr/bin/env python3
"""抓取一帧 RealSense 彩色图并保存，用于 FAST-Calib 标定。

用法：
    python3 capture_image.py /path/to/output.png

订阅 /camera/color/image_raw，收到第一帧后保存为 png 并退出。
"""
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class ImageCapture(Node):
    def __init__(self, save_path: str):
        super().__init__("image_capture")
        self.bridge = CvBridge()
        self.save_path = save_path
        self.sub = self.create_subscription(
            Image, "/camera/color/image_raw", self.callback, 10
        )
        self.get_logger().info(f"等待一帧图像，将保存到 {save_path} ...")

    def callback(self, msg: Image):
        img = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        cv2.imwrite(self.save_path, img)
        self.get_logger().info(f"已保存图像到 {self.save_path}")
        self.destroy_node()
        rclpy.shutdown()


def main():
    rclpy.init()
    save_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/capture.png"
    node = ImageCapture(save_path)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
