DARK_PALETTE = {
    "bg_black": "#000000", "bg_very_dark": "#121212", "bg_dark": "#181818",
    "bg_medium": "#282828", "bg_medium_translucent": "rgba(42, 42, 42, 0.7)",
    "list_selected": "#4A4A4A", "slider_groove": "#535353", "text_primary": "#FFFFFF",
    "text_secondary": "#b3b3b3", "accent_primary": "#1DB954", "accent_secondary": "#1ED760"
}
LIGHT_PALETTE = {
    "bg_black": "#E8E8E8", "bg_very_dark": "#F5F5F5", "bg_dark": "#FFFFFF",
    "bg_medium": "#E0E0E0", "bg_medium_translucent": "rgba(200, 200, 200, 0.7)",
    "list_selected": "#B0BEC5", "slider_groove": "#BDBDBD", "text_primary": "#000000",
    "text_secondary": "#555555", "accent_primary": "#1DB954", "accent_secondary": "#1ED760"
}
OCEAN_PALETTE = DARK_PALETTE.copy(); OCEAN_PALETTE.update({"accent_primary": "#00A8CC", "accent_secondary": "#00CFF4"})
SYNTHWAVE_PALETTE = DARK_PALETTE.copy(); SYNTHWAVE_PALETTE.update({"accent_primary": "#F92672", "accent_secondary": "#FF007F", "text_secondary": "#A6E22E"})

THEME_PALETTES = {
    "dark": DARK_PALETTE, "light": LIGHT_PALETTE,
    "ocean": OCEAN_PALETTE, "synthwave": SYNTHWAVE_PALETTE
}

BASE_STYLESHEET = """
QWidget {{ background-color: {bg_very_dark}; color: {text_primary}; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; border: none; }}
#left_panel {{ background-color: {bg_black}; }} #right_panel, #center_panel {{ background-color: {bg_very_dark}; }}
#player_bar, #player_bar QWidget {{ background-color: {bg_dark}; }} #player_bar {{ border-top: 1px solid {bg_medium}; }}
QPushButton {{ border: none; background-color: transparent; }}
QPushButton#new_playlist_btn {{ font-size: 18px; color: {text_secondary}; font-weight: bold; }} QPushButton#new_playlist_btn:hover {{ color: {text_primary}; }}
QPushButton#search_btn, #settings_save_btn {{ background-color: {accent_primary}; color: {text_primary}; padding: 10px 15px; border-radius: 20px; font-weight: bold; }}
QPushButton#search_btn:hover, #settings_save_btn:hover {{ background-color: {accent_secondary}; }}
#settings_button {{ border-radius: 16px; }} #settings_button:hover {{ background-color: {bg_medium_translucent}; }}
#player_bar QPushButton {{ min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px; }}
#player_bar QPushButton:hover {{ color: {text_primary}; }} #play_pause_btn {{ background-color: {text_primary}; border-radius: 18px; min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px; }}
QListWidget {{ background-color: transparent; }}
QListWidget::item {{ padding: 0px; min-height: 60px; margin-bottom: 2px; border-radius: 4px; }}
QListWidget::item:hover {{ background-color: {bg_medium_translucent}; }} QListWidget::item:selected {{ background-color: {list_selected}; }}
QListWidget::item:selected QWidget, QListWidget::item:selected QLabel {{ background-color: transparent; color: {text_primary}; }}
QLineEdit {{ background-color: {bg_medium}; padding: 8px; border-radius: 5px; }}
QSlider::groove:horizontal {{ background: {slider_groove}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {text_primary}; width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }}
QSlider::handle:horizontal:hover {{ background: {accent_primary}; }} QSlider::sub-page:horizontal {{ background: {text_secondary}; }}
#player_bar QSlider::sub-page:horizontal {{ background: {accent_primary}; }}
QLabel#now_playing_title {{ font-size: 14px; font-weight: bold; }}
QLabel#now_playing_artist, #time_label, #duration_label, #right_panel_header, QTextBrowser {{ color: {text_secondary}; }}
#time_label, #duration_label {{ font-size: 11px; }}
#artist_name_label, #right_panel_header {{ background-color: transparent; }}
#artist_name_label {{ font-size: 48px; font-weight: 900; padding: 10px 0; }}
#right_panel_header {{ font-size: 14px; font-weight: bold; text-transform: uppercase; padding: 10px 0 5px 0; }}
QTextBrowser {{ background-color: transparent; border: none; font-size: 13px; }}

QScrollBar:vertical {{
    background: {bg_dark};
    width: 12px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {slider_groove};
    min-height: 25px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical:hover {{
    background: {list_selected};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background: {bg_dark};
    height: 12px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {slider_groove};
    min-width: 25px;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {list_selected};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none;
    background: none;
    width: 0px;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

QDialog, QMessageBox, QInputDialog {{ background-color: {bg_medium}; }}
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {{
    background-color: transparent;
    color: {text_primary};
}}
QDialog QLineEdit {{
    background-color: {bg_dark};
}}
QDialog QPushButton {{
    background-color: {slider_groove};
    color: {text_primary};
    padding: 8px 16px;
    border-radius: 5px;
    min-width: 80px;
    font-weight: bold;
}}
QDialog QPushButton:hover {{
    background-color: {list_selected};
}}

QPushButton#dialog_accept_btn {{
    background-color: {accent_primary};
}}
QPushButton#dialog_accept_btn:hover {{
    background-color: {accent_secondary};
}}

QDialog QComboBox {{ padding: 5px; background-color: {bg_dark}; border-radius: 4px; }}
QPushButton#clear_cache_btn {{ background-color: {slider_groove}; color: {text_primary}; padding: 8px 16px; border-radius: 5px; }}
QPushButton#clear_cache_btn:hover {{ background-color: {list_selected}; }}
"""

def get_theme(theme_name="dark"):
    palette = THEME_PALETTES.get(theme_name, DARK_PALETTE)
    return BASE_STYLESHEET.format(**palette)

def get_color_for_theme(theme_name, color_key):
    palette = THEME_PALETTES.get(theme_name, DARK_PALETTE)
    return palette.get(color_key, "#121212")