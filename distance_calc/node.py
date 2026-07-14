import rclpy
from rclpy.node import Node
import random
import math

class DistanceCalc(Node):
    def __init__(self):
        super().__init__('distance_calc')
        self.radius = 50.0 #limit radius
        self.ref_x=0.0
        self.ref_y=0.0
        self.mov_x=0.0
        self.mov_y=0.0

        self.get_logger().info('Distance calculator node has started')
        self.get_logger().info(f"Initial reference points are: ({self.ref_x},{self.ref_y})")

        self.ref_timer=self.create_timer(30.0,self.update_ref_point)
        self.loop_timer=self.create_timer(0.5,self.exec_loop)

    def generate_random(self, center_x, center_y):
        theta= random.uniform(0, 2*math.pi) #get random angle between 0 to 2pi radians
        r =self.radius * math.sqrt(random.uniform(0,1)) #??
        x= center_x + r*math.cos(theta)
        y=center_y + r*math.sin(theta)
        return x,y

    def update_ref_point(self):
        self.ref_x=random.uniform(-100.0,100.0)
        self.ref_y=random.uniform(-100.0,100.0)

        self.get_logger().warn(
            f'REFERENCE POINT CHANGED TO ({self.ref_x:.2f},{self.ref_y:.2f})'
        )

    def exec_loop(self):
        self.mov_x, self.mov_y = self.generate_random(self.ref_x,self.ref_y)
        distance = math.sqrt((self.mov_x - self.ref_x)**2 + (self.mov_y - self.ref_y)**2)
        self.get_logger().info(
            f'Ref: ({self.ref_x:.2f},{self.ref_y:.2f} | '
            f'Moving: ({self.mov_x:.2f},{self.mov_y:.2f}) | '
            f'Distance: {distance:.2f} cm'
        )

def main(args=None):
    rclpy.init(args=args)
    node = DistanceCalc()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
