"""截图识字（SnipOCR）入口：主窗 + 系统托盘 + 全局热键 + 流程编排。

流程：热键/按钮 -> CaptureOverlay 全屏框选 -> 裁剪选区
     -> OcrEngine 后台识别（附二维码检测）-> ResultWindow 展示/复制；
     可选自动复制到剪贴板、识别历史入库。
"""

from __future__ import annotations

import faulthandler
import os
import sys
import time

from PyQt6.QtCore import QObject, QRect, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

from app.about_dialog import AboutDialog
from app.autostart import is_frozen, set_autostart
from app.capture import CaptureOverlay
from app.constants import APP_NAME, APP_VERSION
from app.history import HistoryManager
from app.history_window import HistoryWindow
from app.ocr_engine import OcrEngine, pixmap_to_ndarray
from app.result_window import ResultWindow
from app.settings import DATA_DIR, Settings, pretty_hotkey
from app.settings_dialog import SettingsDialog

_MAIN_QSS = """
QMainWindow, #central { background: #15171d; }
#big { color: #f0f2f7; font: 700 24px "Microsoft YaHei"; }
#sub { color: #8a93a3; font: 13px "Microsoft YaHei"; }
#card {
    background: #1e222b;
    border: 1px solid #2c323d;
    border-radius: 14px;
}
#hotkey {
    color: #6ea1ff;
    background: #22314f;
    border: 1px solid #2f4470;
    border-radius: 10px;
    padding: 8px 20px;
    font: 700 20px "Microsoft YaHei";
}
#hotkey_desc { color: #8a93a3; font: 12px "Microsoft YaHei"; }
#status { color: #5b6270; font: 11px "Microsoft YaHei"; }
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4d88ff, stop:1 #3d7bfd);
    color: white; border: none;
    border-radius: 9px; padding: 11px 0; font: 600 14px "Microsoft YaHei";
}
QPushButton#primary:hover { background: #5590ff; }
QPushButton#primary:pressed { background: #2f6fe0; }
QPushButton#ghost {
    background: #262b36; color: #c6ccd8; border: 1px solid #333a48;
    border-radius: 9px; padding: 11px 0; font: 13px "Microsoft YaHei";
}
QPushButton#ghost:hover { background: #2e3441; color: #e7eaf0; }
#fcard {
    background: #1a1e26;
    border: 1px solid #262c37;
    border-radius: 10px;
}
#ftitle { color: #dfe3ea; font: 600 12px "Microsoft YaHei"; }
#fdesc { color: #5f6875; font: 11px "Microsoft YaHei"; }
"""


class HotkeyBridge(QObject):
    """keyboard 库在后台线程回调 -> 转成 Qt 信号（自动排队到主线程）。"""

    activated = pyqtSignal()

    @pyqtSlot()
    def fire(self) -> None:
        self.activated.emit()


