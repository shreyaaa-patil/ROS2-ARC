import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32

class SubscriberZ(Node):
    def __init__(self):
        super().__init__('subscriber_1')
        self.subscriber = self.create_subscription(Int32, 'topic_a', self.listener_callback, 10)
        self.publisher = self.create_publisher(Int32, 'topic_z', 10)

    def listener_callback(self, msg):
        if msg.data % 2 == 0:  # multiples of 2
            self.publisher.publish(msg)
            self.get_logger().info(f'Subscriber 1 published: {msg.data}')

def main():
    rclpy.init()
    node = SubscriberZ()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
