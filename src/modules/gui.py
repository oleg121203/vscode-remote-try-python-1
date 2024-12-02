# modules/gui.py

from __future__ import annotations

import asyncio
import logging
import re
import sys
from typing import Any, List, Optional

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qasync import QEventLoop, asyncSlot
from telethon import errors
from telethon.tl.types import (
    Channel,
    UserStatusLastMonth,
    UserStatusLastWeek,
    UserStatusOffline,
    UserStatusOnline,
    UserStatusRecently,
)

from modules.bot_manager import BotManager
from modules.config_manager import ConfigManager
from modules.file_processor import FileProcessor
from modules.mdb1_database import DatabaseModule
from modules.mt1_telegram import TelegramModule
from modules.themes import get_complete_dialog_style, themes

# Replace relative imports with absolute ones
from modules.translations import translations

# Set initial language and theme
current_language = 'uk'  # Default language
current_theme = 'hacker'  # Default theme


class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(10, 5, 10, 5)
        self.main_layout.setSpacing(10)
        self.setLayout(self.main_layout)

        self.title_layout = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setFont(QFont("Arial", 16))
        self.update_title()
        self.title_layout.addWidget(self.title_label)
        self.main_layout.addLayout(self.title_layout)

        self.main_layout.addStretch()

        self.dynamic_widgets_layout = QHBoxLayout()
        self.dynamic_widgets_layout.setContentsMargins(0, 0, 0, 0)
        self.dynamic_widgets_layout.setSpacing(5)
        self.main_layout.addLayout(self.dynamic_widgets_layout)

        self.controls_layout = QHBoxLayout()
        self.setup_window_controls()
        self.main_layout.addLayout(self.controls_layout)

        self.grip_area = QWidget(self)
        self.grip_area.setFixedSize(200, 30)  # Adjust size as needed
        self.grip_area.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
            QWidget:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        self.title_layout.insertWidget(0, self.grip_area)

        self.moving = False
        self.global_pos = None

    def setup_window_controls(self):
        button_size = 30

        self.minimize_button = QPushButton("—")
        self.minimize_button.setFixedSize(button_size, button_size)
        self.minimize_button.clicked.connect(self.minimize_window)

        self.maximize_button = QPushButton("□")
        self.maximize_button.setFixedSize(button_size, button_size)
        self.maximize_button.clicked.connect(self.toggle_maximize)

        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(button_size, button_size)
        self.close_button.clicked.connect(self.parent().close)

        self.controls_layout.addWidget(self.minimize_button)
        self.controls_layout.addWidget(self.maximize_button)
        self.controls_layout.addWidget(self.close_button)

    def minimize_window(self):
        """Safely minimize the window by checking parent window type"""
        parent = self.window()
        if isinstance(parent, QMainWindow):
            parent.showMinimized()
        else:
            logging.warning("Parent window not found or not a QMainWindow")

    def translate(self, key):
        return translations[current_language].get(key, key)

    def update_title(self):
        self.title_label.setText(self.translate('control_interface'))

    def toggle_maximize(self):
        if self.parent().isMaximized():
            self.parent().showNormal()
            self.maximize_button.setText("□")
        else:
            self.parent().showMaximized()
            self.maximize_button.setText("❐")

    def mousePressEvent(self, event):
        """Handle mouse press with improved position tracking."""
        if event.button() == Qt.MouseButton.LeftButton and self.grip_area.geometry().contains(event.pos()):
            self.moving = True
            self.global_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """Smoother window movement with position delta calculation."""
        if self.moving and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.global_pos
            self.window().move(self.window().pos() + delta)
            self.global_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        """Clean release of window movement."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.moving = False
            self.global_pos = None
            event.accept()
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event):
        """Handle double click to maximize/restore window."""
        if self.grip_area.geometry().contains(event.pos()):
            if self.window().isMaximized():
                self.window().showNormal()
                self.maximize_button.setText("□")
            else:
                self.window().showMaximized()
                self.maximize_button.setText("❐")
            event.accept()
        else:
            event.ignore()


class AuthDialog(QDialog):
    def __init__(self, title: str, label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.value = None

        layout = QVBoxLayout()

        self.label_widget = QLabel(label)
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.EchoMode.Normal)
        layout.addWidget(self.label_widget)
        layout.addWidget(self.input)

        self.button = QPushButton("OK")
        self.button.clicked.connect(self.accept)
        layout.addWidget(self.button)

        self.setLayout(layout)
        self.apply_theme()

    def apply_theme(self):
        theme = themes[current_theme]
        background_color = theme['background_color']
        text_color = theme['text_color']
        button_color = theme['button_color']
        button_hover_color = theme['button_hover_color']
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {background_color};
                color: {text_color};
            }}
            QLabel {{
                color: {text_color};
            }}
            QLineEdit {{
                background-color: white;
                color: black;
            }}
            QPushButton {{
                background-color: {button_color};
                color: {text_color};
            }}
            QPushButton:hover {{
                background-color: {button_hover_color};
            }}
        """)

    def accept(self):
        self.value = self.input.text()
        super().accept()

    async def asyncExec(self):
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def on_finished():
            future.set_result(self.result() == QDialog.DialogCode.Accepted)
            self.deleteLater()

        self.finished.connect(on_finished)
        self.show()

        return await future

    def init_ui(self):
        # ...existing code...
        self.sms_input = QLineEdit()
        self.sms_input.setPlaceholderText("Введите SMS-код")
        self.sms_button = QPushButton("Подтвердить")
        self.sms_button.clicked.connect(self.submit_sms_code)
        layout.addWidget(self.sms_input)
        layout.addWidget(self.sms_button)
        # ...existing code...

    def submit_sms_code(self):
        code = self.sms_input.text()
        asyncio.create_task(self.parent().telegram_module.sign_in_with_code(code))
        self.close()


class ConfigGUI(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.config_manager = config_manager
        self.setWindowTitle(self.translate('settings'))
        self.setModal(True)

        # Set fixed size for more compact window
        self.setFixedSize(500, 400)  # Reduced from 800x600

        # Get screen geometry for centering
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(
            (screen.width() - 500) // 2,  # Center horizontally
            (screen.height() - 400) // 2,  # Center vertically
            500,  # Width
            400   # Height
        )

        # Initialize UI elements as None
        self.api_id_input = None
        self.api_hash_input = None
        self.phone_number_input = None
        self.db_host_input = None
        self.db_port_input = None  # Add port input field
        self.db_user_input = None
        self.db_password_input = None
        self.db_name_input = None
        self.transparency_slider = None
        self.language_selector = None
        self.theme_selector = None
        self.bot_token_input = None
        self.bot_api_id_input = None
        self.bot_api_hash_input = None
        self.limits_slider = None
        self.limits_value_label = None
        self.bot_status_label = None

        # Variables for moving
        self._is_moving = False
        self._start_pos = None

        # Create main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Set size and position
        if parent:
            parent_geometry = parent.geometry()
            self.setGeometry(
                parent_geometry.x() + parent_geometry.width() // 2 - 400,
                parent_geometry.y() + parent_geometry.height() // 2 - 300,
                800,
                600
            )

        # Setup UI components
        self.setup_ui()
        
        # Apply theme and load settings
        self.apply_theme()
        self.load_existing_settings()

    def setup_ui(self):
        """Initialize all UI components with compact layout"""
        self.main_layout.setContentsMargins(10, 10, 10, 10)  # Reduced margins
        self.main_layout.setSpacing(5)  # Reduced spacing

        # Add top bar
        self.top_bar = QWidget()
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(0)
        
        # Create content widget with tabs
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Initialize tabs
        self.tabs = QTabWidget()
        self.setup_tabs()
        content_layout.addWidget(self.tabs)
        
        # Add buttons at the bottom
        buttons_layout = QHBoxLayout()
        self.setup_buttons(buttons_layout)
        content_layout.addLayout(buttons_layout)
        
        # Add widgets to main layout
        self.main_layout.addWidget(self.top_bar)
        self.main_layout.addWidget(content_widget)

    def setup_tabs(self):
        # General tab with compact layout
        self.general_tab = QWidget()
        general_layout = QFormLayout(self.general_tab)
        general_layout.setContentsMargins(5, 5, 5, 5)  # Small margins
        general_layout.setSpacing(5)  # Reduced spacing
        general_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Initialize input fields
        self.api_id_input = QLineEdit()
        self.api_hash_input = QLineEdit()
        self.phone_number_input = QLineEdit()
        self.db_host_input = QLineEdit()
        self.db_port_input = QLineEdit()  # Add port input
        self.db_user_input = QLineEdit()
        self.db_password_input = QLineEdit()
        self.db_name_input = QLineEdit()
        
        # Make input fields smaller
        for input_field in [self.api_id_input, self.api_hash_input, 
                          self.phone_number_input, self.db_host_input,
                          self.db_port_input,  # Add to small fields
                          self.db_user_input, self.db_password_input, 
                          self.db_name_input]:
            input_field.setFixedHeight(25)  # Smaller height
            
        # Add fields to general layout
        general_layout.addRow(QLabel("API ID:"), self.api_id_input)
        general_layout.addRow(QLabel("API Hash:"), self.api_hash_input)
        general_layout.addRow(QLabel(self.translate('phone_number')), self.phone_number_input)
        general_layout.addRow(QLabel("DB Host:"), self.db_host_input)
        general_layout.addRow(QLabel("DB Port:"), self.db_port_input)  # Add port field
        general_layout.addRow(QLabel("DB User:"), self.db_user_input)
        general_layout.addRow(QLabel("DB Password:"), self.db_password_input)
        general_layout.addRow(QLabel("DB Name:"), self.db_name_input)

        # Add limits slider
        self.limits_slider = QSlider(Qt.Orientation.Horizontal)
        self.limits_slider.setMinimum(0)
        self.limits_slider.setMaximum(3)  # Changed from 2 to 3
        self.limits_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.limits_slider.setTickInterval(1)
        self.limits_slider.valueChanged.connect(self.update_limits_label)
        
        self.limits_value_label = QLabel()
        general_layout.addRow(QLabel(self.translate('limits_level')), self.limits_slider)
        general_layout.addRow("", self.limits_value_label)

        self.tabs.addTab(self.general_tab, self.translate('general'))

        # Interface tab
        self.interface_tab = QWidget()
        interface_layout = QFormLayout(self.interface_tab)
        
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setMinimum(50)
        self.transparency_slider.setMaximum(100)
        self.transparency_slider.setValue(100)
        
        self.language_selector = QComboBox()
        self.language_selector.addItems(['English', 'Українська'])
        
        self.theme_selector = QComboBox()
        self.theme_selector.addItems([self.translate(theme_key) for theme_key in themes.keys()])
        
        interface_layout.addRow(QLabel(self.translate('transparency')), self.transparency_slider)
        interface_layout.addRow(QLabel(self.translate('language')), self.language_selector)
        interface_layout.addRow(QLabel(self.translate('theme')), self.theme_selector)
        
        self.tabs.addTab(self.interface_tab, self.translate('interface'))

        # Bot tab
        self.bot_tab = QWidget()
        bot_layout = QFormLayout(self.bot_tab)
        
        self.bot_token_input = QLineEdit()
        self.bot_api_id_input = QLineEdit()
        self.bot_api_hash_input = QLineEdit()
        self.bot_status_label = QLabel("")
        
        # Add bot check button
        self.check_bot_button = QPushButton(self.translate('check_bot_connection'))
        self.check_bot_button.clicked.connect(self.check_bot_connection)
        
        bot_layout.addRow(QLabel(self.translate('bot_token')), self.bot_token_input)
        bot_layout.addRow(QLabel("Bot API ID:"), self.bot_api_id_input)
        bot_layout.addRow(QLabel("Bot API Hash:"), self.bot_api_hash_input)
        bot_layout.addRow("", self.check_bot_button)  # Add check button
        bot_layout.addRow(self.translate('status'), self.bot_status_label)
        
        self.tabs.addTab(self.bot_tab, self.translate('bot_settings'))

    # ... rest of existing ConfigGUI methods remain unchanged ...

    def setup_buttons(self, layout):
        """Setup bottom buttons with compact layout"""
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create buttons first
        self.save_interface_button = QPushButton(self.translate('save_interface_settings'))
        self.save_all_button = QPushButton(self.translate('save_all_settings'))
        self.cancel_button = QPushButton(self.translate('cancel'))
        
        # Set up connections
        self.save_interface_button.clicked.connect(self.save_interface_settings)
        self.save_all_button.clicked.connect(self.save_all_settings)
        self.cancel_button.clicked.connect(self.reject)
        
        # Set compact size for all buttons
        for button in [self.save_interface_button, self.save_all_button, self.cancel_button]:
            button.setFixedHeight(30)  # Smaller button height
            
        # Add to layout
        layout.addWidget(self.save_interface_button)
        layout.addWidget(self.save_all_button)
        layout.addWidget(self.cancel_button)

    def translate(self, key):
        return translations[current_language].get(key, key)

    def init_ui(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.interface_tab = QWidget()
        general_layout = QFormLayout()
        self.api_id_input = QLineEdit()
        self.api_hash_input = QLineEdit()
        self.phone_number_input = QLineEdit()
        general_layout.addRow(QLabel("API ID:"), self.api_id_input)
        general_layout.addRow(QLabel("API Hash:"), self.api_hash_input)
        general_layout.addRow(QLabel(self.translate('phone_number')), self.phone_number_input)
        self.db_host_input = QLineEdit()
        self.db_port_input = QLineEdit()  # Add port input
        self.db_user_input = QLineEdit()
        self.db_password_input = QLineEdit()
        self.db_name_input = QLineEdit()
        general_layout.addRow(QLabel("DB Host:"), self.db_host_input)
        general_layout.addRow(QLabel("DB Port:"), self.db_port_input)  # Add port field
        general_layout.addRow(QLabel("DB User:"), self.db_user_input)
        general_layout.addRow(QLabel("DB Password:"), self.db_password_input)
        general_layout.addRow(QLabel("DB Name:"), self.db_name_input)
        self.general_tab.setLayout(general_layout)
        interface_layout = QFormLayout()
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setMinimum(50)
        self.transparency_slider.setMaximum(100)
        self.transparency_slider.setValue(100)
        self.transparency_slider.valueChanged.connect(self.update_transparency_live)
        interface_layout.addRow(QLabel(self.translate('transparency')), self.transparency_slider)
        self.language_selector = QComboBox()
        self.language_selector.addItems(['English', 'Українська'])
        self.language_selector.setCurrentIndex(0 if current_language == 'en' else 1)
        self.language_selector.currentIndexChanged.connect(self.update_language)
        interface_layout.addRow(QLabel(self.translate('language')), self.language_selector)
        self.theme_selector = QComboBox()
        theme_names = [self.translate(theme_key) for theme_key in themes.keys()]
        self.theme_selector.addItems(theme_names)
        current_theme_index = list(themes.keys()).index(current_theme)
        self.theme_selector.setCurrentIndex(current_theme_index)
        self.theme_selector.currentIndexChanged.connect(self.update_theme)
        interface_layout.addRow(QLabel(self.translate('theme')), self.theme_selector)
        self.interface_tab.setLayout(interface_layout)
        self.tabs.addTab(self.general_tab, self.translate('general'))
        self.tabs.addTab(self.interface_tab, self.translate('interface'))
        layout.addWidget(self.tabs)
        buttons_layout = QHBoxLayout()
        self.save_interface_button = QPushButton(self.translate('save_interface_settings'))
        self.save_interface_button.clicked.connect(self.save_interface_settings)
        self.save_all_button = QPushButton(self.translate('save_all_settings'))
        self.save_all_button.clicked.connect(self.save_all_settings)
        buttons_layout.addWidget(self.save_interface_button)
        buttons_layout.addWidget(self.save_all_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)
        self.apply_theme()
        self.load_existing_settings()

        # Add new widgets to general_layout
        self.limits_label = QLabel(self.translate('limits_level'))
        self.limits_slider = QSlider(Qt.Orientation.Horizontal)
        self.limits_slider.setMinimum(0)
        self.limits_slider.setMaximum(3)  # Changed from 2 to 3
        self.limits_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.limits_slider.setTickInterval(1)
        self.limits_slider.valueChanged.connect(self.update_limits_label)
        
        self.limits_value_label = QLabel()
        self.update_limits_label(self.limits_slider.value())
        
        # Get current limits from config
        current_limits = self.config_manager.get_limits_config()
        preset_name = current_limits.get('preset', 'standard')
        initial_value = {'minimum': 0, 'standard': 1, 'maximum': 2}.get(preset_name, 1)
        self.limits_slider.setValue(initial_value)
        
        general_layout.addRow(self.limits_label, self.limits_slider)
        general_layout.addRow("", self.limits_value_label)

        # Add new Bot tab
        self.bot_tab = QWidget()
        bot_layout = QFormLayout()

        # Bot token input
        self.bot_token_input = QLineEdit()
        bot_config = self.config_manager.get_bot_config()
        self.bot_token_input.setText(bot_config.get('token', ''))
        bot_layout.addRow(QLabel(self.translate('bot_token')), self.bot_token_input)
        
        # Add Bot API ID input
        self.bot_api_id_input = QLineEdit()
        self.bot_api_id_input.setText(str(bot_config.get('api_id', '')))
        bot_layout.addRow(QLabel("Bot API ID:"), self.bot_api_id_input)
        
        # Add Bot API Hash input 
        self.bot_api_hash_input = QLineEdit()
        self.bot_api_hash_input.setText(bot_config.get('api_hash', ''))
        bot_layout.addRow(QLabel("Bot API Hash:"), self.bot_api_hash_input)
        
        # Bot check button
        self.check_bot_button = QPushButton(self.translate('check_bot'))
        self.check_bot_button.clicked.connect(self.check_bot_connection)
        bot_layout.addRow("", self.check_bot_button)
        
        # Bot status indicator
        self.bot_status_label = QLabel("")
        bot_layout.addRow(self.translate('status'), self.bot_status_label)
        
        self.bot_tab.setLayout(bot_layout)
        self.tabs.addTab(self.bot_tab, self.translate('bot_settings'))

    def update_limits_label(self, value):
        """Update limits label with 4 load level descriptions"""
        presets = {
            0: ('minimum', 'Мінімальний (Безпечний режим)'),
            1: ('standard', 'Стандартний (Збалансований)'), 
            2: ('maximum', 'Максимальний (Розширений)'),
            3: ('unlimited', 'Безлімітний (Необмежений)')
        }

        preset_name, display_name = presets[value]
        preset_info = self.config_manager.get_limit_presets()[preset_name]

        if preset_name == 'unlimited':
            info_text = f"""
{display_name}
• Безлімітні запити в годину
• Авто-регулювання затримки
• 4 рівні навантаження (0.25, 0.5, 0.75, 1.0)
• Базова затримка: 2с
• Максимальна затримка: 10с
            """.strip()
        else:
            info_text = f"""
{display_name}
• Max Accounts: {preset_info['max_accounts']}
• Max Groups per Account: {preset_info['max_groups_per_account']}
• Max Messages per Day: {preset_info['max_messages_per_day']}
• Delay: {preset_info['delay_min']}-{preset_info['delay_max']}s
            """.strip()

        self.limits_value_label.setText(info_text)

    def apply_theme(self):
        """Apply theme to dialog window"""
        theme = themes[current_theme]
        self.setStyleSheet(get_complete_dialog_style(theme))

    def load_existing_settings(self):
        telegram_config = self.config_manager.get_telegram_config()
        self.api_id_input.setText(str(telegram_config.get('api_id', '')))
        self.api_hash_input.setText(telegram_config.get('api_hash', ''))
        self.phone_number_input.setText(telegram_config.get('phone_number', ''))
        database_config = self.config_manager.get_database_config()
        self.db_host_input.setText(database_config.get('host', ''))
        self.db_port_input.setText(str(database_config.get('port', '3306')))  # Add port loading
        self.db_user_input.setText(database_config.get('user', ''))
        self.db_password_input.setText(database_config.get('password', ''))
        self.db_name_input.setText(database_config.get('database', ''))
        interface_config = self.config_manager.get_interface_config()
        self.transparency_slider.setValue(interface_config.get('transparency', 100))
        language = interface_config.get('language', 'uk')
        theme = interface_config.get('theme', 'hacker')
        self.language_selector.setCurrentIndex(0 if language == 'en' else 1)
        current_theme_index = list(themes.keys()).index(theme)
        self.theme_selector.setCurrentIndex(current_theme_index)

        # Load bot settings - видалити дублювання і залишити тільки цей блок
        bot_config = self.config_manager.get_bot_config()
        if hasattr(self, 'bot_token_input'):
            self.bot_token_input.setText(bot_config.get('token', ''))
            self.bot_api_id_input.setText(str(bot_config.get('api_id', '')))
            self.bot_api_hash_input.setText(bot_config.get('api_hash', ''))

        # Load and update bot status
        bot_status = self.config_manager.get_bot_status()
        if self.bot_status_label:
            status_text = self.get_formatted_bot_status(bot_status)
            self.bot_status_label.setText(status_text)
            # Set color based on status
            if bot_status['status'] == 'active':
                self.bot_status_label.setStyleSheet("color: green;")
            elif bot_status['status'] == 'error':
                self.bot_status_label.setStyleSheet("color: red;")
            else:
                self.bot_status_label.setStyleSheet("color: gray;")

    def get_formatted_bot_status(self, bot_status: Dict[str, Any]) -> str:
        """Format bot status for display."""
        if not bot_status['is_configured']:
            return self.translate('not_configured')
            
        status_text = []
        status_text.append(f"{self.translate('status')}: {bot_status['status']}")
        
        if bot_status['last_active']:
            status_text.append(f"{self.translate('last_active')}: {bot_status['last_active']}")
            
        if bot_status['created_at']:
            status_text.append(f"{self.translate('created_at')}: {bot_status['created_at']}")
            
        if bot_status.get('errors'):
            status_text.append(f"{self.translate('last_error')}: {bot_status['errors']}")
            
        return "\n".join(status_text)

    def update_transparency_live(self):
        opacity = self.transparency_slider.value() / 100.0
        self.parent().setWindowOpacity(opacity)

    def update_language(self):
        global current_language
        current_language = 'en' if self.language_selector.currentIndex() == 0 else 'uk'
        self.parent().change_language(current_language)
        self.update_translations()
        self.apply_theme()

    def update_theme(self):
        global current_theme
        selected_theme_key = list(themes.keys())[self.theme_selector.currentIndex()]
        current_theme = selected_theme_key
        self.parent().change_theme(current_theme)
        self.apply_theme()

    def update_translations(self):
        self.setWindowTitle(self.translate('settings'))
        self.tabs.setTabText(0, self.translate('general'))
        self.tabs.setTabText(1, self.translate('interface'))
        self.save_interface_button.setText(self.translate('save_interface_settings'))
        self.save_all_button.setText(self.translate('save_all_settings'))

    def translate(self, key):
        return translations[current_language].get(key, key)

    def save_interface_settings(self):
        """Save only interface settings without writing to file"""
        global current_language, current_theme
        current_language = 'en' if self.language_selector.currentIndex() == 0 else 'uk'
        selected_theme_key = list(themes.keys())[self.theme_selector.currentIndex()]
        current_theme = selected_theme_key
        self.config_manager.set_interface_config(
            transparency=self.transparency_slider.value(),
            language=current_language,
            theme=current_theme
        )
        # Remove message box from here - it will be shown in save_all_settings

    def save_all_settings(self):
        """Save all settings and write to file once"""
        api_id = self.api_id_input.text().strip()
        api_hash = self.api_hash_input.text().strip()
        phone_number = self.phone_number_input.text().strip()
        db_host = self.db_host_input.text().strip()
        db_port = self.db_port_input.text().strip() or '3306'  # Add port saving
        db_user = self.db_user_input.text().strip()
        db_password = self.db_password_input.text().strip()
        db_name = self.db_name_input.text().strip()
        
        if not all([api_id, api_hash, phone_number, db_host, db_user, db_password, db_name]):
            QMessageBox.warning(self, self.translate('error'), self.translate('please_fill_all_fields'))
            return
            
        # Save all configurations
        self.config_manager.set_telegram_config(api_id=int(api_id), api_hash=api_hash, phone_number=phone_number)
        self.config_manager.set_database_config(host=db_host, port=int(db_port), user=db_user, password=db_password, database=db_name)
        
        # Save interface settings without showing message
        self.save_interface_settings()  
        
        # Save limits preset with unlimited mode support
        preset_map = {
            0: 'minimum', 
            1: 'standard',
            2: 'maximum',
            3: 'unlimited'  # Add unlimited preset option
        }
        selected_preset = preset_map[self.limits_slider.value()]
        self.config_manager.apply_limit_preset(selected_preset)
        
        # Save bot settings
        if hasattr(self, 'bot_token_input'):
            bot_token = self.bot_token_input.text().strip()
            bot_api_id = self.bot_api_id_input.text().strip()
            bot_api_hash = self.bot_api_hash_input.text().strip()
            
            try:
                bot_api_id = int(bot_api_id) if bot_api_id else None
            except ValueError:
                bot_api_id = None  # Allow saving without API ID
                
            self.config_manager.set_bot_config(
                token=bot_token,
                api_id=bot_api_id,
                api_hash=bot_api_hash
            )
        
        # Save configuration to file and show single confirmation message
        self.config_manager.save_config()
        QMessageBox.information(self, self.translate('settings'), self.translate('settings_saved'))
        self.accept()

    @asyncSlot()
    async def check_bot_connection(self):
        """Test bot connection and update status."""
        try:
            self.check_bot_button.setEnabled(False)
            self.bot_status_label.setText(self.translate('checking_connection'))
            
            bot_token = self.bot_token_input.text().strip()
            bot_api_id = self.bot_api_id_input.text().strip()
            bot_api_hash = self.bot_api_hash_input.text().strip()

            if not all([bot_token, bot_api_id, bot_api_hash]):
                self.bot_status_label.setText(self.translate('please_fill_all_fields'))
                self.bot_status_label.setStyleSheet("color: red;")
                self.config_manager.update_bot_status('error', error='Missing bot credentials')
                return

            try:
                bot_api_id = int(bot_api_id)
            except ValueError:
                self.bot_status_label.setText(self.translate('invalid_api_id'))
                self.bot_status_label.setStyleSheet("color: red;")
                self.config_manager.update_bot_status('error', error='Invalid API ID format')
                return

            # Save current bot config
            self.config_manager.set_bot_config(
                token=bot_token,
                api_id=bot_api_id,
                api_hash=bot_api_hash
            )

            # Test connection using telegram module
            parent = self.parent()
            if parent and hasattr(parent, 'telegram_module'):
                is_connected = await parent.telegram_module.check_bot_status(bot_token)
                
                if is_connected:
                    bot_info = await parent.telegram_module.get_bot_info(bot_token)
                    status_text = f"{self.translate('connected')}: @{bot_info.get('username', 'N/A')}"
                    self.bot_status_label.setText(status_text)
                    self.bot_status_label.setStyleSheet("color: green;")
                    self.config_manager.update_bot_status('active')
                else:
                    self.bot_status_label.setText(self.translate('connection_failed'))
                    self.bot_status_label.setStyleSheet("color: red;")
                    self.config_manager.update_bot_status('error', error='Connection failed')
            else:
                error_msg = self.translate('telegram_module_not_available')
                self.bot_status_label.setText(error_msg)
                self.bot_status_label.setStyleSheet("color: red;")
                self.config_manager.update_bot_status('error', error=error_msg)

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error checking bot connection: {error_msg}")
            self.bot_status_label.setText(f"{self.translate('error')}: {error_msg}")
            self.bot_status_label.setStyleSheet("color: red;")
            self.config_manager.update_bot_status('error', error=error_msg)
        finally:
            self.check_bot_button.setEnabled(True)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def closeEvent(self, event):
        """Handle proper cleanup when closing the dialog"""
        self.reject()
        super().closeEvent(event)


class TrafficLightWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "red"
        self._deleted = False
        self._prev_state = None
        self.setFixedSize(20, 20)

    def set_state(self, state):
        """Set the state of the traffic light only if it has changed."""
        if not self._deleted and not self.isHidden():
            try:
                # Only update if state actually changed
                if state != self._state:
                    self._prev_state = self._state
                    self._state = state
                    self.update()
                    logging.debug(f"Traffic light state changed from {self._prev_state} to {state}")
            except RuntimeError:
                self._deleted = True
                logging.debug("Widget already deleted, ignoring update")

    def closeEvent(self, event):
        """Handle widget cleanup"""
        self._deleted = True
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        color = QColor("grey")
        if self._state == "green":
            color = QColor("#00FF7F")
        elif self._state == "red":
            color = QColor("red")
        elif self._state == "yellow":
            color = QColor("yellow")
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.drawEllipse(0, 0, self.width(), self.height())


class KeywordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.translate('enter_keywords'))
        self.setModal(True)
        self.keywords = None
        self.init_ui()
        self.apply_theme()
        self.setup_checkbox_logic()

    def translate(self, key):
        return translations[current_language].get(key, key)

    def init_ui(self):
        layout = QVBoxLayout()
        self.label = QLabel(self.translate('enter_keywords_for_search'))
        self.input = QLineEdit()
        self.input.setPlaceholderText(self.translate('keywords_example'))
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        self.match_options_group = QGroupBox(self.translate('keyword_matching_options'))
        match_layout = QVBoxLayout()
        self.all_words_checkbox = QCheckBox(self.translate('all_words_must_match'))
        self.at_least_one_checkbox = QCheckBox(self.translate('at_least_one_word'))
        self.at_least_two_checkbox = QCheckBox(self.translate('at_least_two_words'))
        self.at_least_three_checkbox = QCheckBox(self.translate('at_least_three_words'))
        match_layout.addWidget(self.all_words_checkbox)
        match_layout.addWidget(self.at_least_one_checkbox)
        match_layout.addWidget(self.at_least_two_checkbox)
        match_layout.addWidget(self.at_least_three_checkbox)
        self.match_options_group.setLayout(match_layout)
        layout.addWidget(self.match_options_group)
        participants_layout = QHBoxLayout()
        self.min_participants_input = QLineEdit()
        self.max_participants_input = QLineEdit()
        self.min_participants_input.setPlaceholderText(self.translate('minimum_participants'))
        self.max_participants_input.setPlaceholderText(self.translate('maximum_participants'))
        participants_layout.addWidget(QLabel(self.translate('min_participants')))
        participants_layout.addWidget(self.min_participants_input)
        participants_layout.addWidget(QLabel(self.translate('max_participants')))
        participants_layout.addWidget(self.max_participants_input)
        layout.addLayout(participants_layout)
        self.activity_checkbox = QCheckBox(self.translate('only_active_groups'))
        layout.addWidget(self.activity_checkbox)
        self.group_type_selector = QComboBox()
        self.group_type_selector.addItems([
            self.translate('all_types'),
            self.translate('megagroup'),
            self.translate('gigagroup'),
            self.translate('mediagroup')
        ])
        layout.addWidget(QLabel(self.translate('group_type')))
        layout.addWidget(self.group_type_selector)
        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton(self.translate('search'))
        self.cancel_button = QPushButton(self.translate('cancel'))
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        self.setWindowOpacity(0.9)

    def apply_theme(self):
        theme = themes[current_theme]
        background_color = theme['background_color']
        text_color = theme['text_color']
        button_color = theme['button_color']
        button_hover_color = theme['button_hover_color']
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {background_color};
                color: {text_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
            }}
            QLineEdit {{
                background-color: white;
                color: black;
            }}
            QPushButton {{
                background-color: {button_color};
                color: {text_color};
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {button_hover_color};
            }}
        """)

    def setup_checkbox_logic(self):
        self.all_words_checkbox.stateChanged.connect(self.on_all_words_checkbox_changed)
        self.at_least_one_checkbox.stateChanged.connect(self.on_at_least_one_checkbox_changed)
        self.at_least_two_checkbox.stateChanged.connect(self.on_at_least_two_checkbox_changed)
        self.at_least_three_checkbox.stateChanged.connect(self.on_at_least_three_checkbox_changed)

    def on_all_words_checkbox_changed(self, state):
        if self.all_words_checkbox.isChecked():
            self.at_least_one_checkbox.setChecked(False)
            self.at_least_two_checkbox.setChecked(False)
            self.at_least_three_checkbox.setChecked(False)
            self.at_least_one_checkbox.setEnabled(False)
            self.at_least_two_checkbox.setEnabled(False)
            self.at_least_three_checkbox.setEnabled(False)
        else:
            self.at_least_one_checkbox.setEnabled(True)
            self.at_least_two_checkbox.setEnabled(True)
            self.at_least_three_checkbox.setEnabled(True)

    def on_at_least_one_checkbox_changed(self, state):
        if self.at_least_one_checkbox.isChecked():
            self.at_least_two_checkbox.setChecked(True)
            self.at_least_three_checkbox.setChecked(True)
        else:
            self.at_least_two_checkbox.setChecked(False)
            self.at_least_three_checkbox.setChecked(False)

    def on_at_least_two_checkbox_changed(self, state):
        if self.at_least_two_checkbox.isChecked():
            self.at_least_three_checkbox.setChecked(True)
        else:
            self.at_least_three_checkbox.setChecked(False)
            if self.at_least_one_checkbox.isChecked():
                self.at_least_one_checkbox.setChecked(False)

    def on_at_least_three_checkbox_changed(self, state):
        if not self.at_least_three_checkbox.isChecked():
            if self.at_least_two_checkbox.isChecked():
                self.at_least_two_checkbox.setChecked(False)
            if self.at_least_one_checkbox.isChecked():
                self.at_least_one_checkbox.setChecked(False)

    def accept(self):
        self.keywords = self.input.text()
        super().accept()

    async def asyncExec(self):
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def on_accept():
            future.set_result(True)
            self.close()

        def on_reject():
            future.set_result(False)
            self.close()

        self.accepted.connect(on_accept)
        self.rejected.connect(on_reject)
        self.show()

        return await future

    def get_filters(self):
        return {
            'keywords': self.input.text(),
            'match_all_words': self.all_words_checkbox.isChecked(),
            'match_at_least_one': self.at_least_one_checkbox.isChecked(),
            'match_at_least_two': self.at_least_two_checkbox.isChecked(),
            'match_at_least_three': self.at_least_three_checkbox.isChecked(),
            'min_participants': self.min_participants_input.text(),
            'max_participants': self.max_participants_input.text(),
            'only_active': self.activity_checkbox.isChecked(),
            'group_type': self.group_type_selector.currentText()
        }


class GroupsListWidget(QListWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setStyleSheet("""
            QListWidget {
                background-color: rgba(0, 30, 0, 0.4);
                color: white;
                border-radius: 10px;
            }
            QListWidget::item:selected {
                background-color: rgba(0, 30, 0, 0.4);
            }
            QListWidget::item:hover {
                background-color: rgba(0, 30, 0, 0.4);
            }
        """)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def start_blinking(self, index):
        item = self.item(index)
        if item:
            blink_color = QColor("yellow")
            item.setBackground(QBrush(blink_color))
            QTimer.singleShot(500, lambda: item.setBackground(QBrush()))
        else:
            logging.warning(f"No item at index {index} to blink.")

    def mark_processed(self, index):
        item = self.item(index)
        if item:
            processed_font_color = QColor(204, 204, 0)
            item.setForeground(QBrush(processed_font_color))
        else:
            logging.warning(f"No item at index {index} to mark as processed.")

    def open_context_menu(self, position):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #3f3f3f;
            }
            QMenu::item:selected {
                background-color: #3f3f3f;
            }
        """)

        paste_action = QAction(self.main_window.translate('paste_link'), self)
        edit_action = QAction(self.main_window.translate('edit'), self)
        delete_action = QAction(self.main_window.translate('delete'), self)
        add_action = QAction(self.main_window.translate('add_group'), self)

        paste_action.triggered.connect(self.main_window.paste_link_from_clipboard)
        edit_action.triggered.connect(self.edit_selected_item)
        delete_action.triggered.connect(self.delete_selected_item)
        add_action.triggered.connect(self.main_window.add_group_manually)

        menu.addAction(add_action)
        menu.addAction(paste_action)

        if self.selectedItems():
            menu.addAction(edit_action)
            menu.addAction(delete_action)

        menu.exec(self.viewport().mapToGlobal(position))

    def edit_selected_item(self):
        selected_items = self.selectedItems()
        if selected_items:
            self.main_window.edit_group_link(selected_items[0])

    def delete_selected_item(self):
        selected_items = self.selectedItems()
        if selected_items:
            for item in selected_items:
                index = self.row(item)
                self.takeItem(index)
                if 0 <= index < len(self.main_window.groups_list):
                    del self.main_window.groups_list[index]
            self.main_window.groups_status_label.setText(
                f"{self.main_window.translate('groups_found')}: {len(self.main_window.groups_list)}"
            )

    def start_processing(self, index):
        item = self.item(index)
        if item:
            theme = themes[current_theme]
            highlight_color = QColor(theme.get('processing_highlight_color', '#FFFF00'))
            item.setBackground(QBrush(highlight_color))
        else:
            logging.warning(f"No item at index {index} to highlight.")

    def finish_processing(self, index):
        item = self.item(index)
        if item:
            theme = themes[current_theme]
            processed_text_color = QColor(theme.get('processed_text_color', '#808080'))
            item.setForeground(QBrush(processed_text_color))
            item.setBackground(QBrush())
        else:
            logging.warning(f"No item at index {index} to mark as processed.")


def telegram_activity_indicator(func):
    async def wrapper(self, *args, **kwargs):
        if self.tg_connected:
            self.tg_light.set_state("yellow")
        result = await func(self, *args, **kwargs)
        if self.tg_connected:
            self.tg_light.set_state("green")
        return result
    return wrapper


def database_activity_indicator(func):
    async def wrapper(self, *args, **kwargs):
        if self.db_connected:
            self.db_light.set_state("yellow")
        result = await func(self, *args, **kwargs)
        if self.db_connected:
            self.db_light.set_state("green")
        return result
    return wrapper


class MainWindow(QMainWindow):
    def __init__(self, db_module, telegram_module, db_connected, tg_connected, config_manager):
        super().__init__()
        self.db_module = db_module
        self.telegram_module = telegram_module
        self.db_connected = db_connected
        self.tg_connected = tg_connected
        self.config_manager = config_manager

        # Initialize as None for now
        self.connect_lock = None
        self._pending_tasks = set()

        self.file_processor = FileProcessor()
        self.setAcceptDrops(True)  # Enable file drag and drop

        # До��айте лічильник акаунті��
        self.accounts_count = 0

        # Add bot connection state
        self.bot_connected = False
        
        # Add bot traffic light attribute
        self.bot_light = TrafficLightWidget(self)
        
        self.init_ui()
        # Schedule async initialization
        QTimer.singleShot(0, self.start_async_tasks)

        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_connections)
        self.check_timer.start(5000)  # Проверяем соединения каждые 5 секунд

        # Add task management
        self._active_tasks = set()
        self._task_lock = asyncio.Lock()
        self._check_lock = asyncio.Lock()
        self.connection_check_timer = QTimer()
        self.connection_check_timer.timeout.connect(lambda: self._schedule_check())
        self.connection_check_timer.start(5000)  # Check every 5 seconds

    def init_ui(self):
        # Initialize fetch_participants_action first
        self.fetch_participants_action = QAction(self.translate('fetch_participants'), self)
        self.fetch_participants_action.triggered.connect(self.on_fetch_participants)
        
        # Initialize group context menu
        self.group_context_menu = QMenu(self)
        self.group_context_menu.addAction(self.fetch_participants_action)

        # Rest of initialization
        self.db_light = TrafficLightWidget(self)
        self.tg_light = TrafficLightWidget(self)
        
        # ... rest of existing init_ui code ...

        self.db_light = TrafficLightWidget(self)
        self.tg_light = TrafficLightWidget(self)

        self.setWindowTitle(self.translate('control_interface'))
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.setAcceptDrops(True)

        self.is_paused_accounts = False
        self.stop_flag_accounts = False
        self.is_paused_groups = False
        self.stop_flag_groups = False

        self.connection = None

        self.max_groups = 10

        self.groups_list = []
        self.accounts_list = []

        self._is_dragging = False
        self._drag_position = QPoint()

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        self.top_bar = TopBar(self)

        self.add_dynamic_widgets_to_top_bar()

        info_layout = QHBoxLayout()

        groups_layout = QVBoxLayout()
        self.groups_list_widget = GroupsListWidget(main_window=self)
        self.groups_list_widget.setStyleSheet("background-color: rgba(0, 30, 0, 0.4); color: white; border-radius: 10px;")

        self.groups_status_label = QLabel()
        self.groups_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.groups_status_label.setFont(QFont("Arial", 12))

        self.progress_bar_groups = QProgressBar()
        self.progress_bar_groups.setFixedHeight(25)
        self.progress_bar_groups.setTextVisible(False)
        self.progress_bar_groups.setVisible(False)

        self.smart_search_button = QPushButton(self.translate('smart_search'))
        self.smart_search_button.clicked.connect(self.open_keyword_dialog)

        self.pause_button_groups = QPushButton(self.translate('pause'))
        self.pause_button_groups.clicked.connect(self.pause_groups_process)

        self.stop_button_groups = QPushButton(self.translate('stop'))
        self.stop_button_groups.clicked.connect(self.stop_groups_process)

        self.pause_button_groups.setVisible(False)
        self.stop_button_groups.setVisible(False)

        groups_control_layout = QHBoxLayout()
        groups_control_layout.addWidget(self.smart_search_button)
        groups_control_layout.addWidget(self.progress_bar_groups)
        groups_control_layout.addWidget(self.pause_button_groups)
        groups_control_layout.addWidget(self.stop_button_groups)

        groups_layout.addWidget(self.groups_status_label)
        groups_layout.addWidget(self.groups_list_widget)
        groups_layout.addLayout(groups_control_layout)

        accounts_layout = QVBoxLayout()

        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(5)
        self.accounts_table.setHorizontalHeaderLabels([
            self.translate('id'),
            self.translate('first_name'),
            self.translate('last_name'),
            self.translate('username'),
            self.translate('phone')
        ])
        self.accounts_table.verticalHeader().setVisible(False)

        self.accounts_scroll_area = QScrollArea()
        self.accounts_scroll_area.setWidget(self.accounts_table)
        self.accounts_scroll_area.setWidgetResizable(True)
        self.accounts_scroll_area.setStyleSheet("border: none;")

        self.accounts_status_label = QLabel()
        self.accounts_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.accounts_status_label.setFont(QFont("Arial", 12))
        self.accounts_status_label.setText(f"{self.translate('accounts')}: 0")

        self.progress_bar_accounts = QProgressBar()
        self.progress_bar_accounts.setFixedHeight(25)
        self.progress_bar_accounts.setTextVisible(False)
        self.progress_bar_accounts.setVisible(False)

        self.search_accounts_button = QPushButton(self.translate('search_accounts'))
        self.search_accounts_button.clicked.connect(self.search_accounts_in_groups_slot)

        self.pause_button_accounts = QPushButton(self.translate('pause'))
        self.pause_button_accounts.clicked.connect(self.pause_accounts_process)

        self.stop_button_accounts = QPushButton(self.translate('stop'))
        self.stop_button_accounts.clicked.connect(self.stop_accounts_process)

        self.pause_button_accounts.setVisible(False)
        self.stop_button_accounts.setVisible(False)

        accounts_control_layout = QHBoxLayout()
        accounts_control_layout.addWidget(self.search_accounts_button)
        accounts_control_layout.addWidget(self.progress_bar_accounts)
        accounts_control_layout.addWidget(self.pause_button_accounts)
        accounts_control_layout.addWidget(self.stop_button_accounts)

        accounts_layout.addWidget(self.accounts_status_label)
        accounts_layout.addWidget(self.accounts_scroll_area)
        accounts_layout.addLayout(accounts_control_layout)

        info_layout.addLayout(groups_layout)
        info_layout.addLayout(accounts_layout)

        self.status_label = QLabel(self.translate('status_ready'))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.status_label.setFont(QFont("Arial", 14))

        self.main_layout.addWidget(self.top_bar)
        self.main_layout.addLayout(info_layout)
        self.main_layout.addWidget(self.status_label)

        central_widget = QWidget()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        self.apply_theme()
        self.update_translations()
        self.load_interface_settings()

        self.connection_check_timer = QTimer()
        self.connection_check_timer.timeout.connect(self.check_connections)
        self.connection_check_timer.start(60000)

        app = QApplication.instance()
        if (app):
            app.aboutToQuit.connect(lambda: asyncio.create_task(self.handle_shutdown()))

        # Add fetch participants action initialization
        self.fetch_participants_action = QAction(self.translate('fetch_participants'), self)
        self.fetch_participants_action.triggered.connect(self.on_fetch_participants)

        # Initialize group context menu
        self.group_context_menu = QMenu(self)
        self.group_context_menu.addAction(self.fetch_participants_action)
        self.groups_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.groups_list_widget.customContextMenuRequested.connect(self.show_group_context_menu)

    def show_group_context_menu(self, position):
        """Show context menu for group items."""
        if self.groups_list_widget.selectedItems():
            self.group_context_menu.exec(self.groups_list_widget.viewport().mapToGlobal(position))

    @asyncSlot()
    async def start_async_tasks(self):
        """Initialize async components and start initial tasks."""
        try:
            self.connect_lock = asyncio.Lock()
            await self.initial_connection_check()
            
            # Add delay before attempting connection
            await asyncio.sleep(1)
            
            if not self.tg_connected:
                await self.connect_to_telegram()
                
        except Exception as e:
            logging.error(f"Error in start_async_tasks: {e}")
            self.show_error_message(str(e))

    async def initial_connection_check(self):
        """Check initial connections at startup."""
        try:
            if self.telegram_module:
                # First ensure connection
                await self.telegram_module.connect()
                await asyncio.sleep(0.5)  # Small delay after connection
                
                is_connected = await self.telegram_module.is_connected()
                if is_connected:
                    is_authorized = await self.telegram_module.is_user_authorized()
                    self.tg_connected = is_connected and is_authorized
                    self.tg_light.set_state("green" if self.tg_connected else "red")
                else:
                    self.tg_connected = False
                    self.tg_light.set_state("red")

            if self.db_module:
                self.db_connected = await self.db_module.is_connected()
                self.db_light.set_state("green" if self.db_connected else "red")
                
        except Exception as e:
            logging.error(f"Error during initial connection check: {e}")
            self.tg_light.set_state("red")
            self.db_light.set_state("red")
            self.show_error_message(f"Connection check failed: {str(e)}")

    def show_error_message(self, message: str):
        """Shows error message to user."""
        QMessageBox.critical(self, self.translate('error'), message)

    @asyncSlot()
    async def connect_to_telegram(self):
        """Підключення до Telegram з належним блокуванням та обробкою помилок."""
        async with self.connect_lock:
            try:
                await self.telegram_module.connect()
                if not await self.telegram_module.is_user_authorized():
                    await self._handle_telegram_auth()
                else:
                    self.tg_connected = True
                    self.tg_light.set_state("green")
            except Exception as e:
                self.tg_connected = False
                self.tg_light.set_state("red")
                logging.error(f"Error connecting to Telegram: {e}")
                QMessageBox.critical(self, self.translate('error'), str(e))

    async def _handle_telegram_auth(self):
        """Обробка процесу авторизації в Telegram."""
        try:
            await self.telegram_module.send_code_request()
            code_dialog = AuthDialog(
                self.translate('confirmation_code'),
                self.translate('code_from_telegram')
            )
            result = await code_dialog.asyncExec()
            if result:
                code = code_dialog.value
                try:
                    await self.telegram_module.sign_in(code)
                    self.tg_connected = True
                    self.tg_light.set_state("green")
                except errors.SessionPasswordNeededError:
                    password_dialog = AuthDialog(
                        self.translate('password'),
                        self.translate('password')
                    )
                    password_result = await password_dialog.asyncExec()
                    if password_result:
                        password = password_dialog.value
                        await self.telegram_module.sign_in(password=password)
                        self.tg_connected = True
                        self.tg_light.set_state("green")
                    else:
                        raise Exception(self.translate('authorization_cancelled_by_user'))
            else:
                raise Exception(self.translate('authorization_cancelled_by_user'))
        except Exception as e:
            self.tg_connected = False
            self.tg_light.set_state("red")
            logging.error(f"Telegram authorization failed: {e}")
            raise

    def translate(self, key: str) -> str:
        """Перекладає заданий ключ за допомогою поточних мовних налаштувань."""
        return translations[current_language].get(key, key)

    def apply_theme(self):
        """Застосовує поточну тему до головного вікна."""
        theme = themes[current_theme]
        background_color = theme['background_color']
        text_color = theme['text_color']
        button_color = theme['button_color']
        button_hover_color = theme['button_hover_color']

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {background_color};
                color: {text_color};
                border: 1px solid {text_color};
                border-radius: 10px;
            }}
            QWidget#centralWidget {{
                background-color: {background_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: {text_color};
                background-color: transparent;
            }}
            QPushButton {{
                background-color: {button_color};
                color: {text_color};
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
                border: 1px solid {text_color};
            }}
            QPushButton:hover {{
                background-color: {button_hover_color};
            }}
            QProgressBar {{
                border: 2px solid {text_color};
                border-radius: 5px;
                text-align: center;
                background-color: transparent;
            }}
            QProgressBar::chunk {{
                background-color: {button_color};
            }}
            QTableWidget {{
                background-color: rgba(0, 30, 0, 0.4);
                color: {text_color};
                border-radius: 10px;
                border: 1px solid {text_color};
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QListWidget {{
                background-color: rgba(0, 30, 0, 0.4);
                color: {text_color};
                border-radius: 10px;
                border: 1px solid {text_color};
                padding: 5px;
            }}
            QListWidget::item {{
                border-radius: 5px;
                padding: 5px;
            }}
            QListWidget::item:selected {{
                background-color: {button_color};
            }}
        """)

        self.centralWidget().setObjectName("centralWidget")

    def update_translations(self):
        """Оновлює всі переклади в інтерфейсі."""
        self.setWindowTitle(self.translate('control_interface'))
        self.smart_search_button.setText(self.translate('smart_search'))
        self.search_accounts_button.setText(self.translate('search_accounts'))
        self.pause_button_groups.setText(self.translate('pause'))
        self.stop_button_groups.setText(self.translate('stop'))
        self.pause_button_accounts.setText(self.translate('pause'))
        self.stop_button_accounts.setText(self.translate('stop'))
        self.status_label.setText(self.translate('status_ready'))

        headers = [
            self.translate('id'),
            self.translate('first_name'),
            self.translate('last_name'),
            self.translate('username'),
            self.translate('phone')
        ]
        self.accounts_table.setHorizontalHeaderLabels(headers)

        if hasattr(self, 'groups_list'):
            self.groups_status_label.setText(f"{self.translate('groups')} ({len(self.groups_list)}):")

        self.fetch_participants_action.setText(self.translate('fetch_participants'))

        # Он��влення тексту лічильника акаунтів
        self.accounts_status_label.setText(f"{self.translate('accounts')}: {self.accounts_count}")

    def load_interface_settings(self):
        """Завантажує та застосовує налаштування інтерфейсу з конфігурації."""
        interface_config = self.config_manager.get_interface_config()

        opacity = interface_config.get('transparency', 100) / 100.0
        self.setWindowOpacity(opacity)

        language = interface_config.get('language', 'uk')
        self.change_language(language)

        theme = interface_config.get('theme', 'hacker')
        self.change_theme(theme)

    def add_dynamic_widgets_to_top_bar(self):
        """��одає індикатори підключення та кнопки до верхньої панелі."""
        lights_container = QWidget()
        lights_layout = QHBoxLayout()
        lights_layout.setContentsMargins(0, 0, 0, 0)
        lights_layout.setSpacing(5)

        # DB indicator
        db_container = QWidget()
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("DB:"))
        db_layout.addWidget(self.db_light)
        db_container.setLayout(db_layout)

        # TG indicator
        tg_container = QWidget()
        tg_layout = QHBoxLayout()
        tg_layout.addWidget(QLabel("TG:"))
        tg_layout.addWidget(self.tg_light)
        tg_container.setLayout(tg_layout)
        
        # Bot indicator
        bot_container = QWidget()
        bot_layout = QHBoxLayout()
        bot_layout.addWidget(QLabel("BOT:"))
        bot_layout.addWidget(self.bot_light)
        bot_container.setLayout(bot_layout)

        # Add all indicators to layout
        lights_layout.addWidget(db_container)
        lights_layout.addWidget(tg_container)
        lights_layout.addWidget(bot_container)
        lights_container.setLayout(lights_layout)

        self.top_bar.dynamic_widgets_layout.addWidget(lights_container)

        # Settings button
        settings_button = QPushButton(self.translate('settings'))
        settings_button.clicked.connect(self.open_settings)
        self.top_bar.dynamic_widgets_layout.addWidget(settings_button)

    def open_settings(self):
        """Відкриває вікно налаштувань."""
        config_gui = ConfigGUI(config_manager=self.config_manager, parent=self)
        config_gui.exec()
        self.load_interface_settings()

    @asyncSlot()
    async def open_keyword_dialog(self):
        """Відкриває діалогове вікно к��ючових слів та ініціює розумний пошук."""
        dialog = KeywordDialog(parent=self)
        result = await dialog.asyncExec()
        if result:
            filters = dialog.get_filters()
            self.pause_button_groups.setVisible(True)
            self.stop_button_groups.setVisible(True)
            self.is_paused_groups = False
            self.stop_flag_groups = False
            await self.perform_smart_search(filters)

    @asyncSlot()
    async def perform_smart_search(self, filters):
        """Execute smart search with improved task management."""
        if not hasattr(self, '_search_lock'):
            self._search_lock = asyncio.Lock()
            
        if (self._search_lock.locked()):
            logging.warning("Search already in progress")
            return
            
        try:
            async with self._search_lock:
                self.status_label.setText(self.translate('searching_groups'))
                self.groups_list_widget.clear()
                self.groups_list = []

                keywords = filters['keywords']
                if not keywords:
                    QMessageBox.warning(self, self.translate('warning'), self.translate('no_keywords_provided'))
                    self.status_label.setText(self.translate('status_ready'))
                    return

                keyword_list = [word.strip() for word in keywords.split(',') if word.strip()]
                match_all_words = filters['match_all_words']
                
                # Safely parse participant limits
                try:
                    min_participants = int(filters['min_participants']) if filters['min_participants'].strip() else 0
                    max_participants = int(filters['max_participants']) if filters['max_participants'].strip() else None
                except ValueError:
                    QMessageBox.warning(self, self.translate('warning'), "Invalid participant number format")
                    return
                    
                group_type = filters['group_type']

                self.progress_bar_groups.setVisible(True)
                self.progress_bar_groups.setRange(0, 0)

                try:
                    results = await asyncio.wait_for(
                        self.telegram_module.search_groups(
                            keywords=keyword_list,
                            match_all=match_all_words,
                            min_participants=min_participants,
                            max_participants=max_participants,
                            group_type=group_type,
                            stop_flag=lambda: self.stop_flag_groups,
                            pause_flag=lambda: self.is_paused_groups
                        ),
                        timeout=300.0  # 5 minute timeout
                    )
                except asyncio.TimeoutError:
                    QMessageBox.warning(self, self.translate('warning'), "Search operation timed out")
                    return
                finally:
                    self.progress_bar_groups.setVisible(False)
                    self.pause_button_groups.setVisible(False)
                    self.stop_button_groups.setVisible(False)

                if results:
                    for group in results:
                        self.groups_list.append(group)
                        item = QListWidgetItem(f"{group.title} ({group.participants_count} {self.translate('members')})")
                        self.groups_list_widget.addItem(item)
                    self.groups_status_label.setText(f"{self.translate('groups_found')}: {len(self.groups_list)}")
                    self.status_label.setText(self.translate('search_completed'))
                else:
                    self.status_label.setText(self.translate('no_groups_found'))
                    QMessageBox.information(self, self.translate('info'), self.translate('no_groups_found'))

        except Exception as e:
            logging.error(f"Error during smart search: {e}")
            QMessageBox.critical(self, self.translate('error'), str(e))
            self.status_label.setText(self.translate('error_occurred'))
        finally:
            self.progress_bar_groups.setVisible(False)
            self.pause_button_groups.setVisible(False)
            self.stop_button_groups.setVisible(False)

    @pyqtSlot()
    def pause_groups_process(self):
        """Призупиняє або відновлює процес пошуку груп."""
        self.is_paused_groups = not self.is_paused_groups
        self.pause_button_groups.setText(
            self.translate('resume') if self.is_paused_groups else self.translate('pause')
        )

    @pyqtSlot()
    def stop_groups_process(self):
        """Зупиняє процес пошуку груп."""
        self.stop_flag_groups = True
        self.pause_button_groups.setVisible(False)
        self.stop_button_groups.setVisible(False)
        self.status_label.setText(self.translate('process_stopped'))

    @asyncSlot()
    async def search_accounts_in_groups_slot(self):
        """Розпочи��ає пошук акаунтів у г��упах."""
        self.search_accounts_button.setVisible(False)
        self.progress_bar_accounts.setVisible(True)
        self.pause_button_accounts.setVisible(True)
        self.stop_button_accounts.setVisible(True)

        await self.search_accounts_in_groups(auto_start=False)

    @asyncSlot()
    async def search_accounts_in_groups(self, auto_start=False):
        """Шукає акаунти у вибраних групах."""
        if not self.groups_list:
            QMessageBox.warning(self, self.translate('warning'), self.translate('load_groups_first'))
            return

        if not self.tg_connected:
            QMessageBox.warning(self, self.translate('error'), self.translate('no_connection_telegram'))
            return

        try:
            self.is_paused_accounts = False
            self.stop_flag_accounts = False

            self.progress_bar_accounts.setVisible(True)
            self.pause_button_accounts.setVisible(True)
            self.stop_button_accounts.setVisible(True)
            self.search_accounts_button.setVisible(False)

            total_groups = len(self.groups_list)
            self.progress_bar_accounts.setMaximum(total_groups)
            self.progress_bar_accounts.setValue(0)

            # Скидання лічильника перед новим пошуком
            self.accounts_count = 0
            self.accounts_status_label.setText(f"{self.translate('accounts')}: 0")
            
            # Очищення таблиці акаунтів
            self.accounts_table.setRowCount(0)

            # Get current limits config
            limits_config = self.config_manager.get_limits_config()
            max_accounts = limits_config.get('max_accounts', 5)  # Default to 5 if not set

            # Check if we've already reached the limit
            if self.accounts_count >= max_accounts:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    f"Досягнуто ліміту максимальної кількості акаунтів ({max_accounts})"
                )
                return

            for index, group in enumerate(self.groups_list):
                if self.stop_flag_accounts:
                    break

                while self.is_paused_accounts:
                    await asyncio.sleep(0.1)
                    if self.stop_flag_accounts:
                        break

                list_index = index  # Since we're iterating through groups_list directly
                self.groups_list_widget.start_processing(list_index)

                try:
                    self.status_label.setText(f"{self.translate('processing_group')}: {group.title}")

                    group_entity = await self.telegram_module.get_entity(group)
                    if not group_entity:
                        continue

                    can_access = await self.telegram_module.can_access_participants(group_entity)
                    if not can_access:
                        self.status_label.setText(
                            f"{self.translate('cannot_access_group')} '{group_entity.title}' "
                            f"{self.translate('due_to_insufficient_permissions')}"
                        )
                        continue

                    participants = await self.telegram_module.get_participants(group_entity)
                    total_participants = len(participants)
                    
                    # Оновлюємо статус для відображення прогресу обробки учасників
                    for participant_index, participant in enumerate(participants):
                        if self.stop_flag_accounts:
                            break

                        while self.is_paused_accounts:
                            await asyncio.sleep(0.1)
                            if self.stop_flag_accounts:
                                break

                        # Check account limit before adding new account
                        if self.accounts_count >= max_accounts:
                            self.status_label.setText(
                                f"Досягнуто ліміту акаунтів ({max_accounts}). Процес зупинено."
                            )
                            return

                        self.status_label.setText(
                            f"{self.translate('processing_group')}: {group.title} "
                            f"({participant_index + 1}/{total_participants})"
                        )

                        user_info = {
                            'id': participant.id,
                            'first_name': participant.first_name or '',
                            'last_name': participant.last_name or '',
                            'username': participant.username or '',
                            'phone': participant.phone or '',
                            'is_bot': participant.bot
                        }

                        await self.db_module.upsert_user(user_info)

                        existing_ids = set(
                            self.accounts_table.item(row, 0).text()
                            for row in range(self.accounts_table.rowCount())
                            if self.accounts_table.item(row, 0)
                        )

                        if str(user_info['id']) not in existing_ids:
                            # Only add if we haven't reached the limit
                            if self.accounts_count < max_accounts:
                                await self.db_module.upsert_user(user_info)
                                self.add_account_to_table(user_info)
                            else:
                                break

                        await asyncio.sleep(0.01)  # Невелика затримка для обробки подій GUI

                except Exception as e:
                    logging.error(f"Error processing group {group.title}: {e}")
                    continue
                finally:
                    self.groups_list_widget.finish_processing(list_index)

                self.progress_bar_accounts.setValue(index + 1)
                await asyncio.sleep(0.1)

            self.status_label.setText(self.translate('search_completed'))

        except Exception as e:
            logging.error(f"Error during account search: {e}")
            QMessageBox.critical(self, self.translate('error'), str(e))
        finally:
            self.progress_bar_accounts.setVisible(False)
            self.pause_button_accounts.setVisible(False)
            self.stop_button_accounts.setVisible(False)
            self.search_accounts_button.setVisible(True)
            self.pause_button_accounts.setText(self.translate('pause'))

    def add_account_to_table(self, user_info):
        """Додає інформацію про користувача до таблиці."""
        row_position = self.accounts_table.rowCount()
        self.accounts_table.insertRow(row_position)
        self.accounts_table.setItem(row_position, 0, QTableWidgetItem(str(user_info['id'])))
        self.accounts_table.setItem(row_position, 1, QTableWidgetItem(user_info['first_name']))
        self.accounts_table.setItem(row_position, 2, QTableWidgetItem(user_info['last_name']))
        self.accounts_table.setItem(row_position, 3, QTableWidgetItem(user_info['username']))
        self.accounts_table.setItem(row_position, 4, QTableWidgetItem(user_info['phone']))
        
        # Оновлення лічильника та відображення
        self.accounts_count += 1
        self.accounts_status_label.setText(f"{self.translate('accounts')}: {self.accounts_count}")
        
        # Автоматична прокрутка до останнього доданого рядка
        self.accounts_table.scrollToItem(
            self.accounts_table.item(row_position, 0),
            QAbstractItemView.ScrollHint.EnsureVisible
        )

    @pyqtSlot()
    def pause_accounts_process(self):
        """Призупиняє або відновлює процес пошуку акаунтів."""
        self.is_paused_accounts = not self.is_paused_accounts
        self.pause_button_accounts.setText(
            self.translate('resume') if self.is_paused_accounts else self.translate('pause')
        )
        if self.is_paused_accounts:
            self.status_label.setText(self.translate('accounts_process_paused'))
        else:
            self.status_label.setText(self.translate('accounts_process_resumed'))

    @pyqtSlot()
    def stop_accounts_process(self):
        """Зупиняє процес пошуку акаунтів."""
        self.stop_flag_accounts = True
        self.pause_button_accounts.setVisible(False)
        self.stop_button_accounts.setVisible(False)
        self.status_label.setText(self.translate('accounts_process_stopped'))
        self.search_accounts_button.setVisible(True)

    def change_language(self, language: str) -> None:
        """Змінює мову інтерфейсу."""
        global current_language
        current_language = language
        self.update_translations()
        if hasattr(self, 'top_bar'):
            self.top_bar.update_title()
        logging.debug(f"Language changed to {language}")

    def change_theme(self, theme_name: str) -> None:
        """Змінює тему інтер��ейсу."""
        global current_theme
        if (theme_name in themes):
            current_theme = theme_name
            self.apply_theme()
            logging.debug(f"Theme changed to {theme_name}")
        else:
            logging.error(f"Invalid theme name: {theme_name}")
            QMessageBox.warning(
                self,
                self.translate('error'),
                f"Theme '{theme_name}' not found."
            )

    @asyncSlot()
    async def check_connections(self):
        """Safely check connections with proper task management."""
        try:
            if not hasattr(self, '_check_lock'):
                self._check_lock = asyncio.Lock()
                
            if self._check_lock.locked():
                return
                
            async with self._check_lock:
                # Check database connection first
                if self.db_module:
                    self.db_connected = await self.db_module.is_connected()
                    self.db_light.set_state("green" if self.db_connected else "red")

                # Then check telegram account connection
                if self.telegram_module:
                    try:
                        is_connected = await self.telegram_module.is_connected()
                        is_authorized = await self.telegram_module.is_user_authorized()
                        self.tg_connected = is_connected and is_authorized
                        self.tg_light.set_state("green" if self.tg_connected else "red")
                        
                        # Only check bot if account is connected
                        if self.tg_connected and self.telegram_module.bot_manager:
                            bot_status = await self.telegram_module.bot_manager.check_status()
                            was_connected = self.bot_connected
                            self.bot_connected = bot_status['ok']
                            
                            if self.bot_connected:
                                if not was_connected:
                                    logging.info("Bot connection established")
                                self.bot_light.set_state("green")
                            else:
                                if was_connected:
                                    logging.warning(f"Bot disconnected: {bot_status.get('details')}")
                                self.bot_light.set_state("red")
                                
                            # Проверяе�� есть ли рассинхронизация между статусами
                            config_status = self.config_manager.get_bot_status()
                            if config_status['status'] == 'active' and not self.bot_connected:
                                logging.warning("Status mismatch: config shows active but bot is disconnected")
                                self.config_manager.update_bot_status('error', 'Connection lost')
                        else:
                            self.bot_connected = False
                            self.bot_light.set_state("red")
                            
                    except Exception as e:
                        logging.error(f"Connection check error: {e}")
                        self.tg_connected = False
                        self.tg_light.set_state("red")
                        self.bot_connected = False 
                        self.bot_light.set_state("red")

        except Exception as e:
            logging.error(f"Error checking connections: {e}")
            self.db_light.set_state("red")
            self.tg_light.set_state("red")
            self.bot_light.set_state("red")

    def closeEvent(self, event):
        """Обробляє подію закриття вікна."""
        self._widgets_active = False
        asyncio.create_task(self.handle_shutdown())
        event.accept()

    async def handle_shutdown(self):
        """Обробляє завершення роботи додатку."""
        try:
            self.stop_flag_groups = True
            self.stop_flag_groups = True
            self.status_label.setText(f"{self.translate('status')}: {self.translate('process_stopped')}")

            for task in list(self._pending_tasks):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logging.error(f"Error cancelling task: {e}")

            if self.telegram_module:
                if await self.telegram_module.is_connected():
                    await self.telegram_module.disconnect()
                    logging.info(self.translate('disconnected_from_telegram'))

            if self.db_module:
                await self.db_module.disconnect()
                logging.info(self.translate('disconnected_from_db'))
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")

    def _track_task(self, task):
        """Відстежує асинхронні задачі для забезпечення нале��ного завершення."""
        self._pending_tasks.add(task)
        task.add_done_callback(self._remove_task)

    def _remove_task(self, task):
        """Видаляє завершені задачі з відстеження."""
        self._pending_tasks.discard(task)
        try:
            task.result()
        except (asyncio.CancelledError, Exception) as e:
            if not isinstance(e, asyncio.CancelledError):
                logging.error(f"Task failed with error: {e}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                self.handle_dropped_file(file_path)
        event.acceptProposedAction()

    def handle_dropped_file(self, file_path):
        """Process dropped file and extract Telegram links."""
        try:
            links = self.file_processor.extract_links_from_file(file_path)
            if links:
                asyncio.create_task(self.add_links_to_group_list(links))
                QMessageBox.information(
                    self, 
                    self.translate('info'), 
                    f"{len(links)} {self.translate('links_extracted')} {os.path.basename(file_path)}."
                )
            else:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('no_links_found')
                )
        except Exception as e:
            logging.error(f"Error handling dropped file: {e}")
            QMessageBox.critical(self, self.translate('error'), str(e))

    @asyncSlot()
    async def add_links_to_group_list(self, links):
        """Add extracted links to the groups list."""
        for link in links:
            try:
                group = await self.telegram_module.get_entity(link)
                if group and isinstance(group, Channel):
                    if group not in self.groups_list:
                        self.groups_list.append(group)
                        item = QListWidgetItem(
                            f"{group.title} ({group.participants_count} {self.translate('members')})"
                        )
                        self.groups_list_widget.addItem(item)
                else:
                    continue
            except Exception as e:
                logging.error(f"Error adding group from link {link}: {e}")
                continue
        self.groups_status_label.setText(f"{self.translate('groups_found')}: {len(self.groups_list)}")

    @pyqtSlot()
    def paste_link_from_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if (text):
            links = re.findall(self.file_processor.TELEGRAM_LINK_PATTERN, text)
            if (links):
                asyncio.create_task(self.add_links_to_group_list(links))
            else:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('invalid_telegram_link')
                )

    def edit_group_link(self, item):
        index = self.groups_list_widget.row(item)
        group = self.groups_list[index]
        text, ok = QInputDialog.getText(
            self,
            self.translate('edit_link'),
            self.translate('enter_new_link'),
            QLineEdit.EchoMode.Normal,
            group.username or ''
        )
        if ok and text:
            links = re.findall(self.file_processor.TELEGRAM_LINK_PATTERN, text)
            if links:  # Fixed extra parenthesis
                asyncio.create_task(self.update_group_link(index, text))
            else:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('invalid_telegram_link')
                )

    @asyncSlot()
    async def update_group_link(self, index, new_link):
        try:
            group = await self.telegram_module.get_entity(new_link)
            if group and isinstance(group, Channel):
                self.groups_list[index] = group
                self.groups_list_widget.item(index).setText(
                    f"{group.title} ({group.participants_count} {self.translate('members')})"
                )
            else:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('invalid_telegram_link')
                )
        except Exception as e:
            logging.error(f"Error updating group link: {e}")
            QMessageBox.critical(self, self.translate('error'), str(e))

    def add_group_manually(self):
        text, ok = QInputDialog.getText(
            self,
            self.translate('add_group'),
            self.translate('enter_group_link'),
            QLineEdit.EchoMode.Normal
        )
        if ok and text:
            links = re.findall(self.file_processor.TELEGRAM_LINK_PATTERN, text)
            if links:  # Fixed extra parenthesis
                asyncio.create_task(self.add_links_to_group_list(links))
            else:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('invalid_telegram_link')
                )

    @asyncSlot()
    @telegram_activity_indicator
    async def fetch_and_store_participants(self, group_link: str):
        """Fetch participants from a group and store them in the database."""
        participants = await self.telegram_module.get_participants(group_link)
        group_entity = await self.telegram_module.client.get_entity(group_link)
        group_id = group_entity.id

        for user in participants:
            participant_info = {
                'user_id': user.id,
                'group_id': group_id,                'first_name': user.first_name,                'last_name': user.last_name,                'username': user.username,                'phone': user.phone,                'is_bot': user.bot,
            }
            await self.db_module.upsert_participant(participant_info)

    def add_group_context_menu_actions(self):
        """Add context menu actions for group items."""
        # ...existing code...

        fetch_participants_action = QAction(self.translate('fetch_participants'), self)
        fetch_participants_action.triggered.connect(self.on_fetch_participants)

        self.group_context_menu.addAction(fetch_participants_action)

    @asyncSlot()
    @telegram_activity_indicator
    async def on_fetch_participants(self):
        """Handle fetch participants action."""
        selected_items = self.groups_list_widget.selectedItems()
        if selected_items:
            group_item = selected_items[0]
            group_link = group_item.text()
            await self.fetch_and_store_participants(group_link)
            QMessageBox.information(self, self.translate('success'), self.translate('participants_fetched'))

    def update_translations(self):
        """Update translations for UI elements."""
        # ...existing code...
        self.fetch_participants_action.setText(self.translate('fetch_participants'))
        self.accounts_status_label.setText(f"{self.translate('accounts')}: {self.accounts_count}")

    @asyncSlot()
    async def check_bot_status(self):
        """Manually check bot status and show detailed information."""
        try:
            # Get bot config using the correct method
            bot_config = self.config_manager.get_bot_config()
            bot_token = bot_config.get('token')
            
            if not bot_token:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('bot_token_not_configured')
                )
                return

            # Check if telegram is connected first
            if not self.tg_connected:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('connect_telegram_first')
                )
                return

            is_connected = await self.telegram_module.check_bot_status(bot_token)
            
            if is_connected:
                bot_info = await self.telegram_module.get_bot_info(bot_token)
                status_text = f"""
{self.translate('bot_status')}: {self.translate('active')}
{self.translate('bot_name')}: {bot_info.get('first_name', 'N/A')}
{self.translate('bot_username')}: @{bot_info.get('username', 'N/A')}
{self.translate('created_at')}: {bot_config.get('created_at', 'N/A')}
                """.strip()
                
                QMessageBox.information(
                    self,
                    self.translate('bot_status'),
                    status_text
                )
                
                # Update bot indicator
                self.bot_connected = True
                self.bot_light.set_state("green")
            else:
                QMessageBox.warning(
                    self,
                    self.translate('warning'),
                    self.translate('bot_not_responding')
                )
                self.bot_connected = False
                self.bot_light.set_state("red")

        except Exception as e:
            logging.error(f"Error checking bot status: {e}")
            QMessageBox.critical(
                self,
                self.translate('error'),
                f"{self.translate('bot_check_error')}: {str(e)}"
            )
            self.bot_connected = False
            self.bot_light.set_state("red")

    def setup_authentication(self):
        """Настройка аутентификации пользователя."""
        # Исправленный вызов AuthDialog с необходимыми аргу��ентами
        self.auth_dialog = AuthDialog(
            title="Авторизация",
            label="Пожалуйста, введите свои учетные данные:",
            parent=self
        )
        if self.auth_dialog.exec() == QDialog.DialogCode.Accepted:
            # Обработка успешной аутентификации
            pass
        else:
            # Обработка отмены аутент��фикации
            sys.exit(0)

    def restart_session(self):
        """Handle session restart."""
        asyncio.create_task(self.telegram_module.restart_session())

    async def _run_task(self, coro):
        """Safely run a coroutine as a task."""
        try:
            task = asyncio.create_task(coro)
            self._active_tasks.add(task)
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Task error: {e}")
        finally:
            self._active_tasks.discard(task)

    def _schedule_check(self):
        """Schedule connection check without conflicts."""
        if not self._check_lock.locked():
            asyncio.create_task(self._safe_check_connections())

    async def _safe_check_connections(self):
        """Thread-safe connection check."""
        try:
            async with self._check_lock:
                if self.telegram_module:
                    is_connected = await self.telegram_module.is_connected()
                    is_authorized = await self.telegram_module.is_user_authorized()
                    self.tg_connected = is_connected and is_authorized
                    self.tg_light.set_state("green" if self.tg_connected else "red")

                if self.db_module:
                    self.db_connected = await self.db_module.is_connected()
                    self.db_light.set_state("green" if self.db_connected else "red")
                    
                # Check bot status if telegram is connected
                if self.tg_connected and self.telegram_module.bot_manager:
                    bot_status = await self.telegram_module.bot_manager.check_status()
                    self.bot_connected = bot_status['ok']
                    self.bot_light.set_state("green" if self.bot_connected else "red")
                else:
                    self.bot_connected = False
                    self.bot_light.set_state("red")
        except Exception as e:
            logging.error(f"Connection check failed: {e}")
            self.tg_light.set_state("red")
            self.db_light.set_state("red")
            self.bot_light.set_state("red")

    @asyncSlot()
    async def start_async_tasks(self):
        """Initialize async components safely."""
        try:
            async with self._task_lock:
                # Initial connection check
                await self._safe_check_connections()
                
                # Connect to telegram if needed
                if not self.tg_connected and self.telegram_module:
                    await self._run_task(self.connect_to_telegram())
                    
        except Exception as e:
            logging.error(f"Error in start_async_tasks: {e}")
            self.show_error_message(str(e))

    async def initial_connection_check(self):
        """Perform initial connection check."""
        await self._safe_check_connections()

    # Replace the old check_connections method
    @asyncSlot()
    async def check_connections(self):
        """Regular connection status check."""
        await self._safe_check_connections()

    async def connect_to_telegram(self):
        """Connect to Telegram with proper error handling."""
        try:
            async with self._task_lock:
                if not self.telegram_module:
                    return
                    
                await self.telegram_module.connect()
                if not await self.telegram_module.is_user_authorized():
                    await self._handle_telegram_auth()
                else:
                    self.tg_connected = True
                    self.tg_light.set_state("green")
        except Exception as e:
            self.tg_connected = False
            self.tg_light.set_state("red")
            logging.error(f"Telegram connection error: {e}")
            raise

    def closeEvent(self, event):
        """Handle window close with proper cleanup."""
        # Cancel any running tasks
        for task in self._active_tasks:
            task.cancel()
        
        # Stop the check timer
        self.connection_check_timer.stop()
        
        # Proceed with normal cleanup
        self._widgets_active = False
        asyncio.create_task(self.handle_shutdown())
        event.accept()