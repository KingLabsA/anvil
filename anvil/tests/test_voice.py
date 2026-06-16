"""Tests for voice recognition and text-to-speech."""

import pytest
import time
from anvil.voice.recognizer import VoiceRecognizer, TextToSpeech, VoiceCommand


class TestVoiceRecognizer:
    """Test voice recognizer."""
    
    def test_init(self):
        rec = VoiceRecognizer()
        assert rec.language == "en-US"
        assert rec.is_listening is False
    
    def test_start_stop_listening(self):
        rec = VoiceRecognizer()
        assert rec.start_listening() is True
        assert rec.is_listening is True
        rec.stop_listening()
        assert rec.is_listening is False
    
    def test_process_audio(self):
        rec = VoiceRecognizer()
        result = rec.process_audio(b"audio data")
        assert isinstance(result, VoiceCommand)
        assert result.text == "[Voice input received]"
        assert result.confidence == 0.8
    
    def test_parse_command_run(self):
        rec = VoiceRecognizer()
        cmd = rec.parse_command("Run the tests")
        assert cmd["intent"] == "run"
    
    def test_parse_command_fix(self):
        rec = VoiceRecognizer()
        cmd = rec.parse_command("Fix the bug in main.py")
        assert cmd["intent"] == "fix"
    
    def test_parse_command_explain(self):
        rec = VoiceRecognizer()
        cmd = rec.parse_command("Explain this code")
        assert cmd["intent"] == "explain"
    
    def test_parse_command_test(self):
        rec = VoiceRecognizer()
        cmd = rec.parse_command("Test the code")
        assert cmd["intent"] == "test"
    
    def test_parse_command_general(self):
        rec = VoiceRecognizer()
        cmd = rec.parse_command("Hello world")
        assert cmd["intent"] == "general"


class TestTextToSpeech:
    """Test text-to-speech."""
    
    def test_init(self):
        tts = TextToSpeech()
        assert tts.rate == 1.0
        assert tts.is_speaking is False
    
    def test_speak(self):
        tts = TextToSpeech()
        tts.speak("Hello world")
        assert tts.is_speaking is False
    
    def test_stop(self):
        tts = TextToSpeech()
        tts.is_speaking = True
        tts.stop()
        assert tts.is_speaking is False


class TestVoiceCommand:
    """Test voice command dataclass."""
    
    def test_create_command(self):
        cmd = VoiceCommand(
            text="Test command",
            confidence=0.9,
            language="en-US",
            timestamp=time.time(),
        )
        assert cmd.text == "Test command"
        assert cmd.confidence == 0.9
        assert cmd.language == "en-US"
