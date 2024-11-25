# main.py

import sys
import asyncio
import logging
import threading
import os
import warnings
import signal

# Добавьте эти строки до импорта PyQt6
os.environ["QT_EnableHighDpiScaling"] = "1"
os.environ["QT_UseHighDpiPixmaps"] = "1"

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QGuiApplication, QFont
from PyQt6.QtCore import Qt
from qasync import QEventLoop

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF logging
warnings.filterwarnings("ignore", "TSMSendMessageToUIServer.*")

# Module imports
from modules.config_manager import ConfigManager
from modules.mdb1_database import DatabaseModule
from modules.mt1_telegram import TelegramModule
from modules.gui import MainWindow
from modules.bot_manager import BotManager

async def cleanup(telegram_module, bot_manager, db_module):
    """Cleanup resources before exit."""
    try:
        if bot_manager and bot_manager._connected:
            await bot_manager.stop()
        if telegram_module:
            await telegram_module.disconnect()
        if db_module:
            await db_module.disconnect()
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")

def main():
    try:
        # Удаление настройки колірного простору
        # QApplication.setColorSpec(QApplication.ColorSpec.Color)
    
        # Удаление некорректных вызовов setAttribute
        # QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
        # QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    
        # Initialize application
        app = QApplication(sys.argv)
        
        # Установка стандартного шрифта
        default_font = QFont("Segoe UI", 10)
        app.setFont(default_font)
        
        loop = QEventLoop(app)
        asyncio.set_event_loop(loop)
    
        # Fix logging configuration - use 'levelname' instead of 'levelнем'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

        # Ініціалізація менеджера конфігурації
        config_manager = ConfigManager()
        config_manager.load_config()

        # Перевірка повноти конфігурації
        if not config_manager.is_config_complete():
            logging.error("Configuration is incomplete. Please fill in all required fields.")
            QMessageBox.critical(None, "Error", "Configuration is incomplete. Please fill in all required fields.")
            sys.exit(1)

        # Ініціалізація модулів
        db_config = config_manager.get_database_config()
        db_module = DatabaseModule(
            host=db_config.get('host'),
            user=db_config.get('user'),
            password=db_config.get('password'),
            database=db_config.get('database')
        )

        telegram_config = config_manager.get_telegram_config()
        bot_config = config_manager.get_bot_config()

        telegram_module = TelegramModule(
            api_id=int(telegram_config.get('api_id')),
            api_hash=telegram_config.get('api_hash'),
            phone_number=telegram_config.get('phone_number'),
            bot_token=bot_config.get('bot_token')  # Will be None if not set
        )

        # Modify bot initialization
        bot_manager = None
        if bot_config.get('token'):
            try:
                bot_manager = BotManager(
                    bot_token=bot_config['token'],
                    api_id=int(bot_config['api_id']),
                    api_hash=bot_config['api_hash'],
                    session_name=bot_config.get('session_name', 'bot_session')
                )
                # Connect bot manager with config manager
                bot_manager.set_config_manager(config_manager)
                # Start the bot
                loop.run_until_complete(bot_manager.start())
                # Check initial status
                loop.run_until_complete(bot_manager.check_status())
            except Exception as e:
                logging.error(f"Failed to initialize bot: {e}")
                config_manager.update_bot_status('error', str(e))
                bot_manager = None

        # Перевірка підключення до бази даних та створення таблиць
        async def initialize_database():
            db_connected = await db_module.is_connected()
            if db_connected:
                await db_module.ensure_tables_exist()
            else:
                logging.error("Failed to connect to the database.")
                QMessageBox.critical(None, "Error", "Failed to connect to the database.")
                sys.exit(1)

        # Запуск асинхронної ініціалізації бази даних
        loop.run_until_complete(initialize_database())

        # Create cleanup callback
        async def async_cleanup():
            await cleanup(telegram_module, bot_manager, db_module)
            app.quit()

        def handle_exit():
            # Schedule cleanup using QTimer to avoid running coroutines directly
            QTimer.singleShot(0, lambda: asyncio.create_task(async_cleanup()))

        app.aboutToQuit.connect(handle_exit)

        # Set up signal handlers to use the same cleanup
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}")
            handle_exit()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        main_window = MainWindow(
            db_module=db_module,
            telegram_module=telegram_module,
            db_connected=True,
            tg_connected=False,
            config_manager=config_manager
        )
        # Установка прозрачности окна
        main_window.setWindowOpacity(1.0)  # Полностью непрозрачное окно
        main_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Установка флагов окна для полной прозрачности и без рамок
        main_window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowSystemMenuHint | 
            Qt.WindowType.WindowMinimizeButtonHint | 
            Qt.WindowType.WindowMaximizeButtonHint
        )

        main_window.show()

        # Запуск циклу подій
        with loop:
            loop.run_forever()

    except Exception as e:
        logging.error(f"Error during application startup: {e}")
        QMessageBox.critical(None, "Critical Error", f"An error occurred: {e}")
        # Handle cleanup on error differently
        if 'loop' in locals():
            try:
                loop.run_until_complete(cleanup(telegram_module, bot_manager, db_module))
            except Exception as cleanup_error:
                logging.error(f"Error during emergency cleanup: {cleanup_error}")
        sys.exit(1)

if __name__ == "__main__":
    print(dir(Qt))
    main()