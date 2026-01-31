#!/usr/bin/env python3
"""
Final comprehensive test for Monetization & Paywall System
"""

import requests
import json
import uuid
from datetime import datetime

BACKEND_URL = "https://ai-skin-companion.preview.emergentagent.com/api"
TEST_PASSWORD = "TestPass123!"

def test_complete_paywall_flow():
    """Test the complete paywall flow"""
    results = []
    
    def log_result(test_name, passed, details):
        result = {"test": test_name, "passed": passed, "details": details}
        results.append(result)
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name} - {details}")
    
    print("🧪 FINAL MONETIZATION & PAYWALL SYSTEM TEST")
    print("=" * 60)
    
    # Test 1: Register new user with free plan
    unique_id = str(uuid.uuid4())[:8]
    email = f"final_test_{unique_id}@test.com"
    
    user_data = {
        "email": email,
        "password": TEST_PASSWORD,
        "name": "Final Test User",
        "language": "en"
    }
    
    response = requests.post(f"{BACKEND_URL}/auth/register", json=user_data)
    if response.status_code == 200:
        user = response.json().get("user", {})
        plan = user.get("plan")
        scan_count = user.get("scan_count")
        if plan == "free" and scan_count == 0:
            log_result("User Registration", True, f"New user created with plan='{plan}', scan_count={scan_count}")
            token = response.json().get("access_token")
        else:
            log_result("User Registration", False, f"Expected plan='free' and scan_count=0, got plan='{plan}', scan_count={scan_count}")
            return results
    else:
        log_result("User Registration", False, f"Registration failed: {response.text}")
        return results
    
    # Test 2: Subscription status for free user
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BACKEND_URL}/subscription/status", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if (data.get("plan") == "free" and 
            data.get("scan_limit") == 1 and 
            data.get("can_scan") == True):
            log_result("Free User Subscription Status", True, f"Correct free user limits: scan_limit=1, can_scan=True")
        else:
            log_result("Free User Subscription Status", False, f"Incorrect limits: {data}")
    else:
        log_result("Free User Subscription Status", False, f"Request failed: {response.text}")
    
    # Test 3: Pricing endpoint
    response = requests.get(f"{BACKEND_URL}/subscription/pricing")
    if response.status_code == 200:
        data = response.json()
        monthly_price = data.get("monthly", {}).get("price")
        yearly_price = data.get("yearly", {}).get("price")
        if monthly_price == 9.99 and yearly_price == 59.99:
            log_result("Pricing Endpoint", True, f"Correct pricing: monthly=€{monthly_price}, yearly=€{yearly_price}")
        else:
            log_result("Pricing Endpoint", False, f"Incorrect pricing: monthly={monthly_price}, yearly={yearly_price}")
    else:
        log_result("Pricing Endpoint", False, f"Request failed: {response.text}")
    
    # Test 4: First scan (should work)
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    scan_data = {"image_base64": test_image_b64, "language": "en"}
    
    response = requests.post(f"{BACKEND_URL}/scan/analyze", json=scan_data, headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        if data.get("user_plan") == "free" and "locked_features" in data:
            log_result("Free User First Scan", True, "Free user gets limited response with locked features")
        else:
            log_result("Free User First Scan", False, f"Unexpected response structure: {list(data.keys())}")
    else:
        log_result("Free User First Scan", False, f"First scan failed: {response.text}")
    
    # Test 5: Second scan (should fail with 403)
    response = requests.post(f"{BACKEND_URL}/scan/analyze", json=scan_data, headers=headers, timeout=30)
    if response.status_code == 403:
        error_data = response.json()
        detail = error_data.get("detail", {})
        if (isinstance(detail, dict) and 
            detail.get("error") == "scan_limit_reached" and 
            detail.get("upgrade_required") == True):
            log_result("Scan Limit Enforcement", True, "Free user correctly blocked after 1 scan")
        else:
            log_result("Scan Limit Enforcement", False, f"Incorrect error response: {detail}")
    else:
        log_result("Scan Limit Enforcement", False, f"Expected 403, got {response.status_code}")
    
    # Test 6: Upgrade to premium
    upgrade_data = {"plan": "premium"}
    response = requests.post(f"{BACKEND_URL}/subscription/upgrade", json=upgrade_data, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("success") == True and data.get("plan") == "premium":
            log_result("Premium Upgrade", True, "Successfully upgraded to premium")
        else:
            log_result("Premium Upgrade", False, f"Upgrade response incorrect: {data}")
    else:
        log_result("Premium Upgrade", False, f"Upgrade failed: {response.text}")
    
    # Test 7: Premium user subscription status
    response = requests.get(f"{BACKEND_URL}/subscription/status", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if (data.get("plan") == "premium" and 
            data.get("scan_limit") == -1 and 
            data.get("can_scan") == True):
            log_result("Premium User Status", True, "Premium user has unlimited scans")
        else:
            log_result("Premium User Status", False, f"Incorrect premium status: {data}")
    else:
        log_result("Premium User Status", False, f"Request failed: {response.text}")
    
    # Test 8: Premium user scan (should get full response)
    response = requests.post(f"{BACKEND_URL}/scan/analyze", json=scan_data, headers=headers, timeout=30)
    if response.status_code == 200:
        data = response.json()
        if (data.get("user_plan") == "premium" and 
            "routine" in data and 
            "products" in data and 
            "diet_recommendations" in data):
            log_result("Premium User Scan", True, "Premium user gets full response with all features")
        else:
            log_result("Premium User Scan", False, f"Premium response missing features: {list(data.keys())}")
    else:
        log_result("Premium User Scan", False, f"Premium scan failed: {response.text}")
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 FINAL TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    print(f"📊 Success Rate: {(passed/total*100):.1f}%")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Monetization & Paywall System is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the details above.")
    
    return results

if __name__ == "__main__":
    test_complete_paywall_flow()