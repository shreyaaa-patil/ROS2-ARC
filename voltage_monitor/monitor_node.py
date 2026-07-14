#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String
from voltage_monitor.srv import VoltageAlarm   # Custom service type

import numpy as np
import collections


# ── Constants ─────────────────────────────────────────────────────────────────
CALIBRATION_CYCLES   = 200    # Average 200 peaks to build baseline limit
DETECTION_WINDOW_CYC = 100    # 2 seconds at 50 Hz for sustained alarm
TOLERANCE_PERCENT    = 20.0   # ±10 % threshold


class MonitorNode(Node):
    """
    Receives voltage samples from /voltage_samples.

    Algorithm
    ---------
    Phase 1 — Calibration (first 200 cycles):
        baseline_limit = mean( |peak_i| ) for i = 1…200

    Phase 2 — Active monitoring:
        upper_threshold = baseline_limit * 1.10
        lower_threshold = baseline_limit * 0.90
        Each cycle → extract positive and negative peaks.
        If |peak| > upper OR |peak| < lower → ALARM.
        If alarm persists for 100 consecutive cycles (2 s) → CRITICAL.

    Publishes:
        /alarm_status  (std_msgs/String)  — human-readable status each cycle

    Hosts:
        /get_alarm_status  (VoltageAlarm service) — on-demand status query
    """

    def __init__(self):
        super().__init__('monitor_node')

        # ── Subscriber ────────────────────────────────────────────────────────
        self.create_subscription(
            Float32MultiArray,
            'voltage_samples',
            self.handle_samples,
            50
        )

        # ── Publisher: alarm status string ────────────────────────────────────
        self.alarm_pub = self.create_publisher(String, 'alarm_status', 10)

        # ── Service: query current alarm state ────────────────────────────────
        self.srv = self.create_service(
            VoltageAlarm,            # Custom service type
            'get_alarm_status',      # Service name
            self.handle_alarm_query  # Callback
        )

        # ── State ─────────────────────────────────────────────────────────────
        self.calibration_peaks: list = []
        self.baseline_limit: float | None = None
        self.upper_threshold = 0.0
        self.lower_threshold = 0.0

        self.last_pos_peak   = 0.0
        self.last_neg_peak   = 0.0
        self.alarm_active    = False
        self.alarm_message   = 'CALIBRATING'

        self.alarm_window = collections.deque(maxlen=DETECTION_WINDOW_CYC)
        self.cycle_count  = 0

        self.get_logger().info(
            f'MonitorNode is up — calibrating over {CALIBRATION_CYCLES} cycles …'
        )

    # ── Sample callback ───────────────────────────────────────────────────────

    def handle_samples(self, msg: Float32MultiArray):
        """Called for every published cycle (200 samples)."""
        samples = np.array(msg.data, dtype=np.float32)
        if samples.size == 0:
            return

        pos_peak = float(np.max(samples))
        neg_peak = float(np.min(samples))
        abs_peak = max(abs(pos_peak), abs(neg_peak))

        self.last_pos_peak = pos_peak
        self.last_neg_peak = neg_peak
        self.cycle_count  += 1

        # ── Phase 1: Calibration ──────────────────────────────────────────────
        if self.baseline_limit is None:
            self.calibration_peaks.append(abs_peak)
            remaining = CALIBRATION_CYCLES - len(self.calibration_peaks)
            self.alarm_message = f'CALIBRATING — {remaining} cycles left'

            if len(self.calibration_peaks) >= CALIBRATION_CYCLES:
                self.baseline_limit  = float(np.mean(self.calibration_peaks))
                self.upper_threshold = self.baseline_limit * (1 + TOLERANCE_PERCENT / 100)
                self.lower_threshold = self.baseline_limit * (1 - TOLERANCE_PERCENT / 100)
                self.get_logger().info(
                    f'Calibration DONE  '
                    f'baseline={self.baseline_limit:.4f} V  '
                    f'upper={self.upper_threshold:.4f} V  '
                    f'lower={self.lower_threshold:.4f} V'
                )
            self._publish_status()
            return

        # ── Phase 2: Active monitoring ────────────────────────────────────────
        self.alarm_active = (
            abs_peak > self.upper_threshold or
            abs_peak < self.lower_threshold
        )

        self.alarm_window.append(self.alarm_active)
        sustained = (
            len(self.alarm_window) == DETECTION_WINDOW_CYC and
            all(self.alarm_window)
        )

        if not self.alarm_active:
            self.alarm_message = 'OK'
        elif abs_peak > self.upper_threshold:
            pct = (abs_peak - self.baseline_limit) / self.baseline_limit * 100
            self.alarm_message = f'OVERVOLTAGE +{pct:.1f}%'
        else:
            pct = (self.baseline_limit - abs_peak) / self.baseline_limit * 100
            self.alarm_message = f'UNDERVOLTAGE -{pct:.1f}%'

        if sustained:
            self.alarm_message = 'CRITICAL: ' + self.alarm_message

        if self.alarm_active:
            self.get_logger().warn(
                f'ALARM  {self.alarm_message}  '
                f'pos={pos_peak:.4f} V  neg={neg_peak:.4f} V'
            )
        else:
            self.get_logger().debug(
                f'OK  pos={pos_peak:.4f} V  neg={neg_peak:.4f} V'
            )

        self._publish_status()

    # ── Service callback ──────────────────────────────────────────────────────

    def handle_alarm_query(self, request, response):
        """
        Called whenever a client (GUI or external tool) requests alarm status.
        Fills in all voltage fields and returns the response object.
        """
        response.positive_peak    = self.last_pos_peak
        response.negative_peak    = self.last_neg_peak
        response.baseline_limit   = self.baseline_limit if self.baseline_limit else 0.0
        response.upper_threshold  = self.upper_threshold
        response.lower_threshold  = self.lower_threshold
        response.alarm_active     = self.alarm_active
        response.sustained_alarm  = (
            len(self.alarm_window) == DETECTION_WINDOW_CYC and
            all(self.alarm_window)
        )
        response.alarm_message    = self.alarm_message

        return response   # Must return response

    # ── Helper ────────────────────────────────────────────────────────────────

    def _publish_status(self):
        msg = String()
        msg.data = (
            f'{self.alarm_message}  '
            f'pos={self.last_pos_peak:.4f}  '
            f'neg={self.last_neg_peak:.4f}  '
            f'baseline={self.baseline_limit or 0.0:.4f}'
        )
        self.alarm_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    monitor = MonitorNode()

    try:
        rclpy.spin(monitor)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
