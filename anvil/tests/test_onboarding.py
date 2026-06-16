"""Tests for onboarding system."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from anvil.onboarding.manager import OnboardingManager, OnboardingTour, OnboardingStep
from anvil.api.server import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def temp_progress_file(tmp_path):
    """Create a temporary progress file."""
    return tmp_path / "onboarding.json"


@pytest.fixture
def onboarding_manager(temp_progress_file):
    """Create an onboarding manager with temp file."""
    return OnboardingManager(progress_file=temp_progress_file)


class TestOnboardingStep:
    """Test OnboardingStep dataclass."""
    
    def test_create_step(self):
        """Test creating an onboarding step."""
        step = OnboardingStep(
            id="test_step",
            title="Test Step",
            description="This is a test step",
            action="click",
            target=".test-element",
        )
        
        assert step.id == "test_step"
        assert step.title == "Test Step"
        assert step.description == "This is a test step"
        assert step.action == "click"
        assert step.target == ".test-element"
        assert step.completed is False
        assert step.skippable is True


class TestOnboardingTour:
    """Test OnboardingTour dataclass."""
    
    def test_create_tour(self):
        """Test creating an onboarding tour."""
        tour = OnboardingTour(
            id="test_tour",
            name="Test Tour",
            description="This is a test tour",
        )
        
        assert tour.id == "test_tour"
        assert tour.name == "Test Tour"
        assert tour.description == "This is a test tour"
        assert tour.steps == []
        assert tour.current_step == 0
    
    def test_tour_navigation(self):
        """Test tour navigation."""
        tour = OnboardingTour(
            id="test_tour",
            name="Test Tour",
            description="Test",
        )
        
        # Add steps
        tour.steps = [
            OnboardingStep(id="step1", title="Step 1", description="First", action="watch"),
            OnboardingStep(id="step2", title="Step 2", description="Second", action="watch"),
            OnboardingStep(id="step3", title="Step 3", description="Third", action="watch"),
        ]
        
        # Test next_step
        step1 = tour.next_step()
        assert step1.id == "step1"
        assert tour.current_step == 1
        
        step2 = tour.next_step()
        assert step2.id == "step2"
        assert tour.current_step == 2
        
        # Test previous_step
        prev = tour.previous_step()
        assert prev.id == "step1"
        assert tour.current_step == 1
        
        # Test is_complete
        assert not tour.is_complete()
        
        # Go to end
        tour.next_step()
        tour.next_step()
        assert tour.is_complete()
        
        # Test reset
        tour.reset()
        assert tour.current_step == 0
        assert not tour.is_complete()


class TestOnboardingManager:
    """Test OnboardingManager."""
    
    def test_create_manager(self, temp_progress_file):
        """Test creating an onboarding manager."""
        manager = OnboardingManager(progress_file=temp_progress_file)
        assert manager is not None
        assert manager.progress_file == temp_progress_file
    
    def test_default_tours_created(self, onboarding_manager):
        """Test that default tours are created."""
        tours = onboarding_manager.list_tours()
        assert len(tours) == 3
        
        tour_ids = [tour.id for tour in tours]
        assert "quick_start" in tour_ids
        assert "features" in tour_ids
        assert "shortcuts" in tour_ids
    
    def test_get_tour(self, onboarding_manager):
        """Test getting a tour by ID."""
        tour = onboarding_manager.get_tour("quick_start")
        assert tour is not None
        assert tour.id == "quick_start"
        assert tour.name == "Quick Start"
        
        # Test non-existent tour
        tour = onboarding_manager.get_tour("nonexistent")
        assert tour is None
    
    def test_start_tour(self, onboarding_manager):
        """Test starting a tour."""
        tour = onboarding_manager.start_tour("quick_start")
        assert tour is not None
        assert tour.current_step == 0
        
        # Test non-existent tour
        tour = onboarding_manager.start_tour("nonexistent")
        assert tour is None
    
    def test_complete_tour(self, onboarding_manager):
        """Test completing a tour."""
        # Complete a tour
        success = onboarding_manager.complete_tour("quick_start")
        assert success is True
        
        # Check if completed
        assert onboarding_manager.is_tour_completed("quick_start")
        
        # Test non-existent tour
        success = onboarding_manager.complete_tour("nonexistent")
        assert success is False
    
    def test_get_completed_tours(self, onboarding_manager):
        """Test getting completed tours."""
        # Initially no tours completed
        completed = onboarding_manager.get_completed_tours()
        assert len(completed) == 0
        
        # Complete some tours
        onboarding_manager.complete_tour("quick_start")
        onboarding_manager.complete_tour("features")
        
        completed = onboarding_manager.get_completed_tours()
        assert len(completed) == 2
        assert "quick_start" in completed
        assert "features" in completed
    
    def test_should_show_onboarding(self, onboarding_manager):
        """Test if onboarding should be shown."""
        # Initially should show
        assert onboarding_manager.should_show_onboarding()
        
        # After completing a tour, should not show
        onboarding_manager.complete_tour("quick_start")
        assert not onboarding_manager.should_show_onboarding()
    
    def test_get_recommended_tour(self, onboarding_manager):
        """Test getting recommended tour."""
        # Initially recommend quick_start
        tour = onboarding_manager.get_recommended_tour()
        assert tour is not None
        assert tour.id == "quick_start"
        
        # After completing quick_start, recommend features
        onboarding_manager.complete_tour("quick_start")
        tour = onboarding_manager.get_recommended_tour()
        assert tour is not None
        assert tour.id == "features"
        
        # After completing features, recommend shortcuts
        onboarding_manager.complete_tour("features")
        tour = onboarding_manager.get_recommended_tour()
        assert tour is not None
        assert tour.id == "shortcuts"
        
        # After completing all, no recommendation
        onboarding_manager.complete_tour("shortcuts")
        tour = onboarding_manager.get_recommended_tour()
        assert tour is None
    
    def test_reset_all_progress(self, onboarding_manager):
        """Test resetting all progress."""
        # Complete some tours
        onboarding_manager.complete_tour("quick_start")
        onboarding_manager.complete_tour("features")
        
        # Reset
        onboarding_manager.reset_all_progress()
        
        # Check all reset
        assert len(onboarding_manager.get_completed_tours()) == 0
        assert onboarding_manager.should_show_onboarding()
    
    def test_progress_persistence(self, temp_progress_file):
        """Test that progress persists across manager instances."""
        # Create manager and complete a tour
        manager1 = OnboardingManager(progress_file=temp_progress_file)
        manager1.complete_tour("quick_start")
        
        # Create new manager and check progress
        manager2 = OnboardingManager(progress_file=temp_progress_file)
        assert manager2.is_tour_completed("quick_start")
    
    def test_tour_steps_content(self, onboarding_manager):
        """Test that tour steps have proper content."""
        tour = onboarding_manager.get_tour("quick_start")
        assert tour is not None
        assert len(tour.steps) > 0
        
        for step in tour.steps:
            assert step.id
            assert step.title
            assert step.description
            assert step.action in ["click", "type", "watch", "complete"]


class TestOnboardingAPI:
    """Test onboarding API endpoints."""
    
    def test_list_tours_endpoint(self, client):
        """Test listing tours endpoint."""
        response = client.get("/api/onboarding/tours")
        assert response.status_code == 200
        data = response.json()
        assert "tours" in data
        assert len(data["tours"]) == 3
    
    def test_get_tour_endpoint(self, client):
        """Test getting a specific tour."""
        response = client.get("/api/onboarding/tours/quick_start")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "quick_start"
        assert "steps" in data
        assert len(data["steps"]) > 0
    
    def test_get_nonexistent_tour_endpoint(self, client):
        """Test getting a non-existent tour."""
        response = client.get("/api/onboarding/tours/nonexistent")
        assert response.status_code == 404
    
    def test_start_tour_endpoint(self, client):
        """Test starting a tour."""
        response = client.post("/api/onboarding/tours/quick_start/start")
        assert response.status_code == 200
        data = response.json()
        assert data["tour_id"] == "quick_start"
        assert "step" in data
    
    def test_complete_tour_endpoint(self, client):
        """Test completing a tour."""
        response = client.post("/api/onboarding/tours/quick_start/complete")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
    
    def test_onboarding_status_endpoint(self, client):
        """Test onboarding status endpoint."""
        response = client.get("/api/onboarding/status")
        assert response.status_code == 200
        data = response.json()
        assert "should_show_onboarding" in data
        assert "completed_tours" in data
        assert "recommended_tour" in data
