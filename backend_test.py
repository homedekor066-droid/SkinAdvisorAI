#!/usr/bin/env python3
"""
Backend Test Suite for SkinAdvisor AI - Monetization & Paywall System
Testing the NEW subscription endpoints and paywall functionality
"""

import requests
import json
import base64
import os
from datetime import datetime
import uuid

# Configuration
BACKEND_URL = "https://skinsmart-ai-4.preview.emergentagent.com/api"
TEST_EMAIL_PREFIX = "test_paywall_user"
TEST_PASSWORD = "TestPass123!"

class PaywallTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_user_token = None
        self.test_user_id = None
        self.test_user_email = None
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {"passed": 0, "failed": 0, "total": 0}
        }
    
    def log_test(self, test_name, passed, details="", response_data=None):
        """Log test result"""
        result = {
            "test": test_name,
            "passed": passed,
            "details": details,
            "response_data": response_data,
            "timestamp": datetime.now().isoformat()
        }
        self.results["tests"].append(result)
        self.results["summary"]["total"] += 1
        if passed:
            self.results["summary"]["passed"] += 1
            print(f"✅ {test_name}: PASSED - {details}")
        else:
            self.results["summary"]["failed"] += 1
            print(f"❌ {test_name}: FAILED - {details}")
    
    def make_request(self, method, endpoint, data=None, headers=None, expect_status=200):
        """Make HTTP request with error handling"""
        url = f"{BACKEND_URL}{endpoint}"
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=default_headers)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, headers=default_headers)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, headers=default_headers)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, headers=default_headers)
            
            return response
        except Exception as e:
            print(f"Request error: {str(e)}")
            return None
    
    def test_1_register_new_user(self):
        """Test 1: Register a NEW user and verify plan='free' and scan_count=0"""
        # Generate unique email for this test
        unique_id = str(uuid.uuid4())[:8]
        self.test_user_email = f"{TEST_EMAIL_PREFIX}_{unique_id}@test.com"
        
        user_data = {
            "email": self.test_user_email,
            "password": TEST_PASSWORD,
            "name": "Test Paywall User",
            "language": "en"
        }
        
        response = self.make_request("POST", "/auth/register", user_data)
        
        if response and response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            
            # Store token for subsequent tests
            self.test_user_token = data.get("access_token")
            self.test_user_id = user.get("id")
            
            # Verify new user has plan='free' and scan_count=0
            plan = user.get("plan")
            scan_count = user.get("scan_count")
            
            if plan == "free" and scan_count == 0:
                self.log_test(
                    "Register New User with Free Plan",
                    True,
                    f"User created with plan='{plan}' and scan_count={scan_count}",
                    {"plan": plan, "scan_count": scan_count, "user_id": self.test_user_id}
                )
            else:
                self.log_test(
                    "Register New User with Free Plan",
                    False,
                    f"Expected plan='free' and scan_count=0, got plan='{plan}' and scan_count={scan_count}",
                    {"plan": plan, "scan_count": scan_count}
                )
        else:
            error_msg = response.text if response else "No response"
            self.log_test(
                "Register New User with Free Plan",
                False,
                f"Registration failed: {error_msg}",
                {"status_code": response.status_code if response else None}
            )
    
    def test_2_login_returns_plan_and_scan_count(self):
        """Test 2: Verify login returns plan and scan_count in response"""
        login_data = {
            "email": self.test_user_email,
            "password": TEST_PASSWORD
        }
        
        response = self.make_request("POST", "/auth/login", login_data)
        
        if response and response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            
            plan = user.get("plan")
            scan_count = user.get("scan_count")
            
            if plan is not None and scan_count is not None:
                self.log_test(
                    "Login Returns Plan and Scan Count",
                    True,
                    f"Login response includes plan='{plan}' and scan_count={scan_count}",
                    {"plan": plan, "scan_count": scan_count}
                )
            else:
                self.log_test(
                    "Login Returns Plan and Scan Count",
                    False,
                    f"Login response missing plan or scan_count. plan={plan}, scan_count={scan_count}",
                    {"plan": plan, "scan_count": scan_count}
                )
        else:
            error_msg = response.text if response else "No response"
            self.log_test(
                "Login Returns Plan and Scan Count",
                False,
                f"Login failed: {error_msg}",
                {"status_code": response.status_code if response else None}
            )
    
    def test_3_subscription_status_free_user(self):
        """Test 3: GET /api/subscription/status for free user"""
        if not self.test_user_token:
            self.log_test("Subscription Status (Free User)", False, "No auth token available")
            return
        
        headers = {"Authorization": f"Bearer {self.test_user_token}"}
        response = self.make_request("GET", "/subscription/status", headers=headers)
        
        if response and response.status_code == 200:
            data = response.json()
            
            # Verify expected fields for free user
            expected_fields = ["plan", "scan_count", "scan_limit", "can_scan", "features"]
            missing_fields = [field for field in expected_fields if field not in data]
            
            if not missing_fields:
                plan = data.get("plan")
                scan_limit = data.get("scan_limit")
                can_scan = data.get("can_scan")
                features = data.get("features", {})
                
                # Verify free user constraints
                if (plan == "free" and 
                    scan_limit == 1 and 
                    can_scan == True and  # Should be true since scan_count=0
                    isinstance(features, dict)):
                    
                    self.log_test(
                        "Subscription Status (Free User)",
                        True,
                        f"Free user status correct: plan={plan}, scan_limit={scan_limit}, can_scan={can_scan}",
                        data
                    )
                else:
                    self.log_test(
                        "Subscription Status (Free User)",
                        False,
                        f"Incorrect free user status: plan={plan}, scan_limit={scan_limit}, can_scan={can_scan}",
                        data
                    )
            else:
                self.log_test(
                    "Subscription Status (Free User)",
                    False,
                    f"Missing required fields: {missing_fields}",
                    data
                )
        else:
            error_msg = response.text if response else "No response"
            self.log_test(
                "Subscription Status (Free User)",
                False,
                f"Request failed: {error_msg}",
                {"status_code": response.status_code if response else None}
            )
    
    def test_4_subscription_pricing(self):
        """Test 4: GET /api/subscription/pricing (no auth required)"""
        response = self.make_request("GET", "/subscription/pricing")
        
        if response and response.status_code == 200:
            data = response.json()
            
            # Verify pricing structure
            monthly = data.get("monthly", {})
            yearly = data.get("yearly", {})
            features = data.get("features", [])
            
            monthly_price = monthly.get("price")
            yearly_price = yearly.get("price")
            
            if (monthly_price == 9.99 and 
                yearly_price == 59.99 and 
                isinstance(features, list) and 
                len(features) > 0):
                
                self.log_test(
                    "Subscription Pricing",
                    True,
                    f"Pricing correct: monthly=€{monthly_price}, yearly=€{yearly_price}, {len(features)} features",
                    data
                )
            else:
                self.log_test(
                    "Subscription Pricing",
                    False,
                    f"Incorrect pricing: monthly={monthly_price}, yearly={yearly_price}, features_count={len(features)}",
                    data
                )
        else:
            error_msg = response.text if response else "No response"
            self.log_test(
                "Subscription Pricing",
                False,
                f"Request failed: {error_msg}",
                {"status_code": response.status_code if response else None}
            )
    
    def test_5_upgrade_to_premium(self):
        """Test 5: POST /api/subscription/upgrade"""
        if not self.test_user_token:
            self.log_test("Upgrade to Premium", False, "No auth token available")
            return
        
        headers = {"Authorization": f"Bearer {self.test_user_token}"}
        upgrade_data = {"plan": "premium"}
        
        response = self.make_request("POST", "/subscription/upgrade", upgrade_data, headers)
        
        if response and response.status_code == 200:
            data = response.json()
            
            success = data.get("success")
            plan = data.get("plan")
            features_unlocked = data.get("features_unlocked", [])
            
            if (success == True and 
                plan == "premium" and 
                isinstance(features_unlocked, list) and 
                len(features_unlocked) > 0):
                
                self.log_test(
                    "Upgrade to Premium",
                    True,
                    f"Upgrade successful: plan={plan}, {len(features_unlocked)} features unlocked",
                    data
                )
            else:
                self.log_test(
                    "Upgrade to Premium",
                    False,
                    f"Upgrade response incorrect: success={success}, plan={plan}, features_count={len(features_unlocked)}",
                    data
                )
        else:
            error_msg = response.text if response else "No response"
            self.log_test(
                "Upgrade to Premium",
                False,
                f"Upgrade failed: {error_msg}",
                {"status_code": response.status_code if response else None}
            )
    
    def test_6_subscription_status_premium_user(self):
        """Test 6: GET /api/subscription/status for premium user"""
        if not self.test_user_token:
            self.log_test("Subscription Status (Premium User)", False, "No auth token available")
            return
        
        headers = {"Authorization": f"Bearer {self.test_user_token}"}
        response = self.make_request("GET", "/subscription/status", headers=headers)
        
        if response and response.status_code == 200:
            data = response.json()
            
            plan = data.get("plan")
            scan_limit = data.get("scan_limit")
            can_scan = data.get("can_scan")
            features = data.get("features", {})
            
            # Verify premium user status
            if (plan == "premium" and 
                scan_limit == -1 and  # Unlimited
                can_scan == True and 
                isinstance(features, dict)):
                
                # Check that premium features are enabled
                premium_features = ["unlimited_scans", "full_routine", "diet_plan", "product_recommendations"]
                enabled_features = [f for f in premium_features if features.get(f) == True]
                
                if len(enabled_features) == len(premium_features):
                    self.log_test(
                        "Subscription Status (Premium User)",
                        True,
                        f"Premium status correct: plan={plan}, scan_limit={scan_limit}, can_scan={can_scan}, all premium features enabled",
                        data
                    )
                else:
                    self.log_test(
                        "Subscription Status (Premium User)",
                        False,
                        f"Premium features not all enabled: {enabled_features} of {premium_features}",
                        data
                    )
            else:
                self.log_test(
                    "Subscription Status (Premium User)",
                    False,
                    f"Incorrect premium status: plan={plan}, scan_limit={scan_limit}, can_scan={can_scan}",
                    data
                )
        else:
            error_msg = response.text if response else "No response"
            self.log_test(
                "Subscription Status (Premium User)",
                False,
                f"Request failed: {error_msg}",
                {"status_code": response.status_code if response else None}
            )
    
    def test_7_scan_limit_enforcement_new_free_user(self):
        """Test 7: Test scan limit enforcement for a NEW free user"""
        # Create another free user to test scan limits
        unique_id = str(uuid.uuid4())[:8]
        free_user_email = f"test_free_scan_{unique_id}@test.com"
        
        # Register new free user
        user_data = {
            "email": free_user_email,
            "password": TEST_PASSWORD,
            "name": "Test Free Scan User",
            "language": "en"
        }
        
        response = self.make_request("POST", "/auth/register", user_data)
        
        if not response or response.status_code != 200:
            self.log_test("Scan Limit Enforcement", False, "Failed to create test free user")
            return
        
        free_user_token = response.json().get("access_token")
        
        # Create a simple test image (base64 encoded 1x1 pixel)
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        headers = {"Authorization": f"Bearer {free_user_token}"}
        
        # First scan should work (scan_count = 0, limit = 1)
        scan_data = {
            "image_base64": test_image_b64,
            "language": "en"
        }
        
        first_scan = self.make_request("POST", "/scan/analyze", scan_data, headers)
        
        if first_scan and first_scan.status_code == 200:
            first_data = first_scan.json()
            user_plan = first_data.get("user_plan")
            
            if user_plan == "free":
                # Second scan should fail with 403
                second_scan = self.make_request("POST", "/scan/analyze", scan_data, headers)
                
                if second_scan and second_scan.status_code == 403:
                    error_data = second_scan.json()
                    error_type = error_data.get("detail", {}).get("error") if isinstance(error_data.get("detail"), dict) else None
                    upgrade_required = error_data.get("detail", {}).get("upgrade_required") if isinstance(error_data.get("detail"), dict) else None
                    
                    if error_type == "scan_limit_reached" and upgrade_required == True:
                        self.log_test(
                            "Scan Limit Enforcement",
                            True,
                            "Free user correctly blocked after 1 scan with proper error response",
                            {"first_scan_status": 200, "second_scan_status": 403, "error": error_type}
                        )
                    else:
                        self.log_test(
                            "Scan Limit Enforcement",
                            False,
                            f"Incorrect error response: error={error_type}, upgrade_required={upgrade_required}",
                            error_data
                        )
                else:
                    status = second_scan.status_code if second_scan else "No response"
                    self.log_test(
                        "Scan Limit Enforcement",
                        False,
                        f"Second scan should return 403, got {status}",
                        {"second_scan_status": status}
                    )
            else:
                self.log_test(
                    "Scan Limit Enforcement",
                    False,
                    f"First scan should return user_plan='free', got '{user_plan}'",
                    first_data
                )
        else:
            status = first_scan.status_code if first_scan else "No response"
            self.log_test(
                "Scan Limit Enforcement",
                False,
                f"First scan failed with status {status}",
                {"first_scan_status": status}
            )
    
    def test_8_response_structure_free_vs_premium(self):
        """Test 8: Verify different response structures for free vs premium users"""
        # Test with the premium user (from earlier upgrade)
        if not self.test_user_token:
            self.log_test("Response Structure Comparison", False, "No premium user token available")
            return
        
        # Create a simple test image
        test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        headers = {"Authorization": f"Bearer {self.test_user_token}"}
        scan_data = {
            "image_base64": test_image_b64,
            "language": "en"
        }
        
        # Premium user scan
        premium_scan = self.make_request("POST", "/scan/analyze", scan_data, headers)
        
        if premium_scan and premium_scan.status_code == 200:
            premium_data = premium_scan.json()
            user_plan = premium_data.get("user_plan")
            
            if user_plan == "premium":
                # Check premium response has full data
                has_routine = "routine" in premium_data
                has_products = "products" in premium_data
                has_diet = "diet_recommendations" in premium_data
                
                if has_routine and has_products and has_diet:
                    self.log_test(
                        "Response Structure (Premium User)",
                        True,
                        "Premium user gets full response with routine, products, and diet recommendations",
                        {"user_plan": user_plan, "has_routine": has_routine, "has_products": has_products, "has_diet": has_diet}
                    )
                else:
                    self.log_test(
                        "Response Structure (Premium User)",
                        False,
                        f"Premium response missing data: routine={has_routine}, products={has_products}, diet={has_diet}",
                        premium_data
                    )
            else:
                self.log_test(
                    "Response Structure (Premium User)",
                    False,
                    f"Expected user_plan='premium', got '{user_plan}'",
                    premium_data
                )
        else:
            status = premium_scan.status_code if premium_scan else "No response"
            self.log_test(
                "Response Structure (Premium User)",
                False,
                f"Premium scan failed with status {status}",
                {"premium_scan_status": status}
            )
    
    def run_all_tests(self):
        """Run all paywall tests in sequence"""
        print("🧪 Starting Monetization & Paywall System Tests")
        print("=" * 60)
        
        # Test sequence
        self.test_1_register_new_user()
        self.test_2_login_returns_plan_and_scan_count()
        self.test_3_subscription_status_free_user()
        self.test_4_subscription_pricing()
        self.test_5_upgrade_to_premium()
        self.test_6_subscription_status_premium_user()
        self.test_7_scan_limit_enforcement_new_free_user()
        self.test_8_response_structure_free_vs_premium()
        
        # Print summary
        print("\n" + "=" * 60)
        print("🏁 TEST SUMMARY")
        print("=" * 60)
        passed = self.results["summary"]["passed"]
        failed = self.results["summary"]["failed"]
        total = self.results["summary"]["total"]
        
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {failed}/{total}")
        print(f"📊 Success Rate: {(passed/total*100):.1f}%" if total > 0 else "No tests run")
        
        if failed > 0:
            print("\n🔍 FAILED TESTS:")
            for test in self.results["tests"]:
                if not test["passed"]:
                    print(f"   ❌ {test['test']}: {test['details']}")
        
        # Save results to file
        with open("/app/paywall_test_results.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: /app/paywall_test_results.json")
        
        return self.results

if __name__ == "__main__":
    tester = PaywallTester()
    results = tester.run_all_tests()