#!/usr/bin/env python3
"""
Debug scan limit enforcement issue
"""

import requests
import json
import uuid

BACKEND_URL = "https://skinsmart-ai-4.preview.emergentagent.com/api"
TEST_PASSWORD = "TestPass123!"

def test_scan_limit_debug():
    """Debug the scan limit enforcement"""
    
    # Create a new free user
    unique_id = str(uuid.uuid4())[:8]
    email = f"debug_scan_{unique_id}@test.com"
    
    user_data = {
        "email": email,
        "password": TEST_PASSWORD,
        "name": "Debug Scan User",
        "language": "en"
    }
    
    print(f"1. Registering user: {email}")
    response = requests.post(f"{BACKEND_URL}/auth/register", json=user_data)
    
    if response.status_code != 200:
        print(f"❌ Registration failed: {response.text}")
        return
    
    token = response.json().get("access_token")
    user = response.json().get("user", {})
    print(f"✅ User registered: plan={user.get('plan')}, scan_count={user.get('scan_count')}")
    
    # Simple test image
    test_image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    
    headers = {"Authorization": f"Bearer {token}"}
    scan_data = {
        "image_base64": test_image_b64,
        "language": "en"
    }
    
    print("\n2. First scan (should work)...")
    try:
        first_scan = requests.post(f"{BACKEND_URL}/scan/analyze", json=scan_data, headers=headers, timeout=30)
        print(f"First scan status: {first_scan.status_code}")
        
        if first_scan.status_code == 200:
            data = first_scan.json()
            print(f"✅ First scan successful: user_plan={data.get('user_plan')}")
            
            print("\n3. Second scan (should fail with 403)...")
            try:
                second_scan = requests.post(f"{BACKEND_URL}/scan/analyze", json=scan_data, headers=headers, timeout=30)
                print(f"Second scan status: {second_scan.status_code}")
                
                if second_scan.status_code == 403:
                    error_data = second_scan.json()
                    print(f"✅ Second scan correctly blocked: {error_data}")
                else:
                    print(f"❌ Second scan should return 403, got {second_scan.status_code}")
                    print(f"Response: {second_scan.text}")
                    
            except requests.exceptions.Timeout:
                print("❌ Second scan request timed out")
            except Exception as e:
                print(f"❌ Second scan error: {str(e)}")
        else:
            print(f"❌ First scan failed: {first_scan.text}")
            
    except requests.exceptions.Timeout:
        print("❌ First scan request timed out")
    except Exception as e:
        print(f"❌ First scan error: {str(e)}")

if __name__ == "__main__":
    test_scan_limit_debug()