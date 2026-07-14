#!/usr/bin/env python3

import sys
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String
from voltage_monitor.srv import VoltageError    # Custom service
from voltage_monitor.srv import VoltageAlarm    # Custom service

import numpy as np
import collections
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QGroupBox, QGridLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


# ── Constants ─────────────────────────────────────────────────────────────────
SAMPLES_PER_CYCLE = 200
DISPLAY_CYCLES    = 4


# ══════════════════════════════════════════════════════════════════════════════
#  Signal bridge: ROS callbacks → Qt main thread
# ══════════════════════════════════════════════════════════════════════════════

class RosSignals(QObject):
    new_samples = pyqtSignal(list)
    new_status  = pyqtSignal(str)


# ══════════════════════════════════════════════════════════════════════════════
#  ROS2 node — runs in a background QThread
# ══════════════════════════════════════════════════════════════════════════════

class GuiNode(Node):
    """
    Subscribes to voltage topics and hosts clients for both custom services.
    Runs inside a background thread; emits Qt signals to update the GUI.
    """

    def __init__(self, signals: RosSignals):
        super().__init__('gui_node')
        self.signals = signals

        # ── Subscribers ───────────────────────────────────────────────────────
        self.create_subscription(
            Float32MultiArray,
            'voltage_samples',
            self._on_samples,
            50
        )
        self.create_subscription(
            String,
            'alarm_status',
            self._on_alarm_status,
            10
        )

        # ── Service client: set error on simulator ────────────────────────────
        self.error_client = self.create_client(VoltageError, 'set_error_percent')

        # ── Service client: query alarm state from monitor ────────────────────
        self.alarm_client = self.create_client(VoltageAlarm, 'get_alarm_status')

        self.get_logger().info('GuiNode started — waiting for services…')
        self.error_client.wait_for_service(timeout_sec=5.0)
        self.alarm_client.wait_for_service(timeout_sec=5.0)
        self.get_logger().info('Services ready.')

    # ── Service calls (called from Qt thread, safe because non-blocking) ──────

    def call_set_error(self, percent: float):
        """Send VoltageError request to simulator asynchronously."""
        req = VoltageError.Request()
        req.error_percent = float(percent)
        future = self.error_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=2.0)
        if future.result():
            self.get_logger().info(f'SetError → {future.result().message}')

    def call_get_alarm(self):
        """
        Query VoltageAlarm service and return the response,
        or None if the call fails.
        """
        req = VoltageAlarm.Request()
        req.query = True
        future = self.alarm_client.call_async(req)
        rclpy.spin_until_future_complete(self, future, timeout_sec=1.0)
        return future.result()   # None if timeout

    # ── Subscription callbacks ────────────────────────────────────────────────

    def _on_samples(self, msg: Float32MultiArray):
        self.signals.new_samples.emit(list(msg.data))

    def _on_alarm_status(self, msg: String):
        self.signals.new_status.emit(msg.data)


# ══════════════════════════════════════════════════════════════════════════════
#  Background ROS thread
# ══════════════════════════════════════════════════════════════════════════════

class RosThread(QThread):
    def __init__(self, node: GuiNode):
        super().__init__()
        self.node = node

    def run(self):
        rclpy.spin(self.node)


# ══════════════════════════════════════════════════════════════════════════════
#  Oscilloscope widget
# ══════════════════════════════════════════════════════════════════════════════

class OscilloscopeWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(7, 3.5), facecolor='#1a1a2e')
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.ax = self.fig.add_subplot(111)
        self._style_axes()

        buf_size = SAMPLES_PER_CYCLE * DISPLAY_CYCLES
        self.buffer = collections.deque([0.0] * buf_size, maxlen=buf_size)
        self.x      = np.arange(buf_size) / SAMPLES_PER_CYCLE

        self.line,         = self.ax.plot(self.x, list(self.buffer),
                                           color='#00ff88', linewidth=1.2)
        self.upper_line      = self.ax.axhline(4.4, color='#ff4444',
                                               linestyle='--', linewidth=1)
        self.lower_line      = self.ax.axhline(3.6, color='#ff4444',
                                               linestyle='--', linewidth=1)
        self.baseline_line   = self.ax.axhline(4.0, color='#ffcc00',
                                               linestyle=':', linewidth=1)
        self.neg_base_line   = self.ax.axhline(-4.0, color='#ffcc00',
                                               linestyle=':', linewidth=1)

        self.ax.set_xlim(0, DISPLAY_CYCLES)
        self.ax.set_ylim(-5.5, 5.5)
        self.fig.tight_layout(pad=0.5)

    def _style_axes(self):
        self.ax.set_facecolor('#0d0d1a')
        self.ax.tick_params(colors='#aaaaaa', labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#333355')
        self.ax.set_xlabel('Cycles', color='#aaaaaa', fontsize=9)
        self.ax.set_ylabel('Voltage (V)', color='#aaaaaa', fontsize=9)
        self.ax.set_title('Live Waveform — 4 V / 50 Hz',
                          color='#ccccff', fontsize=10, pad=4)
        self.ax.grid(True, color='#1e1e3a', linewidth=0.5)

    def push_cycle(self, samples: list):
        self.buffer.extend(samples)
        self.line.set_ydata(list(self.buffer))
        self.draw_idle()

    def update_thresholds(self, baseline: float, upper: float, lower: float):
        self.upper_line.set_ydata([upper, upper])
        self.lower_line.set_ydata([lower, lower])
        self.baseline_line.set_ydata([baseline, baseline])
        self.neg_base_line.set_ydata([-baseline, -baseline])

    def set_alarm_color(self, alarming: bool):
        self.line.set_color('#ff3333' if alarming else '#00ff88')


# ══════════════════════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self, node: GuiNode):
        super().__init__()
        self.node = node
        self.setWindowTitle('AC Voltage Monitor — ROS2')
        self.setMinimumSize(1100, 700)
        self._apply_dark_theme()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel('⚡  AC VOLTAGE MONITOR  —  ROS2')
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont('Consolas', 14, QFont.Bold))
        title.setStyleSheet('color: #00ccff; padding: 4px;')
        root.addWidget(title)

        # Main row: oscilloscope + status panel
        main_row = QHBoxLayout()
        root.addLayout(main_row, stretch=1)

        # ── Oscilloscope ──────────────────────────────────────────────────────
        self.scope = OscilloscopeWidget()
        main_row.addWidget(self.scope, stretch=2)

        # ── Status panel ──────────────────────────────────────────────────────
        panel = QWidget()
        panel.setMinimumWidth(300)
        panel_layout = QVBoxLayout(panel)
        main_row.addWidget(panel)

        # Phase label
        self.phase_lbl = QLabel('Phase: WAITING…')
        self.phase_lbl.setStyleSheet(
            'color: #ffcc00; font-size: 11px; font-family: Consolas;')
        panel_layout.addWidget(self.phase_lbl)

        # Alarm indicator
        self.alarm_box = QLabel('  ✔  NORMAL  ')
        self.alarm_box.setAlignment(Qt.AlignCenter)
        self.alarm_box.setFont(QFont('Consolas', 13, QFont.Bold))
        self.alarm_box.setFixedHeight(50)
        self.alarm_box.setStyleSheet(
            'background-color:#003300; color:#00ff66; '
            'border:2px solid #00aa44; border-radius:6px;')
        panel_layout.addWidget(self.alarm_box)

        # Stats group
        stats = QGroupBox('Voltage Statistics')
        stats.setStyleSheet(self._group_style())
        grid = QGridLayout(stats)
        grid.setSpacing(6)

        self.pos_peak_lbl  = self._val_label('—')
        self.neg_peak_lbl  = self._val_label('—')
        self.baseline_lbl  = self._val_label('—')
        self.upper_lbl     = self._val_label('—')
        self.lower_lbl     = self._val_label('—')

        for row, (name, widget) in enumerate([
            ('Positive Peak',           self.pos_peak_lbl),
            ('Negative Peak',           self.neg_peak_lbl),
            ('Baseline Limit',          self.baseline_lbl),
            ('Upper Threshold (+10%)',  self.upper_lbl),
            ('Lower Threshold (-10%)',  self.lower_lbl),
        ]):
            lbl = QLabel(name + ':')
            lbl.setStyleSheet('color:#aaaacc; font-size:11px;')
            grid.addWidget(lbl, row, 0)
            grid.addWidget(widget, row, 1)

        panel_layout.addWidget(stats)

        # Raw status string
        self.status_lbl = QLabel('Status: —')
        self.status_lbl.setStyleSheet(
            'color:#666688; font-size:10px; font-family:Consolas;')
        self.status_lbl.setWordWrap(True)
        panel_layout.addWidget(self.status_lbl)
        panel_layout.addStretch()

        # ── Error injection ───────────────────────────────────────────────────
        err_group = QGroupBox('Error Injection  (calls /set_error_percent service)')
        err_group.setStyleSheet(self._group_style())
        err_row = QHBoxLayout(err_group)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(0)
        self.slider.setTickInterval(10)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { height:6px; background:#2a2a4a; border-radius:3px; }
            QSlider::handle:horizontal { background:#00ccff; width:16px; height:16px;
                                         margin:-5px 0; border-radius:8px; }
            QSlider::sub-page:horizontal { background:#0077aa; border-radius:3px; }
        """)

        self.pct_lbl = QLabel('0.0 %')
        self.pct_lbl.setFixedWidth(55)
        self.pct_lbl.setStyleSheet(
            'color:#00ccff; font-size:12px; font-family:Consolas; font-weight:bold;')
        self.slider.valueChanged.connect(
            lambda v: self.pct_lbl.setText(f'{v:.1f} %'))

        inject_btn = QPushButton('Inject Error')
        inject_btn.setFixedWidth(110)
        inject_btn.setStyleSheet(
            'QPushButton{background:#331a00;color:#ffaa00;border:1px solid #cc6600;'
            'border-radius:5px;padding:5px;}'
            'QPushButton:hover{background:#4d2600;}')
        inject_btn.clicked.connect(self._inject_error)

        clear_btn = QPushButton('Clear Error')
        clear_btn.setFixedWidth(100)
        clear_btn.setStyleSheet(
            'QPushButton{background:#001a1a;color:#00ffcc;border:1px solid #006655;'
            'border-radius:5px;padding:5px;}'
            'QPushButton:hover{background:#003322;}')
        clear_btn.clicked.connect(self._clear_error)

        err_row.addWidget(QLabel('Error %:  '))
        err_row.addWidget(self.slider, stretch=1)
        err_row.addWidget(self.pct_lbl)
        err_row.addWidget(inject_btn)
        err_row.addWidget(clear_btn)
        root.addWidget(err_group)

        # ── Polling timer: query alarm service every 500 ms ───────────────────
        self.poll_timer = QTimer()
        self.poll_timer.setInterval(500)
        self.poll_timer.timeout.connect(self._poll_alarm_service)
        self.poll_timer.start()

    # ── Connect ROS signals ───────────────────────────────────────────────────

    def connect_signals(self, signals: RosSignals):
        signals.new_samples.connect(self.scope.push_cycle)
        signals.new_status.connect(self._on_alarm_status)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_alarm_status(self, raw: str):
        self.status_lbl.setText('Status: ' + raw[:150])

        # Infer alarm from text prefix
        alarming = 'OK' not in raw.split('  ')[0]
        critical = raw.startswith('CRITICAL')
        self.scope.set_alarm_color(alarming)

        if critical:
            self.alarm_box.setText('  ⚠  ' + raw.split('  ')[0] + '  ')
            self.alarm_box.setStyleSheet(
                'background:#330000;color:#ff2222;'
                'border:2px solid #ff0000;border-radius:6px;')
        elif alarming and 'CALIBRAT' not in raw:
            self.alarm_box.setText('  ⚠  ' + raw.split('  ')[0] + '  ')
            self.alarm_box.setStyleSheet(
                'background:#331100;color:#ff8800;'
                'border:2px solid #ff6600;border-radius:6px;')
        elif 'CALIBRAT' in raw:
            self.alarm_box.setText('  ⏳  CALIBRATING…  ')
            self.alarm_box.setStyleSheet(
                'background:#1a1a00;color:#ffcc00;'
                'border:2px solid #aa8800;border-radius:6px;')
        else:
            self.alarm_box.setText('  ✔  NORMAL  ')
            self.alarm_box.setStyleSheet(
                'background:#003300;color:#00ff66;'
                'border:2px solid #00aa44;border-radius:6px;')

    def _poll_alarm_service(self):
        """
        Polls /get_alarm_status service every 500 ms.
        Runs in Qt thread — delegates the ROS call to the node.
        """
        def _call():
            result = self.node.call_get_alarm()
            if result:
                self._update_stats(result)

        t = threading.Thread(target=_call, daemon=True)
        t.start()

    def _update_stats(self, r):
        """Update voltage statistics panel from VoltageAlarm service response."""
        self.pos_peak_lbl.setText(f'{r.positive_peak:+.4f} V')
        self.neg_peak_lbl.setText(f'{r.negative_peak:+.4f} V')
        self.baseline_lbl.setText(f'{r.baseline_limit:.4f} V')
        self.upper_lbl.setText(f'{r.upper_threshold:.4f} V')
        self.lower_lbl.setText(f'{r.lower_threshold:.4f} V')

        if r.baseline_limit > 0:
            self.scope.update_thresholds(
                r.baseline_limit, r.upper_threshold, r.lower_threshold)

        if 'CALIBRAT' in r.alarm_message:
            self.phase_lbl.setText('Phase: CALIBRATING')
            self.phase_lbl.setStyleSheet(
                'color:#ffcc00; font-size:11px; font-family:Consolas;')
        else:
            self.phase_lbl.setText('Phase: MONITORING  ✔')
            self.phase_lbl.setStyleSheet(
                'color:#00ff88; font-size:11px; font-family:Consolas;')

    def _inject_error(self):
        val = float(self.slider.value())
        t = threading.Thread(
            target=self.node.call_set_error, args=(val,), daemon=True)
        t.start()

    def _clear_error(self):
        self.slider.setValue(0)
        t = threading.Thread(
            target=self.node.call_set_error, args=(0.0,), daemon=True)
        t.start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _val_label(self, text: str):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl.setStyleSheet(
            'color:#00ccff; font-size:12px; font-family:Consolas; font-weight:bold;')
        return lbl

    def _group_style(self):
        return (
            'QGroupBox{color:#aaaacc;font-size:11px;font-weight:bold;'
            'border:1px solid #333355;border-radius:6px;margin-top:8px;padding-top:8px;}'
            'QGroupBox::title{subcontrol-origin:margin;left:10px;top:0px;}'
        )

    def _apply_dark_theme(self):
        self.setStyleSheet(
            'QMainWindow,QWidget{background-color:#12121f;color:#ccccdd;}'
            'QLabel{font-family:"Segoe UI",Arial,sans-serif;font-size:11px;}'
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main(args=None):
    rclpy.init(args=args)

    signals  = RosSignals()
    ros_node = GuiNode(signals)

    app    = QApplication(sys.argv)
    window = MainWindow(ros_node)
    window.connect_signals(signals)
    window.show()

    ros_thread = RosThread(ros_node)
    ros_thread.start()

    exit_code = app.exec_()

    ros_thread.quit()
    ros_thread.wait()
    ros_node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
