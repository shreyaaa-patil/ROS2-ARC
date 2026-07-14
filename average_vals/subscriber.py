import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32

class AverageVals(Node):
    def __init__(self):
        super().__init__('avg_val')
        self.subscriber = self.create_subscription(Int32, 'avg_val', self.listener_callback, 10)
        self.publisher = self.create_publisher(Int32, 'average_node', 10)
        self.sum=0
        self.count=0
        self.avg=0

    def listener_callback(self, msg):
        self.sum+=msg
        self.count+=1
        self.avg=self.sum/self.count
        self.publisher.publish(msg)
        self.get_logger().info(f'Subscriber published: {msg.data} | average: {self.avg}')


def main():
    rclpy.init()
    node = AverageVals()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
