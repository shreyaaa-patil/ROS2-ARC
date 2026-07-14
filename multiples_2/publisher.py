import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32

class PublisherA(Node):
    def __init__(self):
        super().__init__('publisher_1')
        self.publisher_ = self.create_publisher(Int32, 'topic_a', 10)
        self.timer = self.create_timer(1.0, self.publish_number)
        self.counter = 1

    def publish_number(self):
        msg = Int32()
        msg.data = self.counter
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publisher: {msg.data}')
        self.counter += 1

def main():
    rclpy.init()
    node = PublisherA()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
