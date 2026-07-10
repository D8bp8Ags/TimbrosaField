#!/usr/bin/env python3
"""Entry point for the Field Recorder Analyzer application.

Sets up logging, creates the QApplication, shows the splash screen, and
launches MainWindow (defined in ui/main_window.py — moved there in Fase 7).

Typical usage::

if __name__ == "__main__":     main()
"""

import logging
import os
import sys
import time

import my_app.app_config as app_config
from PyQt5.QtWidgets import QApplication
from my_app.ui.components import ApplicationStylist, SplashScreen
from my_app.ui.main_window import MainWindow

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------
logging.basicConfig(
    #level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.DEBUG),
    level=getattr(logging, os.getenv("LOG_LEVEL", "DEBUG").upper(), logging.INFO),
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Initialize and run the Field Recorder Analyzer Qt application."""
    logger.info("Starting Field Recorder Analyzer…")

    app = QApplication(sys.argv)

    # App setup
    app.setApplicationName(app_config.APP_NAME)
    app.setApplicationVersion(app_config.APP_VERSION)
    app.setOrganizationName(app_config.ORG_NAME)

    # Import and apply ApplicationStylist FIRST
    ApplicationStylist.apply_complete_styling(app)

    # Create and show splash screen
    splash = SplashScreen(app)
    splash.show_and_process()

    # Update loading text
    splash.update_message("Initializing components...")

    # Create main window
    main_window = MainWindow()

    # Final message
    splash.set_ready()
    time.sleep(0.5)

    # Hide splash, show main
    splash.hide()
    main_window.show()

    logger.info("Field Recorder Analyzer started.")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
