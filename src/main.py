# main.py

import asyncio
import json
import logging
import os
import signal
import sys
import threading
import warnings
from datetime import datetime

import pymysql
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from qasync import QEventLoop

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF logging
warnings.filterwarnings("ignore", "TSMSendMessageToUIServer.*")

from modules.bot_manager import BotManager

# Module imports
from modules.config_manager import ConfigManager
from modules.gui import MainWindow
from modules.mdb1_database import DatabaseModule
from modules.mt1_telegram import TelegramModule


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

# Removed duplicate main function

def main():
    # Initialize QApplication first
    app = QApplication(sys.argv)
    
    # Create and set event loop before any async operations
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    telegram_module = None
    bot_manager = None
    db_module = None
    
    try:
        # Setup logging with absolute path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(current_dir, '..', 'sessions', 'logs')
        
        print(f"Creating log directory at: {log_dir}")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d")}.log')
        print(f"Log file will be created at: {log_file}")
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', mode='a'),
                logging.StreamHandler()
            ]
        )
        
        logging.info("Starting application...")
        
        # Initialize config manager and check config
        config_manager = ConfigManager()
        if not config_manager.is_config_complete():
            QMessageBox.critical(None, "Error", "Configuration is incomplete")
            return 1
            
        # Initialize modules with proper error handling
        async def init_modules():
            nonlocal telegram_module, bot_manager, db_module
            
            # Initialize database first with explicit port
            db_config = config_manager.get_database_config()
            if 'port' not in db_config:
                db_config['port'] = 3306  # Add default port if not specified
            db_module = DatabaseModule(
                host=db_config['host'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['database'],
                port=db_config.get('port', 3306)
                # Не передавайте use_unicode
            )
            connection_status = await db_module.test_connection()
    
            if connection_status['error']:
                logging.error(f"Database connection failed: {connection_status['error']}")
                QMessageBox.critical(None, "Error", 
                                   f"Could not connect to database:\n{connection_status['error']}")
                return None
                
            logging.info(f"Database connection successful: MySQL {connection_status['version']}")
            
            # Initialize Telegram module
            telegram_config = config_manager.get_telegram_config()
            bot_config = config_manager.get_bot_config()
            
            telegram_module = TelegramModule(
                api_id=int(telegram_config['api_id']),
                api_hash=telegram_config['api_hash'],
                phone_number=telegram_config['phone_number'],
                bot_token=bot_config.get('token')
            )
            
            # Initialize database tables
            if await db_module.is_connected():
                await db_module.ensure_tables_exist()
            
            # Create main window after modules are initialized
            main_window = MainWindow(
                db_module=db_module,
                telegram_module=telegram_module,
                db_connected=True,
                tg_connected=False,
                config_manager=config_manager
            )
            main_window.show()
            return main_window
            
        # Run initialization in event loop
        with loop:
            main_window = loop.run_until_complete(init_modules())
            
            def cleanup():
                # Schedule cleanup using QTimer to avoid coroutine issues
                async def do_cleanup():
                    if telegram_module:
                        await telegram_module.disconnect()
                    if db_module:
                        await db_module.disconnect()
                        
                QTimer.singleShot(0, lambda: asyncio.create_task(do_cleanup()))
                
            app.aboutToQuit.connect(cleanup)
            
            # Run event loop
            loop.run_forever()
            
    except Exception as e:
        logging.error(f"Error in main: {e}")
        QMessageBox.critical(None, "Error", str(e))
        return 1
        
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())

class MainWindow(QMainWindow):
    # ...existing code...
    
    @asyncSlot()
    async def search_accounts_in_groups(self, auto_start=False):
        """Поиск аккаунтов с умным делегированием задач."""
        try:
            for group in self.groups_list:
                # Умное сканирование группы
                scan_result = await self.telegram_module.smart_scan_group(group.id)
                
                if scan_result['success']:
                    logging.info(f"Group {group.id} scanned using {scan_result['method_used']}")
                    
                    # Обработка результатов
                    for member in scan_result['members']:
                        await self.db_module.upsert_user(member)
                        self.add_account_to_table(member)
                else:
                    logging.error(f"Failed to scan group {group.id}: {scan_result['error']}")
                    
        except Exception as e:
            logging.error(f"Search accounts error: {e}")
            QMessageBox.critical(self, "Error", str(e))

    # ...existing code...