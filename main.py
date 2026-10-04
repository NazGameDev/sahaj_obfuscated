"""main.py — Entry point for সহজ-Sahaj v3.0."""
import os
import sys

from PyQt6.QtWidgets import (
    QApplication, QLabel, QSplashScreen,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontDatabase, QMovie, QIcon, QPixmap

# app_utils is safe to import early — it does not pull in voice_typing.
import app_utils
from app_utils import resource_path
from app_styles import set_font_families
import sahaj_license
from app_dialogs import ensure_licensed


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    clipboard = QApplication.clipboard()
    clipboard.clear()

    app_icon_path = resource_path("header_icon.png")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))

    # --- LICENSE CHECK (before splash) ---
    if not ensure_licensed():
        sys.exit(0)

    # --- Load fonts (fast, main thread) ---
    available_families = []

    font_path1 = resource_path("Nirmala.ttf")
    font_id1 = QFontDatabase.addApplicationFont(font_path1)
    if font_id1 != -1:
        family1 = QFontDatabase.applicationFontFamilies(font_id1)[0]
        available_families.append(family1)

    font_path2 = resource_path("Banikanta.ttf")
    font_id2 = QFontDatabase.addApplicationFont(font_path2)
    if font_id2 != -1:
        family2 = QFontDatabase.applicationFontFamilies(font_id2)[0]
        if family2 not in available_families:
            available_families.append(family2)

    if not available_families:
        available_families = ["Nirmala UI", "Segoe UI", "Arial"]
    else:
        available_families.extend(["Nirmala UI", "Segoe UI", "Arial"])

    seen = set()
    available_families = [f for f in available_families if not (f in seen or seen.add(f))]
    set_font_families(available_families)

    # --- Splash: shown BEFORE any heavy imports so it appears fast ---
    splash_gif_path = resource_path("splash_animation.gif")

    if os.path.exists(splash_gif_path):
        splash = QLabel()
        splash.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        splash.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        movie = QMovie(splash_gif_path)
        splash.setMovie(movie)
        movie.start()
    else:
        splash_label = QLabel()
        splash_label.setFixedSize(450, 250)
        splash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        splash_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2C3E50, stop:1 #3498DB);
                color: white;
                font-family: "Segoe UI";
                font-size: 26px;
                font-weight: bold;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        splash_label.setText("সহজ-Sahaj-v3.0\n\nLoading, please wait...\n\nDeveloped by Nazmul Hussain")
        splash_pixmap = splash_label.grab()
        splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint)

    splash.show()
    app.processEvents()

    # ============================================================
    # Everything below runs AFTER the splash is visible.
    # ============================================================

    # Deferred: voice_typing pulls in torch, transformers, onnxruntime, pyaudio.
    try:
        import voice_typing
        app_utils.voice_typing = voice_typing
    except ImportError as e:
        app_utils.voice_typing = None
        print(f"Voice typing module not available: {e}")

    # Optional typing_modes
    try:
        import typing_modes
        app_utils.typing_modes = typing_modes
        app_utils.HAS_TYPING_MODES = True
    except ImportError as e:
        app_utils.typing_modes = None
        app_utils.HAS_TYPING_MODES = False
        print(f"Typing modes module not available: {e}")

    # Deferred: heavy app_window import (pulls PyQt6 etc.)
    from app_window import AssameseTypingApp
    from app_workers import SetupThread

    # Start the background model-copy thread now that the splash is up
    setup_thread = SetupThread()
    setup_thread.start()

    # Create the main window — positioned OFF-SCREEN so it doesn't
    # peek around the splash.
    main_window = AssameseTypingApp()
    main_window.move(-10000, -10000)
    main_window.show()
    app.processEvents()

    def finish_startup():
        def loaders_busy():
            try:
                if getattr(main_window, "asr_loader_thread", None) and \
                        main_window.asr_loader_thread.isRunning():
                    return True
                if getattr(main_window, "loader_thread", None) and \
                        main_window.loader_thread.isRunning():
                    return True
            except Exception:
                pass
            return False

        def reveal_window_and_dismiss(cover):
            try:
                main_window.move(0, 0)
                app.processEvents()
                main_window.showMaximized()
                main_window.raise_()
                main_window.activateWindow()
            except Exception:
                pass

            def _dismiss():
                try:
                    if cover is not None:
                        cover.close()
                except Exception:
                    pass
            QTimer.singleShot(500, _dismiss)

        if not loaders_busy():
            reveal_window_and_dismiss(splash)
            return

        warmup = QLabel(
            "⏳ Warming up Sahaj's AI Engines...\n"
            "...Ready in just a moment !"
        )
        warmup.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            warmup.setFixedSize(splash.size())
            warmup.move(splash.geometry().topLeft())
        except Exception:
            warmup.setFixedSize(450, 250)
        warmup.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        warmup.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #2C3E50, stop:1 #3498DB);
                color: white;
                font-family: "Segoe UI";
                font-size: 20px;
                font-weight: bold;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        warmup.show()
        try:
            splash.close()
        except Exception:
            pass

        def poll():
            if loaders_busy():
                QTimer.singleShot(300, poll)
            else:
                reveal_window_and_dismiss(warmup)

        QTimer.singleShot(300, poll)

    QTimer.singleShot(7000, finish_startup)
    sys.exit(app.exec())