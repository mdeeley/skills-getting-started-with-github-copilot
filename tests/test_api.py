"""
Tests for the Mergington High School API endpoints
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            **details,
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        if name in activities:
            activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that GET /activities returns all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        
        # Check that we have activities
        assert len(data) > 0
        assert "Soccer Team" in data
        assert "Drama Club" in data
    
    def test_activity_structure(self, client):
        """Test that each activity has the correct structure"""
        response = client.get("/activities")
        data = response.json()
        
        for name, details in data.items():
            assert "description" in details
            assert "schedule" in details
            assert "max_participants" in details
            assert "participants" in details
            assert isinstance(details["participants"], list)
            assert isinstance(details["max_participants"], int)


class TestSignupEndpoint:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_for_valid_activity(self, client):
        """Test signing up for a valid activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        
        # Verify the participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_for_nonexistent_activity(self, client):
        """Test signing up for an activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Activity/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Activity not found"
    
    def test_signup_with_duplicate_email(self, client):
        """Test signing up with an email that's already registered"""
        email = "duplicate@mergington.edu"
        activity = "Drama Club"
        
        # First signup should succeed
        response1 = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Second signup with same email should fail
        response2 = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert response2.status_code == 400
        data = response2.json()
        assert "already signed up" in data["detail"]
    
    def test_signup_with_url_encoded_activity_name(self, client):
        """Test signing up with URL-encoded activity name"""
        response = client.post(
            "/activities/Soccer%20Team/signup?email=player@mergington.edu"
        )
        assert response.status_code == 200


class TestUnregisterEndpoint:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant(self, client):
        """Test unregistering an existing participant"""
        # First, add a participant
        email = "remove@mergington.edu"
        activity = "Art Studio"
        client.post(f"/activities/{activity}/signup?email={email}")
        
        # Now unregister them
        response = client.delete(
            f"/activities/{activity}/unregister?email={email}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "Unregistered" in data["message"]
        
        # Verify the participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data[activity]["participants"]
    
    def test_unregister_from_nonexistent_activity(self, client):
        """Test unregistering from an activity that doesn't exist"""
        response = client.delete(
            "/activities/Fake Activity/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Activity not found"
    
    def test_unregister_nonexistent_participant(self, client):
        """Test unregistering a participant who isn't registered"""
        response = client.delete(
            "/activities/Drama Club/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"]
    
    def test_unregister_preexisting_participant(self, client):
        """Test unregistering a participant that was in the original data"""
        # Drama Club has lily@mergington.edu and james@mergington.edu
        response = client.delete(
            "/activities/Drama Club/unregister?email=lily@mergington.edu"
        )
        assert response.status_code == 200
        
        # Verify the participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "lily@mergington.edu" not in activities_data["Drama Club"]["participants"]


class TestActivityCapacity:
    """Tests for activity capacity management"""
    
    def test_multiple_signups_increase_participant_count(self, client):
        """Test that multiple signups increase the participant count"""
        activity = "Science Olympiad"
        
        # Get initial count
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()[activity]["participants"])
        
        # Add multiple participants
        for i in range(3):
            client.post(
                f"/activities/{activity}/signup?email=student{i}@mergington.edu"
            )
        
        # Check new count
        final_response = client.get("/activities")
        final_count = len(final_response.json()[activity]["participants"])
        
        assert final_count == initial_count + 3


class TestEndToEndWorkflow:
    """End-to-end workflow tests"""
    
    def test_complete_signup_and_unregister_workflow(self, client):
        """Test a complete workflow of signup and unregister"""
        email = "workflow@mergington.edu"
        activity = "Gym Class"
        
        # Get initial state
        initial_response = client.get("/activities")
        initial_participants = initial_response.json()[activity]["participants"].copy()
        
        # Sign up
        signup_response = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert signup_response.status_code == 200
        
        # Verify signup
        after_signup = client.get("/activities")
        assert email in after_signup.json()[activity]["participants"]
        
        # Unregister
        unregister_response = client.delete(
            f"/activities/{activity}/unregister?email={email}"
        )
        assert unregister_response.status_code == 200
        
        # Verify unregister
        final_response = client.get("/activities")
        final_participants = final_response.json()[activity]["participants"]
        assert email not in final_participants
        assert final_participants == initial_participants
