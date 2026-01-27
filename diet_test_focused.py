#!/usr/bin/env python3
"""
Focused Diet & Nutrition Recommendations Test
Tests the diet recommendations feature specifically
"""

import requests
import json
import uuid
from datetime import datetime

# Configuration
BASE_URL = "https://skinai-advisor-2.preview.emergentagent.com/api"

def test_diet_recommendations():
    """Test diet recommendations functionality"""
    print("🧪 Testing Diet & Nutrition Recommendations Feature")
    print("=" * 60)
    
    # Step 1: Register and login
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_email = f"diet_test_{timestamp}@skinadvisor.test"
    
    register_data = {
        "email": test_email,
        "password": "testpass123",
        "name": "Diet Test User",
        "language": "en"
    }
    
    print("1. Registering test user...")
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    if response.status_code != 200:
        print(f"❌ Registration failed: {response.status_code}")
        return False
    
    token = response.json()['access_token']
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ User registered successfully")
    
    # Step 2: Create a scan with minimal image
    print("\n2. Creating scan to test diet recommendations...")
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    
    analyze_data = {
        "image_base64": test_image_b64,
        "language": "en"
    }
    
    response = requests.post(f"{BASE_URL}/scan/analyze", 
                           json=analyze_data, 
                           headers=headers, 
                           timeout=60)
    
    if response.status_code != 200:
        print(f"❌ Scan analyze failed: {response.status_code} - {response.text}")
        return False
    
    scan_result = response.json()
    print("✅ Scan created successfully")
    
    # Step 3: Check if diet_recommendations exists
    print("\n3. Checking diet recommendations in scan response...")
    if 'diet_recommendations' not in scan_result:
        print("❌ diet_recommendations field missing from scan response")
        print("Response keys:", list(scan_result.keys()))
        return False
    
    diet_recs = scan_result['diet_recommendations']
    print("✅ diet_recommendations field found")
    
    # Step 4: Verify structure
    print("\n4. Verifying diet recommendations structure...")
    required_fields = ['eat_more', 'avoid', 'hydration_tip', 'supplements_optional']
    
    for field in required_fields:
        if field not in diet_recs:
            print(f"❌ Missing required field: {field}")
            return False
        print(f"✅ {field}: Found")
    
    # Check data types and content
    if not isinstance(diet_recs['eat_more'], list):
        print("❌ eat_more should be a list")
        return False
    
    if not isinstance(diet_recs['avoid'], list):
        print("❌ avoid should be a list")
        return False
    
    if not isinstance(diet_recs['hydration_tip'], str):
        print("❌ hydration_tip should be a string")
        return False
    
    if not isinstance(diet_recs['supplements_optional'], list):
        print("❌ supplements_optional should be a list")
        return False
    
    print(f"✅ Structure validation passed")
    print(f"   - eat_more: {len(diet_recs['eat_more'])} items")
    print(f"   - avoid: {len(diet_recs['avoid'])} items")
    print(f"   - supplements_optional: {len(diet_recs['supplements_optional'])} items")
    print(f"   - hydration_tip: {len(diet_recs['hydration_tip'])} characters")
    
    # Step 5: Verify item structure
    print("\n5. Verifying item structures...")
    
    for item in diet_recs['eat_more']:
        if not isinstance(item, dict) or 'name' not in item or 'reason' not in item:
            print("❌ eat_more items should have 'name' and 'reason' fields")
            return False
    
    for item in diet_recs['avoid']:
        if not isinstance(item, dict) or 'name' not in item or 'reason' not in item:
            print("❌ avoid items should have 'name' and 'reason' fields")
            return False
    
    for item in diet_recs['supplements_optional']:
        if not isinstance(item, dict) or 'name' not in item or 'reason' not in item:
            print("❌ supplements_optional items should have 'name' and 'reason' fields")
            return False
    
    print("✅ All item structures are valid")
    
    # Step 6: Test deterministic behavior
    print("\n6. Testing deterministic behavior...")
    scan_id = scan_result['id']
    
    # Call scan detail endpoint twice
    response1 = requests.get(f"{BASE_URL}/scan/{scan_id}", headers=headers)
    response2 = requests.get(f"{BASE_URL}/scan/{scan_id}", headers=headers)
    
    if response1.status_code != 200 or response2.status_code != 200:
        print(f"❌ Scan detail failed: {response1.status_code}, {response2.status_code}")
        return False
    
    diet_recs1 = response1.json()['diet_recommendations']
    diet_recs2 = response2.json()['diet_recommendations']
    
    if diet_recs1 == diet_recs2:
        print("✅ Diet recommendations are deterministic")
    else:
        print("❌ Diet recommendations are not deterministic")
        return False
    
    # Step 7: Display sample recommendations
    print("\n7. Sample diet recommendations:")
    print("   Eat More:")
    for item in diet_recs['eat_more'][:3]:  # Show first 3
        print(f"     - {item['name']}: {item['reason']}")
    
    print("   Avoid:")
    for item in diet_recs['avoid'][:3]:  # Show first 3
        print(f"     - {item['name']}: {item['reason']}")
    
    print(f"   Hydration: {diet_recs['hydration_tip']}")
    
    print("   Supplements:")
    for item in diet_recs['supplements_optional'][:2]:  # Show first 2
        print(f"     - {item['name']}: {item['reason']}")
    
    print("\n🎉 All diet recommendations tests passed!")
    return True

if __name__ == "__main__":
    success = test_diet_recommendations()
    exit(0 if success else 1)