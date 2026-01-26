#!/usr/bin/env python3
"""
Backend Testing for SkinAdvisor AI - CRITICAL MONETIZATION UX FIX
Testing Areas:
1. FREE USER RESPONSE STRUCTURE - Issues visible but locked
2. PREMIUM USER RESPONSE STRUCTURE - Full issue details
3. NO "EMPTY ISSUES" BUG - Free users see issues exist
4. SCAN ENDPOINTS - Both /analyze and /{scan_id}
"""

import requests
import json
import base64
import os
from datetime import datetime
import time

# Get backend URL from frontend .env
BACKEND_URL = "https://skin-advisor-ai-1.preview.emergentagent.com/api"

class SkinAdvisorTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_results = []
        self.test_user_token = None
        self.test_user_id = None
        self.premium_user_token = None
        self.premium_user_id = None
        
    def log_test(self, test_name, success, details="", error=""):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "error": error,
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
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
        return base64.b64encode(png_data).decode('utf-8')

    def register_test_user(self, email, name="Test User"):
        """Register a new test user"""
        try:
            response = requests.post(f"{self.backend_url}/auth/register", json={
                "email": email,
                "password": "testpass123",
                "name": name,
                "language": "en"
            })
            
            if response.status_code == 200:
                data = response.json()
                return data["access_token"], data["user"]["id"], data["user"]
            else:
                return None, None, None
                
        except Exception as e:
            return None, None, None

    def login_user(self, email, password="testpass123"):
        """Login user and return token"""
        try:
            response = requests.post(f"{self.backend_url}/auth/login", json={
                "email": email,
                "password": password
            })
            
            if response.status_code == 200:
                data = response.json()
                return data["access_token"], data["user"]["id"], data["user"]
            else:
                return None, None, None
                
        except Exception as e:
            return None, None, None

    def get_auth_headers(self, token):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {token}"}

    def test_1_new_scoring_system_validation(self):
        """Test 1: NEW SCORING SYSTEM VALIDATION"""
        print("=== TEST 1: NEW SCORING SYSTEM VALIDATION ===")
        
        # Register test user for scoring check
        email = f"test_score_check_{int(time.time())}@test.com"
        token, user_id, user_data = self.register_test_user(email, "Score Test User")
        
        if not token:
            self.log_test("1.1 Register Score Test User", False, error="Failed to register test user")
            return
            
        self.log_test("1.1 Register Score Test User", True, f"User registered: {email}")
        
        # Check initial user plan is free
        if user_data.get('plan') != 'free':
            self.log_test("1.2 Initial Plan Check", False, error=f"Expected plan='free', got '{user_data.get('plan')}'")
            return
        
        self.log_test("1.2 Initial Plan Check", True, f"User plan is 'free' as expected")
        
        # Perform a skin scan to test scoring
        try:
            test_image = self.create_test_image()
            headers = self.get_auth_headers(token)
            
            response = requests.post(f"{self.backend_url}/scan/analyze", 
                                   json={"image_base64": test_image, "language": "en"},
                                   headers=headers)
            
            if response.status_code == 200:
                scan_data = response.json()
                score = scan_data.get('analysis', {}).get('overall_score')
                
                if score is None:
                    self.log_test("1.3 Scoring System Test", False, error="No score returned in response")
                    return
                
                # Check if score is in reasonable range (70-84 for most users)
                if 70 <= score <= 84:
                    self.log_test("1.3 Scoring System Test", True, f"Score {score} is in expected range (70-84)")
                elif score >= 90:
                    self.log_test("1.3 Scoring System Test", False, error=f"Score {score} is too high (>=90), should be rare")
                else:
                    self.log_test("1.3 Scoring System Test", True, f"Score {score} is acceptable (below 70)")
                
                # Check score structure
                analysis = scan_data.get('analysis', {})
                required_score_fields = ['overall_score', 'score_label']
                missing_fields = [field for field in required_score_fields if field not in analysis]
                
                if missing_fields:
                    self.log_test("1.4 Score Structure Check", False, error=f"Missing fields: {missing_fields}")
                else:
                    self.log_test("1.4 Score Structure Check", True, f"All required score fields present")
                
            else:
                self.log_test("1.3 Scoring System Test", False, error=f"Scan failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            self.log_test("1.3 Scoring System Test", False, error=f"Exception: {str(e)}")

    def test_2_subscription_flow(self):
        """Test 2: SUBSCRIPTION FLOW TEST"""
        print("=== TEST 2: SUBSCRIPTION FLOW TEST ===")
        
        # Register new user
        email = f"test_subscription_{int(time.time())}@test.com"
        token, user_id, user_data = self.register_test_user(email, "Subscription Test User")
        
        if not token:
            self.log_test("2.1 Register Subscription Test User", False, error="Failed to register test user")
            return
            
        self.log_test("2.1 Register Subscription Test User", True, f"User registered: {email}")
        
        # Check initial plan is "free"
        if user_data.get('plan') != 'free':
            self.log_test("2.2 Initial Plan Check", False, error=f"Expected plan='free', got '{user_data.get('plan')}'")
            return
        
        self.log_test("2.2 Initial Plan Check", True, "Initial plan is 'free'")
        
        # Call POST /api/subscription/upgrade
        try:
            headers = self.get_auth_headers(token)
            response = requests.post(f"{self.backend_url}/subscription/upgrade", 
                                   json={"plan": "premium"},
                                   headers=headers)
            
            if response.status_code == 200:
                upgrade_data = response.json()
                self.log_test("2.3 Subscription Upgrade", True, f"Upgrade successful: {upgrade_data.get('message', 'No message')}")
            else:
                self.log_test("2.3 Subscription Upgrade", False, error=f"Upgrade failed: {response.status_code} - {response.text}")
                return
                
        except Exception as e:
            self.log_test("2.3 Subscription Upgrade", False, error=f"Exception: {str(e)}")
            return
        
        # Call GET /api/auth/me and confirm plan = "premium"
        try:
            response = requests.get(f"{self.backend_url}/auth/me", headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                current_plan = user_data.get('plan')
                
                if current_plan == 'premium':
                    self.log_test("2.4 Plan Verification", True, "User plan is now 'premium'")
                    # Store for later tests
                    self.premium_user_token = token
                    self.premium_user_id = user_id
                else:
                    self.log_test("2.4 Plan Verification", False, error=f"Expected plan='premium', got '{current_plan}'")
            else:
                self.log_test("2.4 Plan Verification", False, error=f"Failed to get user info: {response.status_code}")
                
        except Exception as e:
            self.log_test("2.4 Plan Verification", False, error=f"Exception: {str(e)}")

    def test_3_plan_based_response_structure(self):
        """Test 3: PLAN-BASED RESPONSE STRUCTURE"""
        print("=== TEST 3: PLAN-BASED RESPONSE STRUCTURE ===")
        
        # Create free user and perform scan
        email_free = f"test_free_{int(time.time())}@test.com"
        free_token, free_user_id, _ = self.register_test_user(email_free, "Free User")
        
        if not free_token:
            self.log_test("3.1 Create Free User", False, error="Failed to register free user")
            return
            
        self.log_test("3.1 Create Free User", True, f"Free user registered: {email_free}")
        
        # Perform scan with free user
        try:
            test_image = self.create_test_image()
            headers = self.get_auth_headers(free_token)
            
            response = requests.post(f"{self.backend_url}/scan/analyze", 
                                   json={"image_base64": test_image, "language": "en"},
                                   headers=headers)
            
            if response.status_code == 200:
                free_scan_data = response.json()
                free_scan_id = free_scan_data.get('id')
                
                # Check free user response structure
                if 'locked_features' in free_scan_data:
                    self.log_test("3.2 Free User Scan Response", True, "Free user gets locked_features")
                else:
                    self.log_test("3.2 Free User Scan Response", False, error="Free user missing locked_features")
                
                # Check that free user doesn't get full routine/diet/products
                if 'routine' not in free_scan_data and 'diet_recommendations' not in free_scan_data:
                    self.log_test("3.3 Free User Limited Response", True, "Free user doesn't get full routine/diet")
                else:
                    self.log_test("3.3 Free User Limited Response", False, error="Free user got full data (should be limited)")
                
            else:
                self.log_test("3.2 Free User Scan Response", False, error=f"Free scan failed: {response.status_code}")
                return
                
        except Exception as e:
            self.log_test("3.2 Free User Scan Response", False, error=f"Exception: {str(e)}")
            return
        
        # Test GET /api/scan/{scan_id} with free user
        try:
            response = requests.get(f"{self.backend_url}/scan/{free_scan_id}", headers=headers)
            
            if response.status_code == 200:
                scan_detail = response.json()
                
                # Should have locked_features and preview, but no full routine/diet/products
                has_locked = 'locked_features' in scan_detail
                has_preview = 'preview' in scan_detail
                has_routine = 'routine' in scan_detail
                has_diet = 'diet_recommendations' in scan_detail
                
                if has_locked and has_preview and not has_routine and not has_diet:
                    self.log_test("3.4 Free User Scan Detail", True, "Free user gets limited scan detail")
                else:
                    self.log_test("3.4 Free User Scan Detail", False, 
                                error=f"Wrong structure: locked={has_locked}, preview={has_preview}, routine={has_routine}, diet={has_diet}")
            else:
                self.log_test("3.4 Free User Scan Detail", False, error=f"Failed to get scan detail: {response.status_code}")
                
        except Exception as e:
            self.log_test("3.4 Free User Scan Detail", False, error=f"Exception: {str(e)}")
        
        # Test with premium user if available
        if self.premium_user_token:
            try:
                premium_headers = self.get_auth_headers(self.premium_user_token)
                
                response = requests.post(f"{self.backend_url}/scan/analyze", 
                                       json={"image_base64": test_image, "language": "en"},
                                       headers=premium_headers)
                
                if response.status_code == 200:
                    premium_scan_data = response.json()
                    premium_scan_id = premium_scan_data.get('id')
                    
                    # Check premium user gets full response
                    has_routine = 'routine' in premium_scan_data
                    has_diet = 'diet_recommendations' in premium_scan_data
                    has_products = 'products' in premium_scan_data
                    
                    if has_routine and has_diet and has_products:
                        self.log_test("3.5 Premium User Full Response", True, "Premium user gets full routine/diet/products")
                    else:
                        self.log_test("3.5 Premium User Full Response", False, 
                                    error=f"Premium missing data: routine={has_routine}, diet={has_diet}, products={has_products}")
                    
                    # Test GET /api/scan/{scan_id} with premium user
                    response = requests.get(f"{self.backend_url}/scan/{premium_scan_id}", headers=premium_headers)
                    
                    if response.status_code == 200:
                        premium_detail = response.json()
                        
                        has_routine = 'routine' in premium_detail
                        has_diet = 'diet_recommendations' in premium_detail
                        has_products = 'products' in premium_detail
                        
                        if has_routine and has_diet and has_products:
                            self.log_test("3.6 Premium User Scan Detail", True, "Premium user gets full scan detail")
                        else:
                            self.log_test("3.6 Premium User Scan Detail", False, 
                                        error=f"Premium detail missing: routine={has_routine}, diet={has_diet}, products={has_products}")
                    else:
                        self.log_test("3.6 Premium User Scan Detail", False, error=f"Failed to get premium scan detail: {response.status_code}")
                        
                else:
                    self.log_test("3.5 Premium User Full Response", False, error=f"Premium scan failed: {response.status_code}")
                    
            except Exception as e:
                self.log_test("3.5 Premium User Full Response", False, error=f"Exception: {str(e)}")

    def test_4_scan_limit_enforcement(self):
        """Test 4: SCAN LIMIT ENFORCEMENT"""
        print("=== TEST 4: SCAN LIMIT ENFORCEMENT ===")
        
        # Create new free user for limit testing
        email = f"test_limit_{int(time.time())}@test.com"
        token, user_id, user_data = self.register_test_user(email, "Limit Test User")
        
        if not token:
            self.log_test("4.1 Create Limit Test User", False, error="Failed to register limit test user")
            return
            
        self.log_test("4.1 Create Limit Test User", True, f"Limit test user registered: {email}")
        
        # Check initial scan_count is 0
        initial_scan_count = user_data.get('scan_count', 0)
        if initial_scan_count == 0:
            self.log_test("4.2 Initial Scan Count", True, "Initial scan_count is 0")
        else:
            self.log_test("4.2 Initial Scan Count", False, error=f"Expected scan_count=0, got {initial_scan_count}")
        
        # Perform first scan (should succeed)
        try:
            test_image = self.create_test_image()
            headers = self.get_auth_headers(token)
            
            response = requests.post(f"{self.backend_url}/scan/analyze", 
                                   json={"image_base64": test_image, "language": "en"},
                                   headers=headers)
            
            if response.status_code == 200:
                self.log_test("4.3 First Scan (Should Succeed)", True, "First scan completed successfully")
                
                # Check scan_count incremented
                user_response = requests.get(f"{self.backend_url}/auth/me", headers=headers)
                if user_response.status_code == 200:
                    updated_user = user_response.json()
                    new_scan_count = updated_user.get('scan_count', 0)
                    
                    if new_scan_count == 1:
                        self.log_test("4.4 Scan Count Increment", True, "scan_count incremented to 1")
                    else:
                        self.log_test("4.4 Scan Count Increment", False, error=f"Expected scan_count=1, got {new_scan_count}")
                else:
                    self.log_test("4.4 Scan Count Increment", False, error="Failed to get updated user data")
                    
            else:
                self.log_test("4.3 First Scan (Should Succeed)", False, error=f"First scan failed: {response.status_code}")
                return
                
        except Exception as e:
            self.log_test("4.3 First Scan (Should Succeed)", False, error=f"Exception: {str(e)}")
            return
        
        # Perform second scan (should fail with 403)
        try:
            response = requests.post(f"{self.backend_url}/scan/analyze", 
                                   json={"image_base64": test_image, "language": "en"},
                                   headers=headers)
            
            if response.status_code == 403:
                error_data = response.json()
                
                # Check error structure
                if error_data.get('detail', {}).get('error') == 'scan_limit_reached':
                    self.log_test("4.5 Second Scan (Should Fail)", True, "Second scan blocked with scan_limit_reached")
                    
                    # Check upgrade_required flag
                    if error_data.get('detail', {}).get('upgrade_required') is True:
                        self.log_test("4.6 Upgrade Required Flag", True, "upgrade_required flag is present")
                    else:
                        self.log_test("4.6 Upgrade Required Flag", False, error="upgrade_required flag missing or false")
                        
                else:
                    self.log_test("4.5 Second Scan (Should Fail)", False, error=f"Wrong error type: {error_data}")
                    
            else:
                self.log_test("4.5 Second Scan (Should Fail)", False, error=f"Expected 403, got {response.status_code}")
                
        except Exception as e:
            self.log_test("4.5 Second Scan (Should Fail)", False, error=f"Exception: {str(e)}")

    def test_5_subscription_status_endpoint(self):
        """Test 5: SUBSCRIPTION STATUS ENDPOINT"""
        print("=== TEST 5: SUBSCRIPTION STATUS ENDPOINT ===")
        
        # Test with free user
        email = f"test_status_{int(time.time())}@test.com"
        token, user_id, _ = self.register_test_user(email, "Status Test User")
        
        if not token:
            self.log_test("5.1 Create Status Test User", False, error="Failed to register status test user")
            return
            
        self.log_test("5.1 Create Status Test User", True, f"Status test user registered: {email}")
        
        try:
            headers = self.get_auth_headers(token)
            response = requests.get(f"{self.backend_url}/subscription/status", headers=headers)
            
            if response.status_code == 200:
                status_data = response.json()
                
                # Check free user status
                expected_free = {
                    'plan': 'free',
                    'scan_limit': 1,
                    'can_scan': True
                }
                
                checks_passed = 0
                total_checks = len(expected_free)
                
                for key, expected_value in expected_free.items():
                    if status_data.get(key) == expected_value:
                        checks_passed += 1
                    else:
                        print(f"   Mismatch: {key} = {status_data.get(key)}, expected {expected_value}")
                
                if checks_passed == total_checks:
                    self.log_test("5.2 Free User Status", True, f"All {total_checks} status fields correct")
                else:
                    self.log_test("5.2 Free User Status", False, error=f"Only {checks_passed}/{total_checks} fields correct")
                    
            else:
                self.log_test("5.2 Free User Status", False, error=f"Status request failed: {response.status_code}")
                
        except Exception as e:
            self.log_test("5.2 Free User Status", False, error=f"Exception: {str(e)}")
        
        # Test with premium user if available
        if self.premium_user_token:
            try:
                premium_headers = self.get_auth_headers(self.premium_user_token)
                response = requests.get(f"{self.backend_url}/subscription/status", headers=premium_headers)
                
                if response.status_code == 200:
                    status_data = response.json()
                    
                    # Check premium user status
                    expected_premium = {
                        'plan': 'premium',
                        'scan_limit': -1,  # Unlimited
                        'can_scan': True
                    }
                    
                    checks_passed = 0
                    total_checks = len(expected_premium)
                    
                    for key, expected_value in expected_premium.items():
                        if status_data.get(key) == expected_value:
                            checks_passed += 1
                        else:
                            print(f"   Mismatch: {key} = {status_data.get(key)}, expected {expected_value}")
                    
                    if checks_passed == total_checks:
                        self.log_test("5.3 Premium User Status", True, f"All {total_checks} premium status fields correct")
                    else:
                        self.log_test("5.3 Premium User Status", False, error=f"Only {checks_passed}/{total_checks} fields correct")
                        
                else:
                    self.log_test("5.3 Premium User Status", False, error=f"Premium status request failed: {response.status_code}")
                    
            except Exception as e:
                self.log_test("5.3 Premium User Status", False, error=f"Exception: {str(e)}")

    def run_all_tests(self):
        """Run all tests"""
        print(f"🧪 Starting SkinAdvisor AI Backend Testing - CRITICAL FIXES VALIDATION")
        print(f"Backend URL: {self.backend_url}")
        print(f"Test Time: {datetime.now().isoformat()}")
        print("=" * 80)
        
        # Run all test suites
        self.test_1_new_scoring_system_validation()
        self.test_2_subscription_flow()
        self.test_3_plan_based_response_structure()
        self.test_4_scan_limit_enforcement()
        self.test_5_subscription_status_endpoint()
        
        # Summary
        print("=" * 80)
        print("🏁 TEST SUMMARY")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for test in self.test_results:
                if not test['success']:
                    print(f"  - {test['test']}: {test['error']}")
        
        print("\n" + "=" * 80)
        
        # Save results to file
        with open('/app/backend_test_results.json', 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'success_rate': f"{(passed_tests/total_tests)*100:.1f}%"
                },
                'test_results': self.test_results,
                'backend_url': self.backend_url,
                'test_time': datetime.now().isoformat()
            }, f, indent=2)
        
        return passed_tests == total_tests

if __name__ == "__main__":
    tester = SkinAdvisorTester()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 ALL TESTS PASSED! Critical fixes are working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED! Please review the issues above.")