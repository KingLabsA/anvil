"""Tests for internationalization (i18n)."""

import pytest
import tempfile
from pathlib import Path
from anvil.i18n.translator import Translator, Translation


class TestTranslator:
    """Test translator functionality."""
    
    def test_init_default(self):
        translator = Translator()
        assert translator.language == "en"
    
    def test_init_custom_language(self):
        translator = Translator(language="es")
        assert translator.language == "es"
    
    def test_translate_english(self):
        translator = Translator(language="en")
        assert translator.translate("app.name") == "Anvil"
        assert translator.translate("action.run") == "Run Task"
    
    def test_translate_spanish(self):
        translator = Translator(language="es")
        assert translator.translate("app.name") == "Anvil"
        assert translator.translate("action.run") == "Ejecutar Tarea"
    
    def test_translate_french(self):
        translator = Translator(language="fr")
        assert translator.translate("app.name") == "Anvil"
        assert translator.translate("action.run") == "Exécuter la Tâche"
    
    def test_translate_fallback_to_english(self):
        translator = Translator(language="xx")  # Unknown language
        assert translator.translate("app.name") == "Anvil"
        assert translator.translate("action.run") == "Run Task"
    
    def test_translate_unknown_key(self):
        translator = Translator(language="en")
        assert translator.translate("unknown.key") == "unknown.key"
    
    def test_set_language(self):
        translator = Translator(language="en")
        translator.set_language("es")
        assert translator.language == "es"
        assert translator.translate("action.run") == "Ejecutar Tarea"
    
    def test_add_custom_translation(self):
        translator = Translator(language="en")
        translator.add_translation("custom.key", "Custom Value")
        assert translator.translate("custom.key") == "Custom Value"
    
    def test_get_supported_languages(self):
        translator = Translator()
        languages = translator.get_supported_languages()
        assert "en" in languages
        assert "es" in languages
        assert "fr" in languages
    
    def test_get_language_name(self):
        translator = Translator()
        assert translator.get_language_name("en") == "English"
        assert translator.get_language_name("es") == "Español"
        assert translator.get_language_name("ja") == "日本語"
    
    def test_export_import_translations(self, tmp_path):
        translator = Translator(language="en")
        translator.add_translation("test.key", "Test Value")
        
        # Export
        export_path = tmp_path / "translations.json"
        translator.export_translations(export_path)
        assert export_path.exists()
        
        # Import
        translator2 = Translator(language="en")
        translator2.load_translations(export_path)
        assert translator2.translate("test.key") == "Test Value"
    
    def test_get_all_translations(self):
        translator = Translator(language="en")
        translations = translator.get_all_translations()
        assert "app.name" in translations
        assert "action.run" in translations


class TestTranslation:
    """Test Translation dataclass."""
    
    def test_create_translation(self):
        translation = Translation(
            key="test.key",
            value="Test Value",
            context="Test context",
        )
        assert translation.key == "test.key"
        assert translation.value == "Test Value"
        assert translation.context == "Test context"
    
    def test_translation_defaults(self):
        translation = Translation(key="test.key", value="Test")
        assert translation.context == ""
