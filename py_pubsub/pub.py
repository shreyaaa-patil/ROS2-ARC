#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class AssignmentListener(Node):
    def __init__(self):
        super().__init__('listener_node')

        # Internal memory slots (initialized as integers)
        self.value_one = 0
        self.value_two = 0

        # Subscribe to both publisher topics
        self.sub_one = self.create_subscription(String, 'topic_one', self.callback_one, 10)
        self.sub_two = self.create_subscription(String, 'topic_two', self.callback_two, 10)

        # Output publisher for the conditional action
        self.action_pub = self.create_publisher(String, 'conditional_output', 10)
        self.get_logger().info("Listener Node online. Monitoring numerical streams...")

    def callback_one(self, msg):
        self.value_one = int(msg.data)
        self.check_conditional_logic()

    def callback_two(self, msg):
        self.value_two = int(msg.data)
        self.check_conditional_logic()

    def check_conditional_logic(self):
        # CONDITIONAL LOGIC: Trigger action if both values match and are greater than 20
        if self.value_one == self.value_two and self.value_one > 7:
            output_msg = String()
            output_msg.data = f"CRITERIA MATCHED: BOTH VALUES EQUAL {self.value_one}! EXECUTING ACTION."
            self.action_pub.publish(output_msg)
            self.get_logger().warn(output_msg.data) # Logs highlighted yellow text
        else:
            self.get_logger().info(f"Numbers -> Val 1: {self.value_one} | Val 2: {self.value_two}")

def main(args=None):
    rclpy.init(args=args)
    node = AssignmentListener()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