class MainWindow(QMainWindow):
    """主窗口，同时承担应用控制器职责。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — 屏幕截图文字识别")
        icon = self._build_icon()
        self.setWindowIcon(icon)
        self.resize(640, 500)

        # 配置与历史
        self.settings = Settings()
        self.history = HistoryManager(
            max_items=int(self.settings.get("history_max"))
        )

        # 组件
        self._overlay: CaptureOverlay | None = None
        self._result: ResultWindow | None = None
        self._engine = OcrEngine(self)
        self._engine.result_ready.connect(self._on_ocr_done)
        self._engine.error_occurred.connect(self._on_ocr_error)
        self._bridge = HotkeyBridge()
        self._bridge.activated.connect(self.start_capture)
        self._hotkey_remover = None  # keyboard.add_hotkey 返回的注销函数

        self._build_ui()
        self._tray = self._build_tray(icon)
        self.settings.changed.connect(self._on_setting_changed)
        hotkey_ok = self._apply_hotkey(self.settings.get("hotkey"))
        QTimer.singleShot(300, self._engine.warm_up)  # 后台预热模型

        # 启动形态：首次运行 / 热键注册失败 -> 显示主窗（引导与兜底）；
        # 其余情况静默驻留托盘，不占任务栏。
        if self.settings.get("first_run") or not hotkey_ok:
            self.show()
            self.settings.set("first_run", False)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        central = QFrame()
        central.setObjectName("central")
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(18)

        # ---- 顶部：图标 + 标题 ----
        hero = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(self.windowIcon().pixmap(56, 56))
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        big = QLabel(APP_NAME)
        big.setObjectName("big")
        sub = QLabel("框选屏幕任意区域，离线识别文字 / 二维码")
        sub.setObjectName("sub")
        title_col.addWidget(big)
        title_col.addWidget(sub)
        hero.addWidget(icon_label)
        hero.addSpacing(16)
        hero.addLayout(title_col)
        hero.addStretch(1)
        lay.addLayout(hero)

        # ---- 主卡片：热键 + 操作按钮 ----
        card = QFrame()
        card.setObjectName("card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(20, 18, 20, 18)
        card_lay.setSpacing(14)

        hot_row = QHBoxLayout()
        self.hotkey_label = QLabel(
            pretty_hotkey(self.settings.get("hotkey"))
        )
        self.hotkey_label.setObjectName("hotkey")
        hot_desc = QLabel("全局热键 · 可在设置中修改")
        hot_desc.setObjectName("hotkey_desc")
        hot_row.addWidget(self.hotkey_label)
        hot_row.addSpacing(12)
        hot_row.addWidget(hot_desc)
        hot_row.addStretch(1)
        card_lay.addLayout(hot_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_capture = QPushButton("开始截图")
        btn_capture.setObjectName("primary")
        btn_capture.setMinimumWidth(190)
        btn_capture.clicked.connect(self.start_capture)
        btn_history = QPushButton("识别历史")
        btn_history.setObjectName("ghost")
        btn_history.clicked.connect(self.open_history)
        btn_settings = QPushButton("设置")
        btn_settings.setObjectName("ghost")
        btn_settings.clicked.connect(self.open_settings)
        btn_exit = QPushButton("退出程序")
        btn_exit.setObjectName("ghost")
        btn_exit.setMinimumWidth(104)
        btn_exit.clicked.connect(QApplication.instance().quit)
        btn_row.addWidget(btn_capture)
        btn_row.addWidget(btn_history)
        btn_row.addWidget(btn_settings)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_exit)
        card_lay.addLayout(btn_row)
        lay.addWidget(card)

        # ---- 特性小卡 ----
        features = QHBoxLayout()
        features.setSpacing(10)
        for emoji, title, desc in (
            ("⚡", "本地识别", "onnx 离线推理"),
            ("🔒", "隐私安全", "数据不出本机"),
            ("🧾", "历史回溯", "自动保存记录"),
        ):
            fcard = QFrame()
            fcard.setObjectName("fcard")
            flay = QVBoxLayout(fcard)
            flay.setContentsMargins(14, 11, 14, 11)
            flay.setSpacing(2)
            ftitle = QLabel(f"{emoji}  {title}")
            ftitle.setObjectName("ftitle")
            fdesc = QLabel(desc)
            fdesc.setObjectName("fdesc")
            flay.addWidget(ftitle)
            flay.addWidget(fdesc)
            features.addWidget(fcard, 1)
        lay.addLayout(features)
        lay.addStretch(1)

        self.status_label = QLabel("识别完全在本地离线运行 · 数据不上传")
        self.status_label.setObjectName("status")
        lay.addWidget(
            self.status_label, 0, Qt.AlignmentFlag.AlignHCenter
        )

        self.setStyleSheet(_MAIN_QSS)

    @staticmethod
    def _build_icon() -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#3b82f6"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
        font = QFont("Microsoft YaHei", 30)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(QRect(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, "识")
        painter.end()
        return QIcon(pixmap)

    def _build_tray(self, icon: QIcon) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(icon, self)
        menu = QMenu(self)

        self.act_capture_tray = QAction("截图识别", self)
        self.act_capture_tray.triggered.connect(self.start_capture)
        act_history = QAction("识别历史", self)
        act_history.triggered.connect(self.open_history)
        act_settings = QAction("设置…", self)
        act_settings.triggered.connect(self.open_settings)
        act_about = QAction(f"关于 {APP_NAME}…", self)
        act_about.triggered.connect(self.open_about)
        self.act_autostart = QAction("开机自启", self)
        self.act_autostart.setCheckable(True)
        self.act_autostart.setChecked(bool(self.settings.get("autostart")))
        self.act_autostart.toggled.connect(self._on_tray_autostart)
        if not is_frozen():
            self.act_autostart.setEnabled(False)
            self.act_autostart.setToolTip("仅在打包为 exe 后可用")
        act_show = QAction("显示主窗口", self)
        act_show.triggered.connect(self._show_and_raise)
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(QApplication.instance().quit)

        menu.addAction(self.act_capture_tray)
        menu.addAction(act_history)
        menu.addSeparator()
        menu.addAction(self.act_autostart)
        menu.addAction(act_settings)
        menu.addAction(act_about)
        menu.addSeparator()
        menu.addAction(act_show)
        menu.addAction(act_quit)
        self._refresh_tray_texts()

        tray.setContextMenu(menu)
        tray.setToolTip(f"{APP_NAME} — 屏幕截图文字识别")
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _refresh_tray_texts(self) -> None:
        if hasattr(self, "act_capture_tray"):
            self.act_capture_tray.setText(
                f"截图识别（{pretty_hotkey(self.settings.get('hotkey'))}）"
            )

    # ---------- 热键 ----------
    def _apply_hotkey(self, hotkey: str) -> bool:
        """注册全局热键；重复调用会先注销旧热键（支持热更新）。

        返回是否注册成功（失败时主窗需要显示出来兜底）。
        """
        if self._hotkey_remover is not None:
            try:
                self._hotkey_remover()
            except Exception:
                pass
            self._hotkey_remover = None
        try:
            import keyboard

            self._hotkey_remover = keyboard.add_hotkey(
                hotkey, self._bridge.fire
            )
            self.status_label.setText("识别完全在本地离线运行 · 数据不上传")
            return True
        except Exception as exc:
            self.status_label.setText(
                f"⚠ 全局热键注册失败（{exc}），可用“开始截图”按钮触发"
            )
            return False

    def _on_setting_changed(self, key: str, value) -> None:
        if key == "hotkey":
            self._apply_hotkey(value)
            self.hotkey_label.setText(pretty_hotkey(value))
            self._refresh_tray_texts()

    def _on_tray_autostart(self, checked: bool) -> None:
        if not is_frozen():
            return
        ok = set_autostart(checked)
        self.settings.set("autostart", checked)
        if not ok:  # 写注册表失败：回滚勾选状态
            self.act_autostart.blockSignals(True)
            self.act_autostart.setChecked(not checked)
            self.act_autostart.blockSignals(False)

    # ---------- 流程编排 ----------
    def start_capture(self) -> None:
        if self._overlay is not None:
            return  # 已在框选中
        if self._result is not None:
            self._result.close()
            self._result = None
        self.hide()
        overlay = CaptureOverlay()
        overlay.captured.connect(self._on_captured)
        overlay.cancelled.connect(self._on_cancelled)
        self._overlay = overlay
        overlay.start()

    def _release_overlay(self) -> None:
        if self._overlay is not None:
            overlay, self._overlay = self._overlay, None
            overlay.deleteLater()

    def _on_captured(self, pixmap: QPixmap, rect) -> None:
        self._release_overlay()
        try:
            image = pixmap_to_ndarray(pixmap)  # QPixmap 只能在主线程转换
        except Exception as exc:
            self._on_ocr_error(f"图像转换失败: {exc}")
            return
        self._result = ResultWindow(anchor=rect)
        self._result.retake_requested.connect(self.start_capture)
        self._result.show_loading()
        try:
            submitted = self._engine.recognize(image)
        except Exception as exc:  # 提交阶段异常也要让用户看到，避免假死
            self._result.set_result(f"识别提交失败：{exc}")
            return
        if not submitted:
            self._result.set_result("（上一次识别尚未结束，请稍候再试）")

    def _on_cancelled(self) -> None:
        self._release_overlay()
        self._show_and_raise()

    def _on_ocr_done(self, text: str, qr: str) -> None:
        text = (text or "").strip()
        qr = (qr or "").strip()
        if self._result is not None:
            self._result.set_result(text, qr)
        if text:
            if self.settings.get("auto_copy"):
                QApplication.clipboard().setText(text)
            if self.settings.get("history_enabled"):
                self.history.add(text)

    def _on_ocr_error(self, message: str) -> None:
        if self._result is not None:
            self._result.set_result(f"识别失败：{message}")

    # ---------- 子窗口 ----------
    def open_history(self) -> None:
        HistoryWindow(self.history, self).exec()

    def open_settings(self) -> None:
        SettingsDialog(self.settings, self).exec()

    def open_about(self) -> None:
        AboutDialog(self).exec()

    # ---------- 窗口 ----------
    def _show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_and_raise()

    def closeEvent(self, event) -> None:  # noqa: N802
        """点关闭 = 最小化到托盘，从托盘菜单“退出”才真正退出。"""
        if self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                APP_NAME,
                "程序已最小化到托盘，按 "
                f"{pretty_hotkey(self.settings.get('hotkey'))} 随时截图识别",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            event.accept()


def _install_crash_logger() -> None:
    """崩溃日志：native 崩溃（faulthandler）与未捕获异常写入
    %APPDATA%/SnipOCR/crash.log，便于排查 --noconsole 模式下的问题。"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        stream = open(DATA_DIR / "crash.log", "a", encoding="utf-8", buffering=1)
    except OSError:
        return
    stream.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start "
                 f"pid={os.getpid()} =====\n")
    try:
        faulthandler.enable(stream)
    except Exception:
        pass

    def _hook(exc_type, exc_value, exc_tb):
        import traceback

        traceback.print_exception(exc_type, exc_value, exc_tb, file=stream)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def _is_another_instance_running() -> bool:
    """单实例检测：同名互斥量已存在说明已有实例在托盘驻留。"""
    import ctypes

    ERROR_ALREADY_EXISTS = 183
    ctypes.windll.kernel32.CreateMutexW(
        None, False, "SnipOCR_SingleInstance"
    )
    return ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS


def main() -> None:
    if _is_another_instance_running():
        return  # 已有实例驻留托盘，静默退出避免多开
    _install_crash_logger()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 托盘常驻
    window = MainWindow()  # 是否显示主窗由 first_run / 热键状态决定
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
