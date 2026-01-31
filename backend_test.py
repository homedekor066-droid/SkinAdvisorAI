#!/usr/bin/env python3
"""
PRD Phase 1: Real Skin Analysis Engine Testing
Testing the new analysis response structure with:
1. skin_metrics: 5 metrics (tone_uniformity, texture_smoothness, hydration_appearance, pore_visibility, redness_level)
2. strengths: Array of positive aspects (2-4 items with name, description, confidence)
3. primary_concern: Object with name, severity, why_this_result
4. Enhanced issues: Now include 'why_this_result' explanation and 'priority' (primary/secondary/minor)
5. Free vs Premium Response Differences
6. Score Calculation using weighted average of skin_metrics + issue penalties
"""

import requests
import json
import base64
import os
from datetime import datetime
import time

# Get backend URL from frontend .env
BACKEND_URL = "https://ai-skin-companion.preview.emergentagent.com/api"

# Test user credentials
TEST_EMAIL = "prd_test_user@test.com"
TEST_PASSWORD = "testpass123"
TEST_NAME = "PRD Test User"

class PRDPhase1Tester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_results = []
        self.auth_token = None
        self.user_id = None
        self.scan_id = None
        
    def log_test(self, test_name, success, details="", error="", response_data=None):
        """Log test result with optional response data"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "error": error,
            "response_data": response_data,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        if error:
            print(f"   Error: {error}")
        print()

    def create_test_image(self):
        """Create a simple test image in base64 format"""
        # Create a minimal PNG image (1x1 pixel)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        return base64.b64encode(png_data).decode('utf-8')

    def test_user_registration(self):
        """Test 1: Register new test user (should start as free)"""
        try:
            # First try to delete existing user (ignore if fails)
            try:
                login_response = requests.post(f"{self.backend_url}/auth/login", json={
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD
                })
                if login_response.status_code == 200:
                    token = login_response.json()["access_token"]
                    headers = {"Authorization": f"Bearer {token}"}
                    requests.delete(f"{self.backend_url}/account", headers=headers)
            except:
                pass
            
            # Register new user
            response = requests.post(f"{self.backend_url}/auth/register", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "name": TEST_NAME,
                "language": "en"
            })
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data["access_token"]
                self.user_id = data["user"]["id"]
                
                # Verify user starts as free with scan_count=0
                if (data["user"]["plan"] == "free" and 
                    data["user"]["scan_count"] == 0):
                    self.log_test("User Registration", True, 
                                  f"User created with plan='{data['user']['plan']}', scan_count={data['user']['scan_count']}")
                    return True
                else:
                    self.log_test("User Registration", False, 
                                  f"Expected plan='free' and scan_count=0, got plan='{data['user']['plan']}', scan_count={data['user']['scan_count']}")
                    return False
            else:
                self.log_test("User Registration", False, 
                              f"Registration failed with status {response.status_code}", 
                              response.text, response.json() if response.text else None)
                return False
                
        except Exception as e:
            self.log_test("User Registration", False, "", f"Exception: {str(e)}")
            return False

    def test_free_user_scan_structure(self):
        """Test 2: Free user scan - verify new PRD Phase 1 response structure"""
        try:
            if not self.auth_token:
                self.log_test("Free User Scan Structure", False, "", "No auth token available")
                return False
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            test_image = self.create_test_image()
            
            response = requests.post(f"{self.backend_url}/scan/analyze", 
                                   headers=headers,
                                   json={
                                       "image_base64": test_image,
                                       "language": "en"
                                   })
            
            if response.status_code == 200:
                data = response.json()
                self.scan_id = data.get("id")  # Save for later tests
                
                # Extract analysis data (it's nested under 'analysis')
                analysis = data.get("analysis", {})
                
                # Check PRD Phase 1 structure for FREE users
                required_fields = ["overall_score", "score_label", "strengths", "primary_concern"]
                missing_fields = [field for field in required_fields if field not in analysis]
                
                if missing_fields:
                    self.log_test("Free User Scan Structure", False, 
                                  f"Missing required fields in analysis: {missing_fields}", "", data)
                    return False
                
                # Verify FREE user limitations
                checks = []
                
                # 1. Should have overall_score and score_label
                if "overall_score" in analysis and "score_label" in analysis:
                    checks.append("✓ Has overall_score and score_label")
                else:
                    checks.append("✗ Missing overall_score or score_label")
                
                # 2. Should have strengths (1-2 for free users)
                if "strengths" in analysis and isinstance(analysis["strengths"], list) and len(analysis["strengths"]) >= 1:
                    checks.append(f"✓ Has {len(analysis['strengths'])} strengths")
                else:
                    checks.append("✗ Missing or invalid strengths")
                
                # 3. Should have primary_concern with required fields
                if ("primary_concern" in analysis and isinstance(analysis["primary_concern"], dict) and 
                    "name" in analysis["primary_concern"]):
                    checks.append("✓ Has valid primary_concern")
                else:
                    checks.append("✗ Missing or invalid primary_concern")
                
                # 4. Should have issues_preview (locked for free users) OR locked issues
                if "issues_preview" in analysis:
                    issues_preview = analysis["issues_preview"]
                    if isinstance(issues_preview, list) and len(issues_preview) > 0:
                        first_issue = issues_preview[0]
                        if "locked" in first_issue and first_issue["locked"]:
                            checks.append("✓ Has locked issues_preview (correct for free user)")
                        else:
                            checks.append("✗ Issues_preview not properly locked")
                    else:
                        checks.append("✗ Empty issues_preview")
                elif "issues" in analysis:
                    # Check if issues are properly locked
                    issues = analysis["issues"]
                    if isinstance(issues, list) and len(issues) > 0:
                        first_issue = issues[0]
                        if "locked" in first_issue or "severity_locked" in first_issue:
                            checks.append("✓ Issues are locked for free user")
                        else:
                            checks.append("✗ Issues not properly locked for free user")
                    else:
                        checks.append("✗ No issues found")
                else:
                    checks.append("✗ Missing issues_preview or issues")
                
                # 5. Should NOT have full skin_metrics for free users
                if "skin_metrics" not in analysis:
                    checks.append("✓ No full skin_metrics (correct for free user)")
                else:
                    checks.append("✗ Has full skin_metrics (should be premium only)")
                
                # 6. Should have locked_features indicating what's locked
                if "locked_features" in data and isinstance(data["locked_features"], list):
                    locked_features = data["locked_features"]
                    if "skin_metrics" in locked_features:
                        checks.append("✓ skin_metrics properly locked for free user")
                    else:
                        checks.append("✗ skin_metrics not in locked_features")
                else:
                    checks.append("✗ Missing locked_features list")
                
                all_passed = all("✓" in check for check in checks)
                details = "; ".join(checks)
                
                self.log_test("Free User Scan Structure", all_passed, details, "", data if not all_passed else None)
                return all_passed
                
            else:
                self.log_test("Free User Scan Structure", False, 
                              f"Scan failed with status {response.status_code}", 
                              response.text, response.json() if response.text else None)
                return False
                
        except Exception as e:
            self.log_test("Free User Scan Structure", False, "", f"Exception: {str(e)}")
            return False

    def test_upgrade_to_premium(self):
        """Test 3: Upgrade user to premium"""
        try:
            if not self.auth_token:
                self.log_test("Upgrade to Premium", False, "", "No auth token available")
                return False
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            response = requests.post(f"{self.backend_url}/subscription/upgrade", 
                                   headers=headers,
                                   json={"plan": "premium"})
            
            if response.status_code == 200:
                # Verify upgrade by checking user profile
                profile_response = requests.get(f"{self.backend_url}/auth/me", headers=headers)
                
                if profile_response.status_code == 200:
                    user_data = profile_response.json()
                    if user_data["plan"] == "premium":
                        self.log_test("Upgrade to Premium", True, 
                                      f"User successfully upgraded to plan='{user_data['plan']}'")
                        return True
                    else:
                        self.log_test("Upgrade to Premium", False, 
                                      f"Expected plan='premium', got plan='{user_data['plan']}'")
                        return False
                else:
                    self.log_test("Upgrade to Premium", False, 
                                  f"Could not verify upgrade, profile check failed with status {profile_response.status_code}")
                    return False
            else:
                self.log_test("Upgrade to Premium", False, 
                              f"Upgrade failed with status {response.status_code}", 
                              response.text, response.json() if response.text else None)
                return False
                
        except Exception as e:
            self.log_test("Upgrade to Premium", False, "", f"Exception: {str(e)}")
            return False

    def test_premium_user_scan_structure(self):
        """Test 4: Premium user scan - verify full PRD Phase 1 response structure"""
        try:
            if not self.auth_token:
                self.log_test("Premium User Scan Structure", False, "", "No auth token available")
                return False
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            test_image = self.create_test_image()
            
            response = requests.post(f"{self.backend_url}/scan/analyze", 
                                   headers=headers,
                                   json={
                                       "image_base64": test_image,
                                       "language": "en"
                                   })
            
            if response.status_code == 200:
                data = response.json()
                
                # Check PRD Phase 1 structure for PREMIUM users
                checks = []
                
                # 1. Should have skin_metrics with all 5 metrics
                if "skin_metrics" in data and isinstance(data["skin_metrics"], dict):
                    expected_metrics = ["tone_uniformity", "texture_smoothness", "hydration_appearance", 
                                      "pore_visibility", "redness_level"]
                    metrics = data["skin_metrics"]
                    
                    missing_metrics = []
                    invalid_metrics = []
                    
                    for metric in expected_metrics:
                        if metric not in metrics:
                            missing_metrics.append(metric)
                        else:
                            metric_data = metrics[metric]
                            if (not isinstance(metric_data, dict) or 
                                "score" not in metric_data or 
                                "why" not in metric_data):
                                invalid_metrics.append(metric)
                    
                    if not missing_metrics and not invalid_metrics:
                        checks.append(f"✓ Has all 5 skin_metrics with score and 'why'")
                    else:
                        error_details = []
                        if missing_metrics:
                            error_details.append(f"missing: {missing_metrics}")
                        if invalid_metrics:
                            error_details.append(f"invalid: {invalid_metrics}")
                        checks.append(f"✗ Skin metrics issues: {'; '.join(error_details)}")
                else:
                    checks.append("✗ Missing or invalid skin_metrics")
                
                # 2. Should have strengths (2-4 items for premium)
                if "strengths" in data and isinstance(data["strengths"], list):
                    strengths = data["strengths"]
                    if len(strengths) >= 2:
                        # Check structure of first strength
                        if (len(strengths) > 0 and isinstance(strengths[0], dict) and 
                            "name" in strengths[0] and "description" in strengths[0] and 
                            "confidence" in strengths[0]):
                            checks.append(f"✓ Has {len(strengths)} well-structured strengths")
                        else:
                            checks.append(f"✗ Strengths missing required fields (name, description, confidence)")
                    else:
                        checks.append(f"✗ Only {len(strengths)} strengths (expected 2-4)")
                else:
                    checks.append("✗ Missing or invalid strengths")
                
                # 3. Should have enhanced issues with 'why_this_result' and 'priority'
                if "issues" in data and isinstance(data["issues"], list) and len(data["issues"]) > 0:
                    issues = data["issues"]
                    first_issue = issues[0]
                    
                    required_issue_fields = ["name", "severity", "description", "why_this_result", "priority"]
                    missing_issue_fields = [field for field in required_issue_fields if field not in first_issue]
                    
                    if not missing_issue_fields:
                        checks.append(f"✓ Has {len(issues)} enhanced issues with all required fields")
                    else:
                        checks.append(f"✗ Issues missing fields: {missing_issue_fields}")
                else:
                    checks.append("✗ Missing or empty issues array")
                
                # 4. Should have primary_concern with why_this_result
                if ("primary_concern" in data and isinstance(data["primary_concern"], dict) and 
                    "name" in data["primary_concern"] and "severity" in data["primary_concern"] and
                    "why_this_result" in data["primary_concern"]):
                    checks.append("✓ Has complete primary_concern with why_this_result")
                else:
                    checks.append("✗ Missing or incomplete primary_concern")
                
                # 5. Should have overall scoring information
                if "overall_score" in data and "score_label" in data:
                    checks.append("✓ Has overall scoring information")
                else:
                    checks.append("✗ Missing overall scoring information")
                
                # 6. Should NOT have issues_preview (that's for free users)
                if "issues_preview" not in data:
                    checks.append("✓ No issues_preview (correct for premium user)")
                else:
                    checks.append("✗ Has issues_preview (should be free user only)")
                
                all_passed = all("✓" in check for check in checks)
                details = "; ".join(checks)
                
                self.log_test("Premium User Scan Structure", all_passed, details, "", data if not all_passed else None)
                return all_passed
                
            else:
                self.log_test("Premium User Scan Structure", False, 
                              f"Scan failed with status {response.status_code}", 
                              response.text, response.json() if response.text else None)
                return False
                
        except Exception as e:
            self.log_test("Premium User Scan Structure", False, "", f"Exception: {str(e)}")
            return False

    def test_score_calculation_method(self):
        """Test 5: Verify new score calculation uses skin_metrics"""
        try:
            if not self.auth_token:
                self.log_test("Score Calculation Method", False, "", "No auth token available")
                return False
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            test_image = self.create_test_image()
            
            response = requests.post(f"{self.backend_url}/scan/analyze", 
                                   headers=headers,
                                   json={
                                       "image_base64": test_image,
                                       "language": "en"
                                   })
            
            if response.status_code == 200:
                data = response.json()
                
                checks = []
                
                # Check if score is calculated from metrics
                if "skin_metrics" in data and "overall_score" in data:
                    metrics = data["skin_metrics"]
                    overall_score = data["overall_score"]
                    
                    # Calculate expected score from metrics (weighted average)
                    metric_weights = {
                        'tone_uniformity': 0.25,
                        'texture_smoothness': 0.25,
                        'hydration_appearance': 0.20,
                        'pore_visibility': 0.15,
                        'redness_level': 0.15
                    }
                    
                    calculated_base = 0
                    total_weight = 0
                    
                    for metric_name, weight in metric_weights.items():
                        if metric_name in metrics:
                            score = metrics[metric_name].get('score', 70)
                            calculated_base += score * weight
                            total_weight += weight
                    
                    if total_weight > 0:
                        expected_base = calculated_base / total_weight
                        
                        # Score should be reasonably close to metrics-based calculation
                        # (allowing for issue penalties)
                        if abs(overall_score - expected_base) <= 20:  # Allow for issue deductions
                            checks.append(f"✓ Score ({overall_score}) reasonably derived from metrics (base ~{expected_base:.1f})")
                        else:
                            checks.append(f"✗ Score ({overall_score}) too far from metrics base ({expected_base:.1f})")
                    else:
                        checks.append("✗ Could not calculate expected score from metrics")
                else:
                    checks.append("✗ Missing skin_metrics or overall_score")
                
                # Check score is in reasonable range (PRD goal: most users 70-84)
                if "overall_score" in data:
                    score = data["overall_score"]
                    if 60 <= score <= 90:  # Reasonable range
                        checks.append(f"✓ Score ({score}) in reasonable range")
                    else:
                        checks.append(f"✗ Score ({score}) outside reasonable range (60-90)")
                
                all_passed = all("✓" in check for check in checks)
                details = "; ".join(checks)
                
                self.log_test("Score Calculation Method", all_passed, details)
                return all_passed
                
            else:
                self.log_test("Score Calculation Method", False, 
                              f"Scan failed with status {response.status_code}", 
                              response.text, response.json() if response.text else None)
                return False
                
        except Exception as e:
            self.log_test("Score Calculation Method", False, "", f"Exception: {str(e)}")
            return False

    def test_scan_history_endpoint(self):
        """Test 6: Verify scan history endpoint returns PRD Phase 1 structure"""
        try:
            if not self.auth_token or not self.scan_id:
                self.log_test("Scan History Endpoint", False, "", "No auth token or scan_id available")
                return False
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            response = requests.get(f"{self.backend_url}/scan/{self.scan_id}", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                checks = []
                
                # Should have same structure as analyze endpoint for premium user
                if "skin_metrics" in data:
                    checks.append("✓ Has skin_metrics in history")
                else:
                    checks.append("✗ Missing skin_metrics in history")
                
                if "strengths" in data and isinstance(data["strengths"], list):
                    checks.append(f"✓ Has {len(data['strengths'])} strengths in history")
                else:
                    checks.append("✗ Missing strengths in history")
                
                if "issues" in data and isinstance(data["issues"], list):
                    checks.append(f"✓ Has {len(data['issues'])} issues in history")
                else:
                    checks.append("✗ Missing issues in history")
                
                if "primary_concern" in data:
                    checks.append("✓ Has primary_concern in history")
                else:
                    checks.append("✗ Missing primary_concern in history")
                
                all_passed = all("✓" in check for check in checks)
                details = "; ".join(checks)
                
                self.log_test("Scan History Endpoint", all_passed, details)
                return all_passed
                
            else:
                self.log_test("Scan History Endpoint", False, 
                              f"History request failed with status {response.status_code}", 
                              response.text)
                return False
                
        except Exception as e:
            self.log_test("Scan History Endpoint", False, "", f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all PRD Phase 1 tests"""
        print("🧪 PRD Phase 1: Real Skin Analysis Engine Testing")
        print("=" * 60)
        print(f"Backend URL: {self.backend_url}")
        print(f"Test User: {TEST_EMAIL}")
        print()
        
        # Test sequence
        tests = [
            ("User Registration", self.test_user_registration),
            ("Free User Scan Structure", self.test_free_user_scan_structure),
            ("Upgrade to Premium", self.test_upgrade_to_premium),
            ("Premium User Scan Structure", self.test_premium_user_scan_structure),
            ("Score Calculation Method", self.test_score_calculation_method),
            ("Scan History Endpoint", self.test_scan_history_endpoint)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            if test_func():
                passed += 1
        
        print("=" * 60)
        print(f"📊 TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED - PRD Phase 1 implementation is working correctly!")
        else:
            print(f"⚠️  {total - passed} tests failed - see details above")
        
        # Save detailed results
        with open('/app/prd_phase1_test_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': total,
                    'passed': passed,
                    'failed': total - passed,
                    'success_rate': f"{(passed/total)*100:.1f}%"
                },
                'test_results': self.test_results
            }, f, indent=2)
        
        print(f"📄 Detailed results saved to: /app/prd_phase1_test_results.json")
        
        return passed == total

if __name__ == "__main__":
    tester = PRDPhase1Tester()
    success = tester.run_all_tests()
    exit(0 if success else 1)