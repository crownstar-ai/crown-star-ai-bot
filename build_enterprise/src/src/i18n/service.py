# i18n/service.py – Internationalization service for CrownStar
import json
import os
from pathlib import Path
from typing import Dict, Optional
import locale
import re

class TranslationService:
    _instance = None
    _translations: Dict[str, Dict] = {}
    _current_language: str = "en"
    _available_languages: list = []
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_all_translations()
            cls._instance._detect_system_language()
        return cls._instance
    
    def _load_all_translations(self):
        locales_dir = Path(__file__).parent / "locales"
        if not locales_dir.exists():
            return
        for lang_file in locales_dir.glob("*.json"):
            lang_code = lang_file.stem
            with open(lang_file, 'r', encoding='utf-8') as f:
                self._translations[lang_code] = json.load(f)
                self._available_languages.append(lang_code)
        # Ensure English exists as fallback
        if "en" not in self._translations:
            self._translations["en"] = {}
        self._current_language = "en"
    
    def _detect_system_language(self):
        try:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang:
                lang_code = sys_lang.split('_')[0]
                if lang_code in self._available_languages:
                    self._current_language = lang_code
        except:
            pass
    
    def set_language(self, lang_code: str) -> bool:
        if lang_code in self._translations:
            self._current_language = lang_code
            return True
        return False
    
    def get_language(self) -> str:
        return self._current_language
    
    def get_available_languages(self) -> list:
        return self._available_languages
    
    def get_language_name(self, lang_code: str) -> str:
        trans = self._translations.get(lang_code, {})
        return trans.get("language_name", lang_code)
    
    def translate(self, key: str, **kwargs) -> str:
        parts = key.split('.')
        current = self._translations.get(self._current_language, {})
        # Fallback to English if key missing
        if not current and self._current_language != "en":
            current = self._translations.get("en", {})
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = None
                break
        if current is None:
            # Key not found – return key itself
            return key
        text = str(current)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        return text
    
    def t(self, key: str, **kwargs) -> str:
        return self.translate(key, **kwargs)
    
    def pluralize(self, key: str, count: int, **kwargs) -> str:
        """Simple pluralization – for more complex, use gettext style"""
        singular_key = f"{key}_singular"
        plural_key = f"{key}_plural"
        singular = self.translate(singular_key, **kwargs)
        plural = self.translate(plural_key, **kwargs)
        if count == 1:
            return singular
        return plural.format(count=count)
    
    def format_number(self, number: float, decimals: int = 2) -> str:
        lang = self._current_language
        if lang == "de":
            return f"{number:,.{decimals}f}".replace(",", ".").replace(".", ",")
        elif lang == "fr":
            return f"{number:,.{decimals}f}".replace(",", " ")
        else:
            return f"{number:,.{decimals}f}"
    
    def format_date(self, dt, format_str=None):
        import datetime
        if format_str is None:
            lang = self._current_language
            if lang == "zh":
                format_str = "%Y年%m月%d日"
            elif lang == "ja":
                format_str = "%Y年%m月%d日"
            elif lang == "de":
                format_str = "%d.%m.%Y"
            else:
                format_str = "%Y-%m-%d"
        return dt.strftime(format_str)
    
    def format_datetime(self, dt, format_str=None):
        import datetime
        if format_str is None:
            lang = self._current_language
            if lang == "zh":
                format_str = "%Y年%m月%d日 %H:%M:%S"
            elif lang == "de":
                format_str = "%d.%m.%Y %H:%M:%S"
            else:
                format_str = "%Y-%m-%d %H:%M:%S"
        return dt.strftime(format_str)

# Singleton instance
i18n = TranslationService()
