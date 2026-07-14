import rclpy
from rclpy.node import Node #Node is the base clsss used to create ros2 nodes

class MyNode(Node): #inheritance
    def __init__(self): #constructor
        super().__init__('first_node')
        self.get_logger().info("Hello World ")
        self.create_timer(1.0,self.timer_callback) # 1 second interval
        self.count=1

    def timer_callback(self):
            self.get_logger().info(f"Hello {self.count}")
            self.count+=1


def main(args=None):
    rclpy.init(args=args) # Initialize ROS 2 communication
    node = MyNode() # Create your node instance
    rclpy.spin(node)
    rclpy.shutdown() #close ROS 2 communication

if __name__ == '__main__':
    main()
