#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from voltage_monitor.srv import VoltageError   # Custom service type

import numpy as np


# ── Constants ─────────────────────────────────────────────────────────────────
NOMINAL_PEAK_VOLTAGE = 4.0    # Volts  (step-down transformer output)
MAINS_FREQUENCY      = 50     # Hz
SAMPLES_PER_CYCLE    = 200    # Samples per full AC cycle → 10 kHz sample rate


class SimulatorNode(Node):
    """
    Simulates the step-down transformer output: 4 V peak, 50 Hz sine wave.

    - Publishes one full cycle (200 samples) at 50 times per second
      on /voltage_samples.
    - Hosts a VoltageError service so external callers (error injector
      or GUI) can set Gaussian noise level at runtime.
    """

    def __init__(self):
        super().__init__('simulator_node')

        # ── Publisher ─────────────────────────────────────────────────────────
        self.samples_pub = self.create_publisher(
            Float32MultiArray,
            'voltage_samples',
            10
        )

        # ── Service: set error % ──────────────────────────────────────────────
        self.srv = self.create_service(
            VoltageError,           # Custom service type
            'set_error_percent',    # Service name
            self.handle_set_error   # Callback invoked on every request
        )

        # ── State ─────────────────────────────────────────────────────────────
        self.error_percent = 0.0    # Current noise level (0–100 %)

        # ── Timer: publish one cycle at MAINS_FREQUENCY ───────────────────────
        period = 1.0 / MAINS_FREQUENCY   # 0.02 s → 50 Hz
        self.timer = self.create_timer(period, self.publish_cycle)

        self.get_logger().info(
            f'SimulatorNode is up — publishing {MAINS_FREQUENCY} Hz sine wave '
            f'({SAMPLES_PER_CYCLE} samples/cycle) on /voltage_samples'
        )

    # ── Service callback ──────────────────────────────────────────────────────

    def handle_set_error(self, request, response):
        """
        Called whenever a client sends a VoltageError request.
        Clamps error_percent to [0, 100] and applies it immediately.
        """
        self.error_percent = float(np.clip(request.error_percent, 0.0, 100.0))
        response.success = True
        response.message = (
            f'Error percent set to {self.error_percent:.1f}% — '
            f'noise σ = {(self.error_percent / 100.0) * NOMINAL_PEAK_VOLTAGE:.4f} V'
        )
        self.get_logger().info(response.message)
        return response   # Must return response

    # ── Timer callback ────────────────────────────────────────────────────────

    def publish_cycle(self):
        """Generate one complete 50 Hz cycle (200 samples) and publish."""
        t = np.linspace(0.0, 1.0 / MAINS_FREQUENCY,
                        SAMPLES_PER_CYCLE, endpoint=False)

        # Clean 4 V peak sine wave
        clean = NOMINAL_PEAK_VOLTAGE * np.sin(2 * np.pi * MAINS_FREQUENCY * t)

        # Add Gaussian noise scaled by error_percent of peak voltage

        scale = 1.0 + (self.error_percent / 100.0)
        signal = clean*scale

        msg = Float32MultiArray()
        msg.data = signal.tolist()
        self.samples_pub.publish(msg)

        self.get_logger().debug(
            f'Published cycle  error={self.error_percent:.1f}%  '
            f'max_sample={float(np.max(np.abs(signal))):.4f} V'
        )


def main(args=None):
    rclpy.init(args=args)

    simulator = SimulatorNode()

    try:
        rclpy.spin(simulator)
    except KeyboardInterrupt:
        pass
    finally:
        simulator.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
