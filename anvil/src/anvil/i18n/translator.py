"""Translation system for Anvil - support multiple languages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class Translation:
    """A single translation entry."""
    key: str
    value: str
    context: str = ""


class Translator:
    """Translate text to different languages."""
    
    # Built-in translations
    TRANSLATIONS: dict[str, dict[str, str]] = {
        "en": {
            "app.name": "Anvil",
            "app.subtitle": "The Self-Verified Coding Agent",
            "app.description": "Where code gets forged, hammered, and tested until it holds.",
            "action.run": "Run Task",
            "action.verify": "Verify Code",
            "action.explain": "Explain Code",
            "action.refactor": "Refactor Code",
            "action.fix": "Fix Errors",
            "action.test": "Generate Tests",
            "status.connected": "Connected",
            "status.disconnected": "Disconnected",
            "status.running": "Running...",
            "status.completed": "Completed",
            "status.failed": "Failed",
            "error.connection": "Connection error",
            "error.server": "Server not running",
            "help.get_started": "Get Started",
            "help.documentation": "Documentation",
        },
        "es": {
            "app.name": "Anvil",
            "app.subtitle": "El Agente de Programación Autoverificado",
            "app.description": "Donde el código se forja, martilla y prueba hasta que funciona.",
            "action.run": "Ejecutar Tarea",
            "action.verify": "Verificar Código",
            "action.explain": "Explicar Código",
            "action.refactor": "Refactorizar Código",
            "action.fix": "Corregir Errores",
            "action.test": "Generar Pruebas",
            "status.connected": "Conectado",
            "status.disconnected": "Desconectado",
            "status.running": "Ejecutando...",
            "status.completed": "Completado",
            "status.failed": "Fallido",
            "error.connection": "Error de conexión",
            "error.server": "Servidor no disponible",
            "help.get_started": "Comenzar",
            "help.documentation": "Documentación",
        },
        "fr": {
            "app.name": "Anvil",
            "app.subtitle": "L'Agent de Programmation Auto-Vérifié",
            "app.description": "Là où le code est forgé, martelé et testé jusqu'à ce qu'il tienne.",
            "action.run": "Exécuter la Tâche",
            "action.verify": "Vérifier le Code",
            "action.explain": "Expliquer le Code",
            "action.refactor": "Refactoriser le Code",
            "action.fix": "Corriger les Erreurs",
            "action.test": "Générer des Tests",
            "status.connected": "Connecté",
            "status.disconnected": "Déconnecté",
            "status.running": "Exécution...",
            "status.completed": "Terminé",
            "status.failed": "Échoué",
            "error.connection": "Erreur de connexion",
            "error.server": "Serveur non disponible",
            "help.get_started": "Commencer",
            "help.documentation": "Documentation",
        },
        "de": {
            "app.name": "Anvil",
            "app.subtitle": "Der selbstverifizierende Coding-Agent",
            "app.description": "Wo Code geschmiedet, gehämmert und getestet wird, bis er hält.",
            "action.run": "Aufgabe Ausführen",
            "action.verify": "Code Verifizieren",
            "action.explain": "Code Erklären",
            "action.refactor": "Code Refactoren",
            "action.fix": "Fehler Beheben",
            "action.test": "Tests Generieren",
            "status.connected": "Verbunden",
            "status.disconnected": "Getrennt",
            "status.running": "Wird ausgeführt...",
            "status.completed": "Abgeschlossen",
            "status.failed": "Fehlgeschlagen",
            "error.connection": "Verbindungsfehler",
            "error.server": "Server nicht erreichbar",
            "help.get_started": "Loslegen",
            "help.documentation": "Dokumentation",
        },
        "ja": {
            "app.name": "Anvil",
            "app.subtitle": "自己検証コーディングエージェント",
            "app.description": "コードが鍛えられ、検証され、テストされて、ようやく成立する場所。",
            "action.run": "タスクを実行",
            "action.verify": "コードを検証",
            "action.explain": "コードを説明",
            "action.refactor": "コードをリファクタリング",
            "action.fix": "エラーを修正",
            "action.test": "テストを生成",
            "status.connected": "接続済み",
            "status.disconnected": "切断",
            "status.running": "実行中...",
            "status.completed": "完了",
            "status.failed": "失敗",
            "error.connection": "接続エラー",
            "error.server": "サーバーが起動していません",
            "help.get_started": "はじめに",
            "help.documentation": "ドキュメント",
        },
        "zh": {
            "app.name": "Anvil",
            "app.subtitle": "自验证编码代理",
            "app.description": "代码在此锻造、锤炼、测试，直至通过。",
            "action.run": "运行任务",
            "action.verify": "验证代码",
            "action.explain": "解释代码",
            "action.refactor": "重构代码",
            "action.fix": "修复错误",
            "action.test": "生成测试",
            "status.connected": "已连接",
            "status.disconnected": "未连接",
            "status.running": "运行中...",
            "status.completed": "已完成",
            "status.failed": "失败",
            "error.connection": "连接错误",
            "error.server": "服务器未运行",
            "help.get_started": "开始使用",
            "help.documentation": "文档",
        },
        "ko": {
            "app.name": "Anvil",
            "app.subtitle": "자기검증 코딩 에이전트",
            "app.description": "코드가 단조되고, 두드려지고, 테스트되어 견딜 때까지.",
            "action.run": "작업 실행",
            "action.verify": "코드 검증",
            "action.explain": "코드 설명",
            "action.refactor": "코드 리팩터링",
            "action.fix": "오류 수정",
            "action.test": "테스트 생성",
            "status.connected": "연결됨",
            "status.disconnected": "연결 끊김",
            "status.running": "실행 중...",
            "status.completed": "완료",
            "status.failed": "실패",
            "error.connection": "연결 오류",
            "error.server": "서버가 실행되지 않았습니다",
            "help.get_started": "시작하기",
            "help.documentation": "문서",
        },
        "pt": {
            "app.name": "Anvil",
            "app.subtitle": "O Agente de Programação Auto-Verificado",
            "app.description": "Onde o código é forjado, martelado e testado até funcionar.",
            "action.run": "Executar Tarefa",
            "action.verify": "Verificar Código",
            "action.explain": "Explicar Código",
            "action.refactor": "Refatorar Código",
            "action.fix": "Corrigir Erros",
            "action.test": "Gerar Testes",
            "status.connected": "Conectado",
            "status.disconnected": "Desconectado",
            "status.running": "Executando...",
            "status.completed": "Concluído",
            "status.failed": "Falhou",
            "error.connection": "Erro de conexão",
            "error.server": "Servidor não disponível",
            "help.get_started": "Começar",
            "help.documentation": "Documentação",
        },
        "ru": {
            "app.name": "Anvil",
            "app.subtitle": "Самопроверяющий агент кодирования",
            "app.description": "Где код куется, проковывается и тестируется до тех пор, пока не выдержит.",
            "action.run": "Запустить задачу",
            "action.verify": "Проверить код",
            "action.explain": "Объяснить код",
            "action.refactor": "Рефакторинг кода",
            "action.fix": "Исправить ошибки",
            "action.test": "Сгенерировать тесты",
            "status.connected": "Подключено",
            "status.disconnected": "Отключено",
            "status.running": "Выполняется...",
            "status.completed": "Завершено",
            "status.failed": "Ошибка",
            "error.connection": "Ошибка соединения",
            "error.server": "Сервер не запущен",
            "help.get_started": "Начать",
            "help.documentation": "Документация",
        },
        "it": {
            "app.name": "Anvil",
            "app.subtitle": "L'Agente di Programmazione Auto-Verificato",
            "app.description": "Dove il codice viene forgiato, martellato e testato fino a reggere.",
            "action.run": "Esegui Compito",
            "action.verify": "Verifica Codice",
            "action.explain": "Spiega Codice",
            "action.refactor": "Refactoring Codice",
            "action.fix": "Correggi Errori",
            "action.test": "Genera Test",
            "status.connected": "Connesso",
            "status.disconnected": "Disconnesso",
            "status.running": "In esecuzione...",
            "status.completed": "Completato",
            "status.failed": "Fallito",
            "error.connection": "Errore di connessione",
            "error.server": "Server non disponibile",
            "help.get_started": "Inizia",
            "help.documentation": "Documentazione",
        },
        "ar": {
            "app.name": "Anvil",
            "app.subtitle": "وكيل البرمجة المُتحقق من نفسه",
            "app.description": "حيث يتم تشكيل الكود ودقه واختباره حتى يصمد.",
            "action.run": "تنفيذ المهمة",
            "action.verify": "التحقق من الكود",
            "action.explain": "شرح الكود",
            "action.refactor": "إعادة هيكلة الكود",
            "action.fix": "إصلاح الأخطاء",
            "action.test": "إنشاء الاختبارات",
            "status.connected": "متصل",
            "status.disconnected": "غير متصل",
            "status.running": "جاري التنفيذ...",
            "status.completed": "مكتمل",
            "status.failed": "فشل",
            "error.connection": "خطأ في الاتصال",
            "error.server": "الخادم غير متاح",
            "help.get_started": "ابدأ",
            "help.documentation": "التوثيق",
        },
    }
    
    def __init__(self, language: str = "en"):
        """Initialize translator.
        
        Args:
            language: Language code (en, es, fr, de, ja, zh, ko, pt, ru, it, ar)
        """
        self.language = language
        self.custom_translations: dict[str, str] = {}
    
    def translate(self, key: str, **kwargs) -> str:
        """Translate a key to the current language.
        
        Args:
            key: Translation key
            **kwargs: Format arguments for string interpolation
            
        Returns:
            Translated string
        """
        # Check custom translations first
        if self.language in self.custom_translations and key in self.custom_translations[self.language]:
            return self.custom_translations[self.language][key].format(**kwargs)
        
        # Check built-in translations
        if self.language in self.TRANSLATIONS:
            if key in self.TRANSLATIONS[self.language]:
                return self.TRANSLATIONS[self.language][key].format(**kwargs)
        
        # Fall back to English
        if key in self.TRANSLATIONS.get("en", {}):
            return self.TRANSLATIONS["en"][key].format(**kwargs)
        
        # Return key as fallback
        return key.format(**kwargs)
    
    def set_language(self, language: str) -> None:
        """Set the current language."""
        self.language = language
    
    def add_translation(self, key: str, value: str, language: str | None = None) -> None:
        """Add a custom translation."""
        lang = language or self.language
        if lang not in self.custom_translations:
            self.custom_translations[lang] = {}
        self.custom_translations[lang][key] = value
    
    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages."""
        return list(self.TRANSLATIONS.keys())
    
    def get_language_name(self, language: str) -> str:
        """Get the native name of a language."""
        names = {
            "en": "English",
            "es": "Español",
            "fr": "Français",
            "de": "Deutsch",
            "ja": "日本語",
            "zh": "中文",
            "ko": "한국어",
            "pt": "Português",
            "ru": "Русский",
            "it": "Italiano",
            "ar": "العربية",
        }
        return names.get(language, language)
    
    def load_translations(self, path: str | Path) -> None:
        """Load translations from a JSON file."""
        data = json.loads(Path(path).read_text())
        for lang, translations in data.items():
            if lang not in self.custom_translations:
                self.custom_translations[lang] = {}
            self.custom_translations[lang].update(translations)
    
    def export_translations(self, path: str | Path) -> None:
        """Export custom translations to a JSON file."""
        Path(path).write_text(json.dumps(self.custom_translations, indent=2))
    
    def get_all_translations(self, language: str | None = None) -> dict[str, str]:
        """Get all translations for a language."""
        lang = language or self.language
        result = {}
        
        # Add built-in translations
        if lang in self.TRANSLATIONS:
            result.update(self.TRANSLATIONS[lang])
        
        # Add custom translations
        if lang in self.custom_translations:
            result.update(self.custom_translations[lang])
        
        return result
