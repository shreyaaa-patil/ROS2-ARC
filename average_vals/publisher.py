import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
import random

class AvgVal(Node):
    def __init__(self):
        super().__init__('avg_publisher')
        self.publisher = self.create_publisher(Int32, 'values', 10)
        self.timer = self.create_timer(2.0, self.publish_temp)

    def publish_temp(self):
        val = random.uniform(1, 1000)
        msg = Int32()
        msg.data = val
        self.publisher.publish(msg)
        self.get_logger().info(f'Published Value: {val}')

def main():
    rclpy.init()
    node = AvgVal()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
