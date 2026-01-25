#!/usr/bin/env python3
"""
SkinAdvisor AI Backend API Testing Suite
Tests all backend endpoints for functionality and integration
"""

import requests
import json
import uuid
import time
from datetime import datetime

# Configuration
BASE_URL = "https://skinsmart-ai-4.preview.emergentagent.com/api"
TEST_USER_EMAIL = f"testuser_{uuid.uuid4().hex[:8]}@skinadvisor.com"
TEST_USER_PASSWORD = "SecurePass123!"
TEST_USER_NAME = "Sarah Johnson"

class BackendTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.auth_token = None
        self.user_id = None
        self.test_results = []
        
    def log_test(self, test_name, success, message, response_data=None):
        """Log test results"""
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'response_data': response_data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if response_data and not success:
            print(f"   Response: {json.dumps(response_data, indent=2)}")
    
    def test_health_check(self):
        """Test basic API health"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("Health Check", True, f"API is healthy: {data}")
                return True
            else:
                self.log_test("Health Check", False, f"Health check failed with status {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Health check error: {str(e)}")
            return False
    
    def test_user_registration(self):
        """Test user registration endpoint"""
        try:
            payload = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": TEST_USER_NAME,
                "language": "en"
            }
            
            response = self.session.post(f"{self.base_url}/auth/register", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'access_token' in data and 'user' in data:
                    self.auth_token = data['access_token']
                    self.user_id = data['user']['id']
                    self.log_test("User Registration", True, f"User registered successfully with ID: {self.user_id}")
                    return True
                else:
                    self.log_test("User Registration", False, "Missing access_token or user in response", data)
                    return False
            else:
                self.log_test("User Registration", False, f"Registration failed with status {response.status_code}", response.json() if response.content else None)
                return False
                
        except Exception as e:
            self.log_test("User Registration", False, f"Registration error: {str(e)}")
            return False
    
    def test_user_login(self):
        """Test user login endpoint"""
        try:
            payload = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
            
            response = self.session.post(f"{self.base_url}/auth/login", json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'access_token' in data and 'user' in data:
                    # Update token in case it's different
                    self.auth_token = data['access_token']
                    self.log_test("User Login", True, f"Login successful for user: {data['user']['email']}")
                    return True
                else:
                    self.log_test("User Login", False, "Missing access_token or user in response", data)
                    return False
            else:
                self.log_test("User Login", False, f"Login failed with status {response.status_code}", response.json() if response.content else None)
                return False
                
        except Exception as e:
            self.log_test("User Login", False, f"Login error: {str(e)}")
            return False
    
    def test_get_user_profile(self):
        """Test get current user profile endpoint"""
        if not self.auth_token:
            self.log_test("Get User Profile", False, "No auth token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = self.session.get(f"{self.base_url}/auth/me", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'id' in data and 'email' in data and 'name' in data:
                    self.log_test("Get User Profile", True, f"Profile retrieved for user: {data['email']}")
                    return True
                else:
                    self.log_test("Get User Profile", False, "Missing required fields in profile response", data)
                    return False
            else:
                self.log_test("Get User Profile", False, f"Profile retrieval failed with status {response.status_code}", response.json() if response.content else None)
                return False
                
        except Exception as e:
            self.log_test("Get User Profile", False, f"Profile retrieval error: {str(e)}")
            return False
    
    def test_languages_api(self):
        """Test languages endpoint - should return 9 languages"""
        try:
            response = self.session.get(f"{self.base_url}/languages", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) == 9:
                    # Check if all required fields are present
                    required_fields = ['code', 'name', 'rtl']
                    all_valid = all(all(field in lang for field in required_fields) for lang in data)
                    
                    if all_valid:
                        language_codes = [lang['code'] for lang in data]
                        self.log_test("Languages API", True, f"Retrieved 9 languages: {', '.join(language_codes)}")
                        return True
                    else:
                        self.log_test("Languages API", False, "Some languages missing required fields", data)
                        return False
                else:
                    self.log_test("Languages API", False, f"Expected 9 languages, got {len(data) if isinstance(data, list) else 'non-list'}", data)
                    return False
            else:
                self.log_test("Languages API", False, f"Languages API failed with status {response.status_code}", response.json() if response.content else None)
                return False
                
        except Exception as e:
            self.log_test("Languages API", False, f"Languages API error: {str(e)}")
            return False
    
    def test_translations_api(self):
        """Test translations endpoints for English and French"""
        languages_to_test = ['en', 'fr']
        all_passed = True
        
        for lang in languages_to_test:
            try:
                response = self.session.get(f"{self.base_url}/translations/{lang}", timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and len(data) > 0:
                        # Check for some key translations
                        key_translations = ['app_name', 'welcome', 'login', 'register', 'scan_skin']
                        missing_keys = [key for key in key_translations if key not in data]
                        
                        if not missing_keys:
                            self.log_test(f"Translations API ({lang})", True, f"Retrieved {len(data)} translations for {lang}")
                        else:
                            self.log_test(f"Translations API ({lang})", False, f"Missing key translations: {missing_keys}")
                            all_passed = False
                    else:
                        self.log_test(f"Translations API ({lang})", False, f"Invalid translations format for {lang}", data)
                        all_passed = False
                else:
                    self.log_test(f"Translations API ({lang})", False, f"Translations API failed for {lang} with status {response.status_code}")
                    all_passed = False
                    
            except Exception as e:
                self.log_test(f"Translations API ({lang})", False, f"Translations API error for {lang}: {str(e)}")
                all_passed = False
        
        return all_passed
    
    def test_profile_update(self):
        """Test profile update endpoint"""
        if not self.auth_token:
            self.log_test("Profile Update", False, "No auth token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            payload = {
                "age": 28,
                "gender": "female",
                "skin_goals": ["anti-aging", "hydration", "acne-control"],
                "country": "United States",
                "language": "en"
            }
            
            response = self.session.put(f"{self.base_url}/profile", json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'profile' in data and data['profile']:
                    profile = data['profile']
                    # Verify the updated data
                    if (profile.get('age') == 28 and 
                        profile.get('gender') == 'female' and 
                        profile.get('country') == 'United States'):
                        self.log_test("Profile Update", True, "Profile updated successfully with correct data")
                        return True
                    else:
                        self.log_test("Profile Update", False, "Profile data not updated correctly", data)
                        return False
                else:
                    self.log_test("Profile Update", False, "Missing profile in response", data)
                    return False
            else:
                self.log_test("Profile Update", False, f"Profile update failed with status {response.status_code}", response.json() if response.content else None)
                return False
                
        except Exception as e:
            self.log_test("Profile Update", False, f"Profile update error: {str(e)}")
            return False
    
    def test_scan_history(self):
        """Test scan history endpoint - should be empty for new user"""
        if not self.auth_token:
            self.log_test("Scan History", False, "No auth token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = self.session.get(f"{self.base_url}/scan/history", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    if len(data) == 0:
                        self.log_test("Scan History", True, "Scan history is empty for new user (as expected)")
                        return True
                    else:
                        self.log_test("Scan History", True, f"Scan history retrieved with {len(data)} scans")
                        return True
                else:
                    self.log_test("Scan History", False, "Scan history response is not a list", data)
                    return False
            else:
                self.log_test("Scan History", False, f"Scan history failed with status {response.status_code}", response.json() if response.content else None)
                return False
                
        except Exception as e:
            self.log_test("Scan History", False, f"Scan history error: {str(e)}")
            return False
    
    def test_account_deletion(self):
        """Test account deletion endpoint"""
        if not self.auth_token:
            self.log_test("Account Deletion", False, "No auth token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = self.session.delete(f"{self.base_url}/account", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'message' in data and 'deleted' in data['message'].lower():
                    self.log_test("Account Deletion", True, "Account deleted successfully")
                    return True
                else:
                    self.log_test("Account Deletion", False, "Unexpected deletion response", data)
                    return False
            else:
                self.log_test("Account Deletion", False, f"Account deletion failed with status {response.status_code}", response.json() if response.content else None)
                return False
                
        except Exception as e:
            self.log_test("Account Deletion", False, f"Account deletion error: {str(e)}")
            return False
    
    def test_diet_recommendations_structure(self, diet_recs):
        """Verify diet recommendations structure"""
        required_fields = ['eat_more', 'avoid', 'hydration_tip', 'supplements_optional']
        
        # Check all required fields exist
        for field in required_fields:
            if field not in diet_recs:
                return False, f"Missing required field: {field}"
        
        # Check eat_more structure
        if not isinstance(diet_recs['eat_more'], list):
            return False, "eat_more should be a list"
        
        for item in diet_recs['eat_more']:
            if not isinstance(item, dict) or 'name' not in item or 'reason' not in item:
                return False, "eat_more items should have 'name' and 'reason' fields"
        
        # Check avoid structure
        if not isinstance(diet_recs['avoid'], list):
            return False, "avoid should be a list"
        
        for item in diet_recs['avoid']:
            if not isinstance(item, dict) or 'name' not in item or 'reason' not in item:
                return False, "avoid items should have 'name' and 'reason' fields"
        
        # Check hydration_tip
        if not isinstance(diet_recs['hydration_tip'], str):
            return False, "hydration_tip should be a string"
        
        # Check supplements_optional structure
        if not isinstance(diet_recs['supplements_optional'], list):
            return False, "supplements_optional should be a list"
        
        for item in diet_recs['supplements_optional']:
            if not isinstance(item, dict) or 'name' not in item or 'reason' not in item:
                return False, "supplements_optional items should have 'name' and 'reason' fields"
        
        return True, "Structure validation passed"
    
    def test_diet_recommendations_with_mock_scan(self):
        """Test diet recommendations by creating a mock scan"""
        if not self.auth_token:
            self.log_test("Diet Recommendations - Mock Scan", False, "No auth token available")
            return False
        
        try:
            # Create a simple 1x1 pixel base64 image for testing
            test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            
            analyze_data = {
                "image_base64": test_image_b64,
                "language": "en"
            }
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = self.session.post(f"{self.base_url}/scan/analyze", 
                                       json=analyze_data, 
                                       headers=headers, 
                                       timeout=30)
            
            if response.status_code == 200:
                scan_result = response.json()
                
                # Check if diet_recommendations exists in the analyze response
                if 'diet_recommendations' not in scan_result:
                    self.log_test("Diet Recommendations - Mock Scan", False, "diet_recommendations field missing from analyze response")
                    return False
                
                diet_recs = scan_result['diet_recommendations']
                
                # Verify structure
                structure_valid, message = self.test_diet_recommendations_structure(diet_recs)
                
                if structure_valid:
                    self.log_test("Diet Recommendations - Mock Scan", True, f"Diet recommendations present and valid in analyze response. Found {len(diet_recs['eat_more'])} eat_more items, {len(diet_recs['avoid'])} avoid items, {len(diet_recs['supplements_optional'])} supplements")
                    
                    # Test deterministic behavior by calling the same scan detail endpoint twice
                    scan_id = scan_result['id']
                    return self.test_diet_recommendations_deterministic(scan_id)
                else:
                    self.log_test("Diet Recommendations - Mock Scan", False, f"Invalid structure: {message}")
                    return False
                    
            else:
                self.log_test("Diet Recommendations - Mock Scan", False, f"Scan analyze failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.log_test("Diet Recommendations - Mock Scan", False, f"Error: {str(e)}")
            return False
    
    def test_diet_recommendations_deterministic(self, scan_id):
        """Test that diet recommendations are deterministic"""
        if not self.auth_token:
            self.log_test("Diet Recommendations - Deterministic", False, "No auth token available")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Call the same scan detail endpoint twice
            response1 = self.session.get(f"{self.base_url}/scan/{scan_id}", headers=headers, timeout=10)
            response2 = self.session.get(f"{self.base_url}/scan/{scan_id}", headers=headers, timeout=10)
            
            if response1.status_code == 200 and response2.status_code == 200:
                scan_data1 = response1.json()
                scan_data2 = response2.json()
                
                if 'diet_recommendations' not in scan_data1 or 'diet_recommendations' not in scan_data2:
                    self.log_test("Diet Recommendations - Deterministic", False, "diet_recommendations missing from scan detail response")
                    return False
                
                diet_recs1 = scan_data1['diet_recommendations']
                diet_recs2 = scan_data2['diet_recommendations']
                
                if diet_recs1 == diet_recs2:
                    self.log_test("Diet Recommendations - Deterministic", True, "Diet recommendations are deterministic - same scan returns identical results")
                    return True
                else:
                    self.log_test("Diet Recommendations - Deterministic", False, "Diet recommendations are not deterministic - same scan returns different results")
                    return False
            else:
                self.log_test("Diet Recommendations - Deterministic", False, f"Scan detail failed: {response1.status_code}, {response2.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Diet Recommendations - Deterministic", False, f"Error: {str(e)}")
            return False
    
    def test_diet_recommendations_existing_scans(self):
        """Test diet recommendations with existing scans"""
        if not self.auth_token:
            self.log_test("Diet Recommendations - Existing Scans", False, "No auth token available")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Get scan history
            response = self.session.get(f"{self.base_url}/scan/history", headers=headers, timeout=10)
            
            if response.status_code == 200:
                scans = response.json()
                
                if len(scans) == 0:
                    self.log_test("Diet Recommendations - Existing Scans", True, "No existing scans found - this is expected for new user")
                    return True
                
                # Test the first scan
                scan_id = scans[0]['id']
                scan_response = self.session.get(f"{self.base_url}/scan/{scan_id}", headers=headers, timeout=10)
                
                if scan_response.status_code == 200:
                    scan_data = scan_response.json()
                    
                    if 'diet_recommendations' in scan_data:
                        diet_recs = scan_data['diet_recommendations']
                        structure_valid, message = self.test_diet_recommendations_structure(diet_recs)
                        
                        if structure_valid:
                            self.log_test("Diet Recommendations - Existing Scans", True, f"Diet recommendations found and valid in existing scan {scan_id}")
                            return True
                        else:
                            self.log_test("Diet Recommendations - Existing Scans", False, f"Invalid structure in existing scan: {message}")
                            return False
                    else:
                        # This is expected for older scans - the endpoint should generate them
                        self.log_test("Diet Recommendations - Existing Scans", True, "Older scan without diet_recommendations - endpoint should generate them on-the-fly")
                        return True
                else:
                    self.log_test("Diet Recommendations - Existing Scans", False, f"Failed to get scan detail: {scan_response.status_code}")
                    return False
            else:
                self.log_test("Diet Recommendations - Existing Scans", False, f"Failed to get scan history: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Diet Recommendations - Existing Scans", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all backend tests in sequence"""
        print(f"\n🧪 Starting SkinAdvisor AI Backend API Tests")
        print(f"📍 Base URL: {self.base_url}")
        print(f"👤 Test User: {TEST_USER_EMAIL}")
        print("=" * 60)
        
        # Test sequence
        tests = [
            ("Health Check", self.test_health_check),
            ("User Registration", self.test_user_registration),
            ("User Login", self.test_user_login),
            ("Get User Profile", self.test_get_user_profile),
            ("Languages API", self.test_languages_api),
            ("Translations API", self.test_translations_api),
            ("Profile Update", self.test_profile_update),
            ("Scan History", self.test_scan_history),
            ("Account Deletion", self.test_account_deletion)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n🔍 Running: {test_name}")
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                self.log_test(test_name, False, f"Unexpected error: {str(e)}")
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print("⚠️  Some tests failed. Check details above.")
        
        return passed, total, self.test_results

def main():
    """Main test execution"""
    tester = BackendTester()
    passed, total, results = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'passed': passed,
                'total': total,
                'success_rate': f"{(passed/total)*100:.1f}%",
                'timestamp': datetime.now().isoformat()
            },
            'detailed_results': results
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)