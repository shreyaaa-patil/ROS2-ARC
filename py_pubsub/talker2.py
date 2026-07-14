#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import random

class PublisherTwo(Node):
    def __init__(self):
        super().__init__('publisher_two_node')
        self.publisher_ = self.create_publisher(String, 'topic_two', 10)
        self.create_timer(2.0, self.timer_callback)
        self.get_logger().info("Publisher Two has started.")

    def timer_callback(self):
        msg = String()
        # Generates a random integer between 1 and 30
        random_num = random.randint(1, 30)
        msg.data = str(random_num)
        
        self.publisher_.publish(msg)
        self.get_logger().info(f"Published to topic_two: {msg.data}")

def main(args=None):
    rclpy.init(args=args)
    node = PublisherTwo()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
