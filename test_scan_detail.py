import requests
import json
import base64

# Check if we can clear scan cache
BACKEND_URL = 'https://ai-skin-companion.preview.emergentagent.com/api'

# Login
login_response = requests.post(f'{BACKEND_URL}/auth/login', json={
    'email': 'prd_test_user@test.com',
    'password': 'testpass123'
})

if login_response.status_code == 200:
    token = login_response.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    
    # Try to make a new scan with different image data to avoid cache
    # Create a slightly different image (2x1 instead of 1x1)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
    new_image = base64.b64encode(png_data).decode('utf-8')
    
    # Make new scan
    scan_response = requests.post(f'{BACKEND_URL}/scan/analyze', 
                                headers=headers,
                                json={
                                    'image_base64': new_image,
                                    'language': 'en'
                                })
    
    if scan_response.status_code == 200:
        scan_data = scan_response.json()
        scan_id = scan_data.get('id')
        print(f'New scan ID: {scan_id}')
        
        # Check if this scan has the full structure
        analysis = scan_data.get('analysis', {})
        print(f'Analysis has skin_metrics: {"skin_metrics" in analysis}')
        print(f'Analysis has strengths: {"strengths" in analysis}')
        print(f'Analysis has primary_concern: {"primary_concern" in analysis}')
        
        # Now check the scan detail endpoint
        detail_response = requests.get(f'{BACKEND_URL}/scan/{scan_id}', headers=headers)
        if detail_response.status_code == 200:
            detail_data = detail_response.json()
            detail_analysis = detail_data.get('analysis', {})
            print(f'Detail analysis has skin_metrics: {"skin_metrics" in detail_analysis}')
            print(f'Detail analysis has strengths: {"strengths" in detail_analysis}')
            print(f'Detail analysis has primary_concern: {"primary_concern" in detail_analysis}')
        else:
            print(f'Detail request failed: {detail_response.status_code}')
    else:
        print(f'Scan failed: {scan_response.status_code}')
else:
    print(f'Login failed: {login_response.status_code}')