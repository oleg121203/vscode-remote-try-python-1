# modules/themes.py

themes = {
    'hacker': {
        'background_color': '#0C0C0C',
        'text_color': '#00FF41',
        'button_color': '#1A1A1A',
        'button_hover_color': '#2A2A2A',
        'tab_selected_color': '#1E1E1E',
        'tab_unselected_color': '#141414',
        'processing_highlight_color': 'rgba(0, 255, 65, 0.15)',
        'processed_text_color': '#008F11',
        'border_color': '#00FF41',
        'hover_color': 'rgba(0, 255, 65, 0.1)',
        'active_color': 'rgba(0, 255, 65, 0.2)',
        'accent_color': '#00FF41',
        'shadow_color': 'rgba(0, 255, 65, 0.2)',
        'overlay_color': 'rgba(12, 12, 12, 0.95)',
        'success_color': '#00FF41',
        'error_color': '#FF0000',
        'warning_color': '#FFFF00'
    },
    'light': {
        'background_color': '#FFFFFF',
        'text_color': '#2C3E50',
        'button_color': '#ECF0F1',
        'button_hover_color': '#BDC3C7',
        'tab_selected_color': '#E0E6E8',
        'tab_unselected_color': '#F5F6FA',
        'processing_highlight_color': 'rgba(52, 152, 219, 0.15)',
        'processed_text_color': '#7F8C8D',
        'border_color': '#E0E6E8',
        'hover_color': 'rgba(52, 152, 219, 0.1)',
        'active_color': 'rgba(52, 152, 219, 0.2)',
        'accent_color': '#3498DB',
        'shadow_color': 'rgba(44, 62, 80, 0.1)',
        'overlay_color': 'rgba(255, 255, 255, 0.95)',
        'success_color': '#2ECC71',
        'error_color': '#E74C3C',
        'warning_color': '#F1C40F'
    },
    'dark': {
        'background_color': '#1A1B1E',
        'text_color': '#E0E0E0',
        'button_color': '#2C2D30',
        'button_hover_color': '#3A3B3E',
        'tab_selected_color': '#2C2D30',
        'tab_unselected_color': '#1A1B1E',
        'processing_highlight_color': 'rgba(255, 255, 255, 0.1)',
        'processed_text_color': '#808080',
        'border_color': '#2C2D30',
        'hover_color': 'rgba(255, 255, 255, 0.05)',
        'active_color': 'rgba(255, 255, 255, 0.1)',
        'accent_color': '#5C5CFF',
        'shadow_color': 'rgba(0, 0, 0, 0.3)',
        'overlay_color': 'rgba(26, 27, 30, 0.95)',
        'success_color': '#4CAF50',
        'error_color': '#FF5252',
        'warning_color': '#FFC107'
    },
    'cyberpunk': {
        'background_color': '#0B0B19',
        'text_color': '#FF2E88',
        'button_color': '#1B1B2F',
        'button_hover_color': '#2B2B3F',
        'tab_selected_color': '#1B1B2F',
        'tab_unselected_color': '#0B0B19',
        'processing_highlight_color': 'rgba(255, 46, 136, 0.15)',
        'processed_text_color': '#00F3FF',
        'border_color': '#FF2E88',
        'hover_color': 'rgba(255, 46, 136, 0.1)',
        'active_color': 'rgba(255, 46, 136, 0.2)',
        'accent_color': '#FF2E88',
        'shadow_color': 'rgba(255, 46, 136, 0.3)',
        'overlay_color': 'rgba(11, 11, 25, 0.95)',
        'success_color': '#00F3FF',
        'error_color': '#FF2E88',
        'warning_color': '#FFD700'
    }
}

def get_dialog_styles(theme):
    """Returns styles for dialog windows"""
    return f"""
        QDialog {{
            background-color: {theme['background_color']};
            color: {theme['text_color']};
            border: none;
            border-radius: 10px;
        }}
    """

def get_label_styles(theme):
    """Returns styles for labels"""
    return f"""
        QLabel {{
            color: {theme['text_color']};
            background: transparent;
            padding: 5px;
        }}
    """

def get_input_styles(theme):
    """Returns styles for input fields"""
    return f"""
        QLineEdit {{
            background-color: {theme['button_color']};
            color: {theme['text_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
            padding: 8px;
            margin: 2px;
        }}
        QLineEdit:hover {{
            background-color: {theme['button_hover_color']};
            border: 1px solid {theme['accent_color']};
        }}
    """

def get_button_styles(theme):
    """Returns styles for buttons"""
    return f"""
        QPushButton {{
            background-color: {theme['button_color']};
            color: {theme['text_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
            padding: 8px 15px;
            margin: 5px;
        }}
        QPushButton:hover {{
            background-color: {theme['button_hover_color']};
            border: 1px solid {theme['accent_color']};
        }}
    """

def get_tab_styles(theme):
    """Returns styles for tab widgets"""
    return f"""
        QTabWidget {{
            background-color: transparent;
            border: none;
        }}
        QTabWidget::pane {{
            border: 1px solid {theme['border_color']};
            background: {theme['background_color']};
            border-radius: 5px;
            margin-top: -1px;
        }}
        QTabBar::tab {{
            background: {theme['tab_unselected_color']};
            color: {theme['text_color']};
            padding: 10px 20px;
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
            margin: 2px;
        }}
        QTabBar::tab:selected {{
            background: {theme['tab_selected_color']};
            border: 1px solid {theme['accent_color']};
        }}
        QTabBar::tab:hover {{
            background: {theme['button_hover_color']};
        }}
    """

def get_combo_styles(theme):
    """Returns styles for combo boxes"""
    return f"""
        QComboBox {{
            background-color: {theme['button_color']};
            color: {theme['text_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
            padding: 8px;
            margin: 2px;
        }}
        QComboBox:hover {{
            background-color: {theme['button_hover_color']};
            border: 1px solid {theme['accent_color']};
        }}
        QComboBox::drop-down {{
            border: none;
            padding: 0 5px;
        }}
    """

def get_slider_styles(theme):
    """Returns styles for sliders"""
    return f"""
        QSlider {{
            background: transparent;
            height: 30px;
        }}
        QSlider::groove:horizontal {{
            background: {theme['button_color']};
            height: 4px;
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {theme['accent_color']};
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {theme['text_color']};
        }}
    """

def get_group_styles(theme):
    """Returns styles for group boxes"""
    return f"""
        QGroupBox {{
            background-color: {theme['background_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
            margin-top: 10px;
            padding: 15px;
        }}
        QGroupBox::title {{
            color: {theme['text_color']};
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }}
    """

def get_checkbox_styles(theme):
    """Returns styles for checkboxes"""
    return f"""
        QCheckBox {{
            color: {theme['text_color']};
            spacing: 8px;
            padding: 5px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {theme['border_color']};
            border-radius: 3px;
        }}
        QCheckBox::indicator:unchecked {{
            background-color: {theme['button_color']};
        }}
        QCheckBox::indicator:unchecked:hover {{
            background-color: {theme['button_hover_color']};
            border: 1px solid {theme['accent_color']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {theme['accent_color']};
        }}
    """

def get_menu_styles(theme):
    """Returns styles for menus"""
    return f"""
        QMenu {{
            background-color: {theme['background_color']};
            color: {theme['text_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 5px;
            padding: 5px;
        }}
        QMenu::item {{
            padding: 5px 20px;
            border-radius: 3px;
        }}
        QMenu::item:selected {{
            background-color: {theme['button_hover_color']};
        }}
    """

def get_scroll_area_styles(theme):
    """Returns styles for scroll areas"""
    return f"""
        QScrollArea {{
            background-color: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: {theme['background_color']};
            width: 12px;
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical {{
            background: {theme['button_color']};
            border-radius: 6px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {theme['button_hover_color']};
        }}
    """

def get_config_dialog_compact_styles(theme):
    """Returns compact styles for config dialog"""
    return f"""
        QDialog {{
            background-color: {theme['background_color']};
            color: {theme['text_color']};
            border: 1px solid {theme['border_color']};
            border-radius: 8px;
        }}
        QFormLayout {{
            margin: 5px;
            spacing: 5px;
        }}
        QLineEdit {{
            padding: 3px 5px;
            height: 25px;
        }}
        QComboBox {{
            height: 25px;
            padding: 3px 5px;
        }}
        QTabWidget::pane {{
            border: 1px solid {theme['border_color']};
            padding: 5px;
        }}
        QTabBar::tab {{
            padding: 5px 10px;
            min-width: 80px;
        }}
        QPushButton {{
            padding: 5px 10px;
            height: 25px;
        }}
    """

def get_complete_dialog_style(theme):
    """Returns complete style for dialog windows"""
    return "\n".join([
        get_dialog_styles(theme),
        get_label_styles(theme),
        get_input_styles(theme),
        get_button_styles(theme),
        get_tab_styles(theme),
        get_combo_styles(theme),
        get_slider_styles(theme),
        get_group_styles(theme),
        get_checkbox_styles(theme),
        get_menu_styles(theme),
        get_scroll_area_styles(theme),
        get_config_dialog_compact_styles(theme)
    ])