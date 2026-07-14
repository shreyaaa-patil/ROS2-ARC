import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
import random

class TempPublisher(Node):
    def __init__(self):
        super().__init__('temp_publisher')
        self.publisher = self.create_publisher(Int32, 'temperature', 10)
        self.timer = self.create_timer(2.0, self.publish_temp)

    def publish_temp(self):
        temp = random.uniform(1, 1000)
        msg = Int32()
        msg.data = temp
        self.publisher.publish(msg)
        self.get_logger().info(f'Published Temp: {temp}')

def main():
    rclpy.init()
    node = TempPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
