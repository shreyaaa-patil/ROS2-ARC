import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

class TempSubscriber(Node):
    def __init__(self):
        super().__init__('temp_subscriber')
        self.subscriber = self.create_subscription(Float32, 'temperature', self.listener_callback, 10)

    def listener_callback(self, msg):
        temp = msg.data
        if temp < 15:
            category = "Cold"
        elif 15 <= temp <= 30:
            category = "Normal"
        else:
            category = "Hot"
        self.get_logger().info(f'Received Temp: {temp:.2f}°C → {category}')

def main():
    rclpy.init()
    node = TempSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
