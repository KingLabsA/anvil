"""Tests for image analyzer."""

import pytest
from pathlib import Path
from anvil.image.analyzer import ImageAnalyzer, ImageAnalysis


@pytest.fixture
def sample_images(tmp_path):
    """Create sample images for testing."""
    # Create a minimal PNG file
    png_data = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    
    screenshot = tmp_path / "screenshot.png"
    screenshot.write_bytes(png_data)
    
    diagram = tmp_path / "flow_diagram.png"
    diagram.write_bytes(png_data)
    
    code = tmp_path / "code_snippet.png"
    code.write_bytes(png_data)
    
    generic = tmp_path / "random_image.png"
    generic.write_bytes(png_data)
    
    unsupported = tmp_path / "document.pdf"
    unsupported.write_bytes(b"%PDF-1.4")
    
    return tmp_path


class TestImageAnalyzer:
    """Test ImageAnalyzer functionality."""
    
    def test_analyze_screenshot(self, sample_images):
        """Test analyzing a screenshot."""
        analyzer = ImageAnalyzer()
        result = analyzer.analyze(sample_images / "screenshot.png")
        
        assert result.image_type == "screenshot"
        assert result.dimensions == (1, 1)
        assert len(result.suggestions) > 0
    
    def test_analyze_diagram(self, sample_images):
        """Test analyzing a diagram."""
        analyzer = ImageAnalyzer()
        result = analyzer.analyze(sample_images / "flow_diagram.png")
        
        assert result.image_type == "diagram"
        assert len(result.suggestions) > 0
    
    def test_analyze_code_image(self, sample_images):
        """Test analyzing a code image."""
        analyzer = ImageAnalyzer()
        result = analyzer.analyze(sample_images / "code_snippet.png")
        
        assert result.image_type == "code"
        assert len(result.suggestions) > 0
    
    def test_analyze_generic(self, sample_images):
        """Test analyzing a generic image."""
        analyzer = ImageAnalyzer()
        result = analyzer.analyze(sample_images / "random_image.png")
        
        assert result.image_type == "generic"
        assert len(result.suggestions) > 0
    
    def test_unsupported_format(self, sample_images):
        """Test analyzing an unsupported format."""
        analyzer = ImageAnalyzer()
        with pytest.raises(ValueError, match="Unsupported image format"):
            analyzer.analyze(sample_images / "document.pdf")
    
    def test_file_not_found(self, tmp_path):
        """Test analyzing a non-existent file."""
        analyzer = ImageAnalyzer()
        with pytest.raises(FileNotFoundError):
            analyzer.analyze(tmp_path / "nonexistent.png")
    
    def test_supported_formats(self):
        """Test getting supported formats."""
        analyzer = ImageAnalyzer()
        formats = analyzer.get_supported_formats()
        assert ".png" in formats
        assert ".jpg" in formats
        assert ".jpeg" in formats
    
    def test_is_supported(self, sample_images):
        """Test checking if a file is supported."""
        analyzer = ImageAnalyzer()
        assert analyzer.is_supported(sample_images / "screenshot.png")
        assert not analyzer.is_supported(sample_images / "document.pdf")


class TestImageAnalysis:
    """Test ImageAnalysis dataclass."""
    
    def test_create_analysis(self):
        """Test creating an image analysis."""
        analysis = ImageAnalysis(
            image_path="/path/to/image.png",
            image_type="screenshot",
            dimensions=(1920, 1080),
            description="Test screenshot",
            detected_text=["Text 1", "Text 2"],
            detected_code=["code 1"],
            suggestions=["suggestion 1"],
            confidence=0.8,
        )
        
        assert analysis.image_path == "/path/to/image.png"
        assert analysis.image_type == "screenshot"
        assert analysis.dimensions == (1920, 1080)
        assert analysis.confidence == 0.8
