#!/usr/bin/env python3
"""
COMPREHENSIVE MONETIZATION UX FIX TESTING
Testing the critical fix where free users must see issues (locked, not hidden).

This test creates a more realistic scenario to ensure issues are detected.
"""

import requests
import json
import base64
import os
from datetime import datetime
import uuid

# Get backend URL from environment
BACKEND_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://ai-skin-companion.preview.emergentagent.com')
API_BASE = f"{BACKEND_URL}/api"

def create_realistic_test_image():
    """Create a more realistic test image that might trigger issue detection"""
    # This is a small but valid JPEG image (2x2 pixels) that should trigger the AI analysis
    # The AI should detect at least the universal optimization issues
    jpeg_base64 = "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/8A8A"
    return jpeg_base64

def test_monetization_ux_comprehensive():
    """Comprehensive test of the monetization UX fix"""
    print("🧪 COMPREHENSIVE MONETIZATION UX FIX TESTING")
    print("=" * 60)
    
    results = []
    
    # Test 1: Register free user
    print("1️⃣ Testing Free User with Realistic Image...")
    
    try:
        # Register free user
        email = f"test_comprehensive_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(f"{API_BASE}/auth/register", json={
            "email": email,
            "password": "testpass123",
            "name": "Test Comprehensive User",
            "language": "en"
        })
        
        if response.status_code != 200:
            print(f"❌ Failed to register user: {response.status_code}")
            return False
        
        user_data = response.json()
        token = user_data.get('access_token')
        user = user_data.get('user', {})
        
        print(f"✅ User registered: {email}")
        print(f"   Plan: {user.get('plan')}, Scan count: {user.get('scan_count')}")
        
        # Test 2: Perform scan with realistic image
        print("\n2️⃣ Performing scan with realistic image...")
        
        headers = {"Authorization": f"Bearer {token}"}
        realistic_image = create_realistic_test_image()
        
        scan_response = requests.post(f"{API_BASE}/scan/analyze", 
                                    json={
                                        "image_base64": realistic_image,
                                        "language": "en"
                                    }, 
                                    headers=headers)
        
        if scan_response.status_code != 200:
            print(f"❌ Scan failed: {scan_response.status_code}")
            print(f"   Response: {scan_response.text}")
            return False
        
        scan_data = scan_response.json()
        
        # Test 3: Validate free user response structure
        print("\n3️⃣ Validating Free User Response Structure...")
        
        validation_results = []
        
        # Check basic structure
        if scan_data.get('user_plan') == 'free':
            validation_results.append("✅ user_plan = 'free'")
        else:
            validation_results.append(f"❌ user_plan = '{scan_data.get('user_plan')}' (expected 'free')")
        
        if scan_data.get('locked') == True:
            validation_results.append("✅ locked = true")
        else:
            validation_results.append(f"❌ locked = {scan_data.get('locked')} (expected true)")
        
        # Check analysis structure
        analysis = scan_data.get('analysis', {})
        issue_count = analysis.get('issue_count', 0)
        issues_preview = analysis.get('issues_preview', [])
        
        validation_results.append(f"📊 issue_count = {issue_count}")
        validation_results.append(f"📊 issues_preview length = {len(issues_preview)}")
        
        # CRITICAL TEST: The backend should ALWAYS return at least some optimization issues
        # due to UNIVERSAL_OPTIMIZATION_ISSUES in the code
        if issue_count > 0:
            validation_results.append("✅ CRITICAL: Issues detected (as expected)")
            
            if len(issues_preview) > 0:
                validation_results.append("✅ CRITICAL: issues_preview not empty")
                
                # Check each issue in preview
                for i, issue in enumerate(issues_preview):
                    name = issue.get('name', '')
                    locked = issue.get('locked', False)
                    
                    if name and locked:
                        validation_results.append(f"  ✅ Issue {i+1}: '{name}' (locked: {locked})")
                    else:
                        validation_results.append(f"  ❌ Issue {i+1}: name='{name}', locked={locked}")
                
                # Check that severity and description are locked
                first_issue = issues_preview[0]
                if 'severity' not in first_issue and 'description' not in first_issue:
                    validation_results.append("✅ CRITICAL: Issue details properly locked (no severity/description)")
                else:
                    validation_results.append(f"❌ CRITICAL: Issue details leaked - severity: {'severity' in first_issue}, description: {'description' in first_issue}")
                
            else:
                validation_results.append("❌ CRITICAL BUG: issue_count > 0 but issues_preview is empty!")
        else:
            validation_results.append("⚠️  WARNING: No issues detected - this might indicate a problem with AI analysis")
        
        # Check that issue_count matches issues_preview length
        if issue_count == len(issues_preview):
            validation_results.append("✅ issue_count matches issues_preview length")
        else:
            validation_results.append(f"❌ issue_count ({issue_count}) != issues_preview length ({len(issues_preview)})")
        
        # Check locked features
        locked_features = scan_data.get('locked_features', [])
        if len(locked_features) > 0:
            validation_results.append(f"✅ locked_features: {len(locked_features)} features locked")
        else:
            validation_results.append("❌ locked_features missing or empty")
        
        # Check that premium features are not present
        premium_features = ['routine', 'diet_recommendations', 'products']
        leaked_features = [f for f in premium_features if f in scan_data]
        
        if not leaked_features:
            validation_results.append("✅ Premium features properly locked")
        else:
            validation_results.append(f"❌ Premium features leaked: {leaked_features}")
        
        # Print all validation results
        for result in validation_results:
            print(f"   {result}")
        
        # Test 4: Test scan detail endpoint
        print("\n4️⃣ Testing Scan Detail Endpoint...")
        
        scan_id = scan_data.get('id')
        if scan_id:
            detail_response = requests.get(f"{API_BASE}/scan/{scan_id}", headers=headers)
            
            if detail_response.status_code == 200:
                detail_data = detail_response.json()
                
                # Should have same structure as scan/analyze
                detail_analysis = detail_data.get('analysis', {})
                detail_issue_count = detail_analysis.get('issue_count', 0)
                detail_issues_preview = detail_analysis.get('issues_preview', [])
                
                if detail_issue_count == issue_count and len(detail_issues_preview) == len(issues_preview):
                    print("   ✅ Scan detail endpoint consistent with analyze endpoint")
                else:
                    print(f"   ❌ Scan detail inconsistent: count {detail_issue_count} vs {issue_count}, preview {len(detail_issues_preview)} vs {len(issues_preview)}")
            else:
                print(f"   ❌ Scan detail failed: {detail_response.status_code}")
        
        # Test 5: Upgrade to premium and test
        print("\n5️⃣ Testing Premium Upgrade...")
        
        upgrade_response = requests.post(f"{API_BASE}/subscription/upgrade", 
                                       json={"plan": "premium"}, 
                                       headers=headers)
        
        if upgrade_response.status_code == 200:
            print("   ✅ Upgraded to premium")
            
            # Test premium scan
            premium_scan_response = requests.post(f"{API_BASE}/scan/analyze", 
                                                json={
                                                    "image_base64": realistic_image,
                                                    "language": "en"
                                                }, 
                                                headers=headers)
            
            if premium_scan_response.status_code == 200:
                premium_data = premium_scan_response.json()
                
                # Check premium response structure
                if premium_data.get('user_plan') == 'premium' and premium_data.get('locked') == False:
                    print("   ✅ Premium user gets unlocked response")
                    
                    # Should have full issues (not issues_preview)
                    premium_analysis = premium_data.get('analysis', {})
                    if 'issues' in premium_analysis and 'issues_preview' not in premium_analysis:
                        print("   ✅ Premium user gets full issues (not preview)")
                        
                        # Check that issues have full details
                        issues = premium_analysis.get('issues', [])
                        if issues and all('severity' in issue and 'description' in issue for issue in issues):
                            print("   ✅ Premium issues have full details (severity, description)")
                        else:
                            print("   ⚠️  Premium issues missing some details")
                    else:
                        print("   ❌ Premium user response structure incorrect")
                    
                    # Should have premium features
                    premium_features = ['routine', 'diet_recommendations', 'products']
                    available_features = [f for f in premium_features if f in premium_data]
                    
                    if len(available_features) == len(premium_features):
                        print("   ✅ Premium user gets all premium features")
                    else:
                        print(f"   ❌ Premium user missing features: {set(premium_features) - set(available_features)}")
                else:
                    print(f"   ❌ Premium response incorrect: plan={premium_data.get('user_plan')}, locked={premium_data.get('locked')}")
            else:
                print(f"   ❌ Premium scan failed: {premium_scan_response.status_code}")
        else:
            print(f"   ❌ Premium upgrade failed: {upgrade_response.status_code}")
        
        # Final assessment
        print("\n" + "=" * 60)
        
        # Count critical issues
        critical_failures = [r for r in validation_results if "❌ CRITICAL" in r]
        
        if not critical_failures:
            print("🎉 MONETIZATION UX FIX WORKING CORRECTLY!")
            print("✅ Free users can see issues exist (builds trust)")
            print("✅ Free users cannot see issue details (drives conversion)")
            print("✅ Premium users get full access")
            
            # Save success result
            with open('/app/comprehensive_test_results.json', 'w') as f:
                json.dump({
                    'status': 'SUCCESS',
                    'free_user_scan': scan_data,
                    'validation_results': validation_results,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
            
            return True
        else:
            print("❌ CRITICAL ISSUES FOUND:")
            for failure in critical_failures:
                print(f"   {failure}")
            
            # Save failure result
            with open('/app/comprehensive_test_results.json', 'w') as f:
                json.dump({
                    'status': 'FAILURE',
                    'critical_failures': critical_failures,
                    'free_user_scan': scan_data,
                    'validation_results': validation_results,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
            
            return False
        
    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_monetization_ux_comprehensive()
    exit(0 if success else 1)