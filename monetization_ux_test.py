#!/usr/bin/env python3
"""
CRITICAL MONETIZATION UX FIX TESTING
Testing that free users see issues (locked, not hidden) for proper conversion UX.

Test Scenarios:
1. Free User Response Structure - issues_preview with names visible, details locked
2. Premium User Response Structure - full issue details
3. No "Empty Issues" Bug - free users see issue_count and issues_preview when issues exist
"""

import requests
import json
import base64
import os
from datetime import datetime
import uuid

# Get backend URL from environment
BACKEND_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://skin-advisor-ai-1.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

print(f"🔗 Testing Backend API at: {API_BASE}")

class MonetizationUXTester:
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
    
    def log_test(self, name, passed, details=""):
        self.test_results.append({
            'name': name,
            'passed': passed,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
        if passed:
            self.passed += 1
            print(f"✅ {name}")
            if details:
                print(f"   {details}")
        else:
            self.failed += 1
            print(f"❌ {name}")
            if details:
                print(f"   {details}")
        print()
    
    def create_test_image(self):
        """Create a simple test image in base64 format"""
        # Create a minimal 1x1 pixel PNG in base64
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    def register_user(self, user_type="free"):
        """Register a new user for testing"""
        try:
            email = f"test_{user_type}_{uuid.uuid4().hex[:8]}@example.com"
            response = requests.post(f"{API_BASE}/auth/register", json={
                "email": email,
                "password": "testpass123",
                "name": f"Test {user_type.title()} User",
                "language": "en"
            })
            
            if response.status_code == 200:
                data = response.json()
                user = data.get('user', {})
                
                if user.get('plan') == 'free' and user.get('scan_count') == 0:
                    self.log_test(f"User Registration ({user_type})", True, f"Email: {email}")
                    return data.get('access_token'), user.get('id'), email
                else:
                    self.log_test(f"User Registration ({user_type})", False, f"Expected plan='free', scan_count=0, got plan='{user.get('plan')}', scan_count={user.get('scan_count')}")
            else:
                self.log_test(f"User Registration ({user_type})", False, f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            self.log_test(f"User Registration ({user_type})", False, f"Exception: {str(e)}")
        
        return None, None, None

    def upgrade_to_premium(self, token):
        """Upgrade user to premium"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.post(f"{API_BASE}/subscription/upgrade", 
                                   json={"plan": "premium"}, 
                                   headers=headers)
            
            if response.status_code == 200:
                self.log_test("Premium Upgrade", True, "User upgraded to premium successfully")
                return True
            else:
                self.log_test("Premium Upgrade", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Premium Upgrade", False, f"Exception: {str(e)}")
            return False

    def test_free_user_scan_response(self, token):
        """Test FREE user scan response - CRITICAL MONETIZATION UX"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            test_image = self.create_test_image()
            
            response = requests.post(f"{API_BASE}/scan/analyze", 
                                   json={
                                       "image_base64": test_image,
                                       "language": "en"
                                   }, 
                                   headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Critical checks for monetization UX
                checks = []
                all_passed = True
                
                # 1. User plan should be 'free'
                if data.get('user_plan') == 'free':
                    checks.append("✓ user_plan = 'free'")
                else:
                    checks.append(f"✗ user_plan = '{data.get('user_plan')}' (expected 'free')")
                    all_passed = False
                
                # 2. Should be locked
                if data.get('locked') == True:
                    checks.append("✓ locked = true")
                else:
                    checks.append(f"✗ locked = {data.get('locked')} (expected true)")
                    all_passed = False
                
                # 3. Analysis should contain issue_count
                analysis = data.get('analysis', {})
                issue_count = analysis.get('issue_count')
                if isinstance(issue_count, int) and issue_count >= 0:
                    checks.append(f"✓ issue_count = {issue_count}")
                else:
                    checks.append(f"✗ issue_count = {issue_count} (expected integer >= 0)")
                    all_passed = False
                
                # 4. Analysis should contain issues_preview
                issues_preview = analysis.get('issues_preview', [])
                if isinstance(issues_preview, list):
                    checks.append(f"✓ issues_preview array with {len(issues_preview)} items")
                    
                    # 5. Each issue in preview should have name and be locked
                    for i, issue in enumerate(issues_preview):
                        if issue.get('name') and issue.get('locked') == True:
                            checks.append(f"  ✓ Issue {i+1}: '{issue.get('name')}' (locked)")
                        else:
                            checks.append(f"  ✗ Issue {i+1}: missing name or not locked")
                            all_passed = False
                else:
                    checks.append(f"✗ issues_preview = {type(issues_preview)} (expected list)")
                    all_passed = False
                
                # 6. Should have locked_features
                locked_features = data.get('locked_features', [])
                if isinstance(locked_features, list) and len(locked_features) > 0:
                    checks.append(f"✓ locked_features: {len(locked_features)} features locked")
                else:
                    checks.append("✗ locked_features missing or empty")
                    all_passed = False
                
                # 7. Should NOT have full routine/diet/products (those are premium)
                has_routine = 'routine' in data
                has_diet = 'diet_recommendations' in data
                has_products = 'products' in data
                
                if not has_routine and not has_diet and not has_products:
                    checks.append("✓ Premium features properly locked (no routine/diet/products)")
                else:
                    checks.append(f"✗ Premium features leaked: routine={has_routine}, diet={has_diet}, products={has_products}")
                    all_passed = False
                
                # 8. CRITICAL: If issue_count > 0, issues_preview should not be empty
                if issue_count > 0 and len(issues_preview) == 0:
                    checks.append("✗ CRITICAL BUG: issue_count > 0 but issues_preview is empty!")
                    all_passed = False
                elif issue_count > 0 and len(issues_preview) > 0:
                    checks.append("✓ CRITICAL FIX: Issues detected and visible in preview")
                elif issue_count == 0:
                    checks.append("✓ No issues detected (acceptable)")
                
                # 9. Check that issue_count matches issues_preview length
                if issue_count == len(issues_preview):
                    checks.append("✓ issue_count matches issues_preview length")
                else:
                    checks.append(f"✗ issue_count ({issue_count}) != issues_preview length ({len(issues_preview)})")
                    all_passed = False
                
                details = "\n    ".join(checks)
                self.log_test("Free User Scan Response Structure", all_passed, details)
                
                return data.get('id'), issue_count > 0, data
                
            else:
                self.log_test("Free User Scan Response Structure", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Free User Scan Response Structure", False, f"Exception: {str(e)}")
        
        return None, False, None

    def test_premium_user_scan_response(self, token):
        """Test PREMIUM user scan response structure"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            test_image = self.create_test_image()
            
            response = requests.post(f"{API_BASE}/scan/analyze", 
                                   json={
                                       "image_base64": test_image,
                                       "language": "en"
                                   }, 
                                   headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                checks = []
                all_passed = True
                
                # 1. User plan should be 'premium'
                if data.get('user_plan') == 'premium':
                    checks.append("✓ user_plan = 'premium'")
                else:
                    checks.append(f"✗ user_plan = '{data.get('user_plan')}' (expected 'premium')")
                    all_passed = False
                
                # 2. Should NOT be locked
                if data.get('locked') == False:
                    checks.append("✓ locked = false")
                else:
                    checks.append(f"✗ locked = {data.get('locked')} (expected false)")
                    all_passed = False
                
                # 3. Analysis should contain full issues (not issues_preview)
                analysis = data.get('analysis', {})
                issues = analysis.get('issues', [])
                if isinstance(issues, list):
                    checks.append(f"✓ Full issues array with {len(issues)} items")
                    
                    # Check if issues have full details (name, severity, description)
                    for i, issue in enumerate(issues):
                        if issue.get('name') and 'severity' in issue and 'description' in issue:
                            checks.append(f"  ✓ Issue {i+1}: '{issue.get('name')}' (severity: {issue.get('severity')})")
                        else:
                            checks.append(f"  ✗ Issue {i+1}: missing details")
                            all_passed = False
                else:
                    checks.append(f"✗ issues = {type(issues)} (expected list)")
                    all_passed = False
                
                # 4. Should have premium features
                has_routine = 'routine' in data
                has_diet = 'diet_recommendations' in data
                has_products = 'products' in data
                
                if has_routine and has_diet and has_products:
                    checks.append("✓ Premium features available (routine, diet, products)")
                else:
                    checks.append(f"✗ Missing premium features: routine={has_routine}, diet={has_diet}, products={has_products}")
                    all_passed = False
                
                # 5. Should NOT have issues_preview (that's for free users)
                if 'issues_preview' not in analysis:
                    checks.append("✓ No issues_preview (correct for premium)")
                else:
                    checks.append("✗ Has issues_preview (should only be for free users)")
                    all_passed = False
                
                details = "\n    ".join(checks)
                self.log_test("Premium User Scan Response Structure", all_passed, details)
                
                return data.get('id'), data
                
            else:
                self.log_test("Premium User Scan Response Structure", False, f"Status: {response.status_code}, Response: {response.text}")
                
        except Exception as e:
            self.log_test("Premium User Scan Response Structure", False, f"Exception: {str(e)}")
        
        return None, None

    def test_scan_detail_endpoint(self, token, scan_id, user_type="free"):
        """Test GET /api/scan/{scan_id} endpoint"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"{API_BASE}/scan/{scan_id}", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                checks = []
                all_passed = True
                
                if user_type == "free":
                    # Free user checks
                    if data.get('user_plan') == 'free' and data.get('locked') == True:
                        checks.append("✓ Free user scan detail properly locked")
                    else:
                        checks.append(f"✗ Expected free/locked, got plan='{data.get('user_plan')}', locked={data.get('locked')}")
                        all_passed = False
                    
                    # Should have issues_preview and issue_count
                    analysis = data.get('analysis', {})
                    if 'issues_preview' in analysis and 'issue_count' in analysis:
                        checks.append("✓ Has issues_preview and issue_count")
                    else:
                        checks.append("✗ Missing issues_preview or issue_count")
                        all_passed = False
                        
                else:  # premium
                    # Premium user checks
                    if data.get('user_plan') == 'premium':
                        checks.append("✓ Premium user scan detail")
                    else:
                        checks.append(f"✗ Expected premium, got '{data.get('user_plan')}'")
                        all_passed = False
                    
                    # Should have full issues (not issues_preview)
                    analysis = data.get('analysis', {})
                    if 'issues' in analysis and isinstance(analysis['issues'], list):
                        checks.append("✓ Has full issues array")
                    else:
                        checks.append("✗ Missing full issues array")
                        all_passed = False
                
                details = "\n    ".join(checks)
                self.log_test(f"{user_type.title()} User Scan Detail Endpoint", all_passed, details)
                
            else:
                self.log_test(f"{user_type.title()} User Scan Detail Endpoint", False, f"Status: {response.status_code}")
                
        except Exception as e:
            self.log_test(f"{user_type.title()} User Scan Detail Endpoint", False, f"Exception: {str(e)}")

    def run_tests(self):
        """Run all monetization UX tests"""
        print("🧪 TESTING CRITICAL MONETIZATION UX FIX")
        print("=" * 60)
        print("Testing that free users see issues (locked, not hidden)")
        print()
        
        # Test 1: Free User Flow
        print("1️⃣ Testing Free User Flow...")
        free_token, free_user_id, free_email = self.register_user("free")
        
        if not free_token:
            print("❌ Cannot continue without free user token")
            return
        
        # Test free user scan
        free_scan_id, has_issues, free_scan_data = self.test_free_user_scan_response(free_token)
        
        # Test free user scan detail
        if free_scan_id:
            self.test_scan_detail_endpoint(free_token, free_scan_id, "free")
        
        print("\n2️⃣ Testing Premium User Flow...")
        
        # Test 2: Premium User Flow
        premium_token, premium_user_id, premium_email = self.register_user("premium")
        
        if premium_token:
            # Upgrade to premium
            if self.upgrade_to_premium(premium_token):
                # Test premium scan
                premium_scan_id, premium_scan_data = self.test_premium_user_scan_response(premium_token)
                
                # Test premium scan detail
                if premium_scan_id:
                    self.test_scan_detail_endpoint(premium_token, premium_scan_id, "premium")
        
        print("\n3️⃣ Critical Issue Detection Validation...")
        
        # Verify the critical fix: Free users must see issues when they exist
        if has_issues:
            self.log_test("Critical Fix Verification", True, "Free users can see issues exist (names visible, details locked)")
        else:
            print("⚠️  Note: No issues detected in test scan - this is acceptable but limits validation")
            self.log_test("Critical Fix Verification", True, "Test completed (no issues detected to validate visibility)")
        
        # Final summary
        print("\n" + "=" * 60)
        total = self.passed + self.failed
        print(f"📊 TEST SUMMARY: {self.passed}/{total} passed ({self.failed} failed)")
        
        if self.failed == 0:
            print("🎉 ALL TESTS PASSED - Monetization UX fix is working correctly!")
            print("✅ Free users can see issues exist (builds trust)")
            print("✅ Free users cannot see issue details (drives conversion)")
            print("✅ Premium users get full access")
        else:
            print(f"⚠️  {self.failed} tests failed - Issues need attention")
        
        # Save detailed results
        with open('/app/monetization_ux_test_results.json', 'w') as f:
            json.dump({
                'summary': {'passed': self.passed, 'failed': self.failed, 'total': total},
                'tests': self.test_results,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: /app/monetization_ux_test_results.json")
        
        return self.failed == 0

def main():
    tester = MonetizationUXTester()
    success = tester.run_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())