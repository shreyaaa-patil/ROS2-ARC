#!/usr/bin/env python3

import sys
import rclpy
from rclpy.node import Node
from voltage_monitor.srv import VoltageError   # Custom service type

import threading


class ErrorInjectorNode(Node):
    """
    Interactive CLI client that calls the /set_error_percent service
    on the SimulatorNode to inject Gaussian noise.

    Usage
    -----
    Run the node. Then type in the terminal:
      15      → inject 15 % noise
      0       → clear noise
      q       → quit
    """

    def __init__(self):
        super().__init__('error_injector_node')

        # Create a client for the VoltageError service
        self.client = self.create_client(VoltageError, 'set_error_percent')

        # Block until the simulator server comes online
        self.get_logger().info('Waiting for /set_error_percent service (SimulatorNode)…')
        while not self.client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('  still waiting…')

        self.get_logger().info(
            'Service found!  '
            'Enter error % (0–100) and press Enter.  q = quit.'
        )

        # Read stdin in a background thread (same pattern as my_addr client)
        t = threading.Thread(target=self._stdin_reader, daemon=True)
        t.start()

    def send_error(self, percent: float):
        """Build the request, send it asynchronously, spin until done."""
        req = VoltageError.Request()
        req.error_percent = percent

        # call_async() does NOT block — returns a Future immediately
        future = self.client.call_async(req)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            result = future.result()
            self.get_logger().info(
                f'Response → success={result.success}  |  "{result.message}"'
            )
        else:
            self.get_logger().error('Service call failed or timed out.')

    def _stdin_reader(self):
        for line in sys.stdin:
            line = line.strip()
            if line.lower() == 'q':
                self.get_logger().info('Quitting ErrorInjectorNode.')
                rclpy.shutdown()
                break
            try:
                val = float(line)
                if -100.0 <= val <= 100.0:
                    self.send_error(val)
                else:
                    self.get_logger().warn('Value must be between 0 and 100.')
            except ValueError:
                self.get_logger().warn(f'Invalid input: "{line}"')


def main(args=None):
    rclpy.init(args=args)

    injector = ErrorInjectorNode()

    try:
        rclpy.spin(injector)
    except KeyboardInterrupt:
        pass
    finally:
        injector.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
