from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import jwt
import bcrypt
import base64
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
import json
import re
import secrets
import hashlib

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'skincare_db')]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'skincare-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24 * 7  # 1 week

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

app = FastAPI(title="SkinAdvisor AI API", version="1.0.0")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    language: str = "en"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    skin_goals: Optional[List[str]] = []
    country: Optional[str] = None
    language: str = "en"

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    profile: Optional[UserProfile] = None
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class SkinAnalysisRequest(BaseModel):
    image_base64: str
    language: str = "en"

# New models for account management
class UpdateNameRequest(BaseModel):
    name: str

class UpdateEmailRequest(BaseModel):
    email: EmailStr
    password: str

class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

# ==================== DETERMINISTIC SCORING SYSTEM ====================

# Issue weights for score calculation (FIXED - DO NOT RANDOMIZE)
ISSUE_WEIGHTS = {
    'acne': 5,
    'dark_spots': 3,
    'hyperpigmentation': 3,
    'wrinkles': 4,
    'fine_lines': 2,
    'redness': 3,
    'rosacea': 4,
    'large_pores': 3,
    'dehydration': 4,
    'dryness': 3,
    'oiliness': 2,
    'uneven_tone': 2,
    'texture': 2,
    'blackheads': 2,
    'whiteheads': 2,
    'sun_damage': 4,
    'dark_circles': 2,
    'sensitivity': 3,
}

# Score ranges with labels
SCORE_LABELS = {
    (0, 39): {'label': 'poor', 'description': 'Poor skin condition'},
    (40, 59): {'label': 'below_average', 'description': 'Below average'},
    (60, 74): {'label': 'average', 'description': 'Average'},
    (75, 89): {'label': 'good', 'description': 'Good skin condition'},
    (90, 100): {'label': 'excellent', 'description': 'Excellent'},
}

def get_score_label(score: int) -> dict:
    """Get the label and description for a given score"""
    for (min_score, max_score), info in SCORE_LABELS.items():
        if min_score <= score <= max_score:
            return info
    return {'label': 'unknown', 'description': 'Unknown'}

def calculate_deterministic_score(issues: List[dict]) -> dict:
    """
    Calculate skin health score using DETERMINISTIC formula.
    Score is calculated ONLY from detected issues and their severity.
    LLM does NOT control this score.
    """
    base_score = 95  # Start with near-perfect score
    
    score_factors = []
    total_deduction = 0
    
    for issue in issues:
        issue_name = issue.get('name', '').lower().replace(' ', '_')
        severity = min(10, max(0, issue.get('severity', 0)))  # Clamp 0-10
        
        # Find matching weight
        weight = 2  # Default weight
        for key, w in ISSUE_WEIGHTS.items():
            if key in issue_name or issue_name in key:
                weight = w
                break
        
        # Calculate deduction: severity * weight
        deduction = severity * weight / 10  # Normalize to percentage
        total_deduction += deduction
        
        if severity > 0:
            severity_label = 'mild' if severity <= 3 else 'moderate' if severity <= 6 else 'severe'
            score_factors.append({
                'issue': issue.get('name', 'Unknown'),
                'severity': severity,
                'severity_label': severity_label,
                'deduction': round(deduction, 1)
            })
    
    # Calculate final score
    final_score = max(0, min(100, round(base_score - total_deduction)))
    
    # Sort factors by deduction (most impactful first)
    score_factors.sort(key=lambda x: x['deduction'], reverse=True)
    
    score_info = get_score_label(final_score)
    
    return {
        'score': final_score,
        'label': score_info['label'],
        'description': score_info['description'],
        'factors': score_factors[:5],  # Top 5 factors
        'base_score': base_score,
        'total_deduction': round(total_deduction, 1)
    }

def compute_image_hash(image_base64: str) -> str:
    """Compute a stable hash of the image for caching/comparison"""
    # Use first 10000 chars to create hash (for performance)
    sample = image_base64[:10000] if len(image_base64) > 10000 else image_base64
    return hashlib.sha256(sample.encode()).hexdigest()[:16]

# ==================== AUTH HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_reset_token() -> str:
    return secrets.token_urlsafe(32)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get('user_id')
        user = await db.users.find_one({'id': user_id})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({'email': user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    user = {
        'id': user_id,
        'email': user_data.email,
        'password': hash_password(user_data.password),
        'name': user_data.name,
        'profile': {
            'language': user_data.language,
            'age': None,
            'gender': None,
            'skin_goals': [],
            'country': None
        },
        'created_at': datetime.utcnow()
    }
    
    await db.users.insert_one(user)
    token = create_token(user_id)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_data.email,
            name=user_data.name,
            profile=UserProfile(**user['profile']),
            created_at=user['created_at']
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({'email': credentials.email})
    if not user or not verify_password(credentials.password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_token(user['id'])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            profile=UserProfile(**user.get('profile', {})) if user.get('profile') else None,
            created_at=user['created_at']
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user['id'],
        email=current_user['email'],
        name=current_user['name'],
        profile=UserProfile(**current_user.get('profile', {})) if current_user.get('profile') else None,
        created_at=current_user['created_at']
    )

# ==================== FORGOT PASSWORD ====================

@api_router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    user = await db.users.find_one({'email': request.email})
    if not user:
        return {"message": "If this email exists, a reset link has been sent"}
    
    reset_token = create_reset_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    await db.password_resets.delete_many({'user_id': user['id']})
    await db.password_resets.insert_one({
        'user_id': user['id'],
        'token': reset_token,
        'expires_at': expires_at,
        'created_at': datetime.utcnow()
    })
    
    return {
        "message": "Password reset token generated",
        "reset_token": reset_token,
        "expires_in": "1 hour"
    }

@api_router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    reset_record = await db.password_resets.find_one({'token': request.token})
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    if reset_record['expires_at'] < datetime.utcnow():
        await db.password_resets.delete_one({'token': request.token})
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    await db.users.update_one(
        {'id': reset_record['user_id']},
        {'$set': {'password': hash_password(request.new_password)}}
    )
    
    await db.password_resets.delete_one({'token': request.token})
    
    return {"message": "Password reset successfully"}

# ==================== PROFILE ROUTES ====================

@api_router.put("/profile", response_model=UserResponse)
async def update_profile(profile: UserProfile, current_user: dict = Depends(get_current_user)):
    await db.users.update_one(
        {'id': current_user['id']},
        {'$set': {'profile': profile.dict()}}
    )
    updated_user = await db.users.find_one({'id': current_user['id']})
    return UserResponse(
        id=updated_user['id'],
        email=updated_user['email'],
        name=updated_user['name'],
        profile=UserProfile(**updated_user.get('profile', {})),
        created_at=updated_user['created_at']
    )

@api_router.put("/profile/name", response_model=UserResponse)
async def update_name(request: UpdateNameRequest, current_user: dict = Depends(get_current_user)):
    if not request.name or len(request.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters")
    
    await db.users.update_one(
        {'id': current_user['id']},
        {'$set': {'name': request.name.strip()}}
    )
    updated_user = await db.users.find_one({'id': current_user['id']})
    return UserResponse(
        id=updated_user['id'],
        email=updated_user['email'],
        name=updated_user['name'],
        profile=UserProfile(**updated_user.get('profile', {})) if updated_user.get('profile') else None,
        created_at=updated_user['created_at']
    )

@api_router.put("/profile/email", response_model=UserResponse)
async def update_email(request: UpdateEmailRequest, current_user: dict = Depends(get_current_user)):
    if not verify_password(request.password, current_user['password']):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    existing = await db.users.find_one({'email': request.email})
    if existing and existing['id'] != current_user['id']:
        raise HTTPException(status_code=400, detail="Email already in use")
    
    await db.users.update_one(
        {'id': current_user['id']},
        {'$set': {'email': request.email}}
    )
    updated_user = await db.users.find_one({'id': current_user['id']})
    return UserResponse(
        id=updated_user['id'],
        email=updated_user['email'],
        name=updated_user['name'],
        profile=UserProfile(**updated_user.get('profile', {})) if updated_user.get('profile') else None,
        created_at=updated_user['created_at']
    )

@api_router.put("/profile/password")
async def update_password(request: UpdatePasswordRequest, current_user: dict = Depends(get_current_user)):
    if not verify_password(request.current_password, current_user['password']):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    await db.users.update_one(
        {'id': current_user['id']},
        {'$set': {'password': hash_password(request.new_password)}}
    )
    
    return {"message": "Password updated successfully"}

@api_router.delete("/account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    await db.scans.delete_many({'user_id': current_user['id']})
    await db.password_resets.delete_many({'user_id': current_user['id']})
    await db.users.delete_one({'id': current_user['id']})
    return {"message": "Account deleted successfully"}

# ==================== DETERMINISTIC AI SKIN ANALYSIS ====================

LANGUAGE_PROMPTS = {
    'en': 'English',
    'fr': 'French',
    'tr': 'Turkish',
    'it': 'Italian',
    'es': 'Spanish',
    'de': 'German',
    'ar': 'Arabic',
    'zh': 'Simplified Chinese',
    'hi': 'Hindi'
}

def parse_json_response(response: str) -> dict:
    """Parse JSON from AI response with multiple fallback strategies"""
    # Try to find JSON in code blocks first
    code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object directly
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Try to clean and parse the entire response
    try:
        cleaned = response.strip()
        if cleaned.startswith('{'):
            return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    return None

async def analyze_skin_with_ai(image_base64: str, language: str = 'en') -> dict:
    """
    Analyze skin using OpenAI GPT-4o vision with DETERMINISTIC settings.
    Temperature = 0 for consistent results.
    """
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    
    # DETERMINISTIC PROMPT - Very specific instructions for consistent output
    system_prompt = f"""You are a professional dermatological AI analyzer for cosmetic skin assessment.
Your analysis must be CONSISTENT and DETERMINISTIC - the same image must produce the same results.

CRITICAL RULES:
1. Analyze ONLY what is visible in the image
2. Use FIXED thresholds for classification
3. Be PRECISE with severity ratings (0-10 scale)
4. Do NOT guess or assume - only report observed conditions

SKIN TYPE CLASSIFICATION (use ONE):
- "oily": Visible shine, enlarged pores in T-zone
- "dry": Flaky patches, tight appearance, fine lines from dehydration
- "combination": Oily T-zone with dry cheeks
- "normal": Balanced, minimal issues, healthy appearance
- "sensitive": Visible redness, reactive appearance

ISSUE DETECTION - For each issue provide:
- name: Specific issue name
- severity: Integer 0-10 (0=none, 1-3=mild, 4-6=moderate, 7-10=severe)
- confidence: Float 0.0-1.0 (how certain you are)
- description: Brief factual observation in {lang_name}

SEVERITY GUIDELINES:
- 0: Not present
- 1-3: Mild - barely noticeable, minor concern
- 4-6: Moderate - clearly visible, should address
- 7-10: Severe - prominent, needs attention

Respond ONLY with valid JSON in {lang_name}. No markdown, no explanation, just JSON:
{{"skin_type": "type", "skin_type_confidence": 0.9, "skin_type_description": "description", "issues": [{{"name": "issue", "severity": 5, "confidence": 0.8, "description": "observation"}}], "recommendations": ["advice1", "advice2"]}}"""
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"skin-analysis-deterministic",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o").with_params(temperature=0)  # DETERMINISTIC: temp=0
        
        image_content = ImageContent(image_base64=image_base64)
        
        user_message = UserMessage(
            text=f"""Analyze this facial skin image systematically:

1. SKIN TYPE: Classify based on visible characteristics
2. ISSUES: Detect and rate each visible issue (severity 0-10, confidence 0-1)
3. RECOMMENDATIONS: Provide 3-5 specific skincare recommendations

Check for: acne, dark spots, wrinkles, fine lines, redness, large pores, dehydration, oiliness, uneven tone, blackheads, texture issues, sun damage, dark circles.

Return ONLY JSON. Respond in {lang_name}.""",
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        logger.info(f"AI response length: {len(response)}")
        
        result = parse_json_response(response)
        
        if result:
            # Validate and normalize the response
            validated = validate_ai_response(result, language)
            return validated
        else:
            logger.warning(f"Could not parse AI response: {response[:300]}")
            return get_fallback_analysis(language)
            
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        return get_fallback_analysis(language)

def validate_ai_response(result: dict, language: str) -> dict:
    """Validate and normalize AI response to ensure consistency"""
    
    # Ensure skin_type is valid
    valid_skin_types = ['oily', 'dry', 'combination', 'normal', 'sensitive']
    skin_type = result.get('skin_type', 'normal').lower()
    if skin_type not in valid_skin_types:
        skin_type = 'combination'
    
    # Ensure skin_type_confidence
    skin_type_confidence = result.get('skin_type_confidence', 0.8)
    if not isinstance(skin_type_confidence, (int, float)):
        skin_type_confidence = 0.8
    skin_type_confidence = max(0.0, min(1.0, float(skin_type_confidence)))
    
    # Validate issues
    validated_issues = []
    raw_issues = result.get('issues', [])
    
    for issue in raw_issues:
        if not isinstance(issue, dict):
            continue
            
        name = issue.get('name', '')
        if not name:
            continue
            
        # Clamp severity to 0-10
        severity = issue.get('severity', 0)
        if not isinstance(severity, (int, float)):
            severity = 0
        severity = int(max(0, min(10, severity)))
        
        # Clamp confidence to 0-1
        confidence = issue.get('confidence', 0.7)
        if not isinstance(confidence, (int, float)):
            confidence = 0.7
        confidence = max(0.0, min(1.0, float(confidence)))
        
        # Only include issues with severity > 0 and confidence > 0.3
        if severity > 0 and confidence > 0.3:
            validated_issues.append({
                'name': str(name),
                'severity': severity,
                'confidence': round(confidence, 2),
                'description': issue.get('description', f'{name} detected')
            })
    
    # Sort by severity (highest first)
    validated_issues.sort(key=lambda x: x['severity'], reverse=True)
    
    # Validate recommendations
    recommendations = result.get('recommendations', [])
    if not isinstance(recommendations, list):
        recommendations = []
    recommendations = [str(r) for r in recommendations if r][:5]
    
    if not recommendations:
        recommendations = [
            "Maintain a consistent skincare routine",
            "Use sunscreen daily",
            "Stay hydrated"
        ]
    
    return {
        'skin_type': skin_type,
        'skin_type_confidence': round(skin_type_confidence, 2),
        'skin_type_description': result.get('skin_type_description', f'Your skin type appears to be {skin_type}'),
        'issues': validated_issues,
        'recommendations': recommendations
    }

def get_fallback_analysis(language: str) -> dict:
    """Return a safe fallback analysis when AI fails"""
    return {
        'skin_type': 'normal',
        'skin_type_confidence': 0.5,
        'skin_type_description': 'Unable to fully analyze the image. Please try with better lighting.',
        'issues': [],
        'recommendations': [
            'Use a gentle cleanser twice daily',
            'Apply moisturizer appropriate for your skin type',
            'Use sunscreen daily',
            'Stay hydrated'
        ]
    }

async def generate_routine_with_ai(analysis: dict, language: str = 'en') -> dict:
    """Generate skincare routine based on analysis with DETERMINISTIC settings"""
    if not EMERGENT_LLM_KEY:
        return get_fallback_routine(analysis.get('skin_type', 'normal'))
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    skin_type = analysis.get('skin_type', 'normal')
    issues = analysis.get('issues', [])
    
    # Create deterministic prompt based on skin type and issues
    issues_text = ', '.join([f"{i['name']} (severity {i['severity']})" for i in issues[:5]]) if issues else 'No major issues'
    
    system_prompt = f"""You are a skincare routine expert. Create a personalized routine based on skin analysis.

RULES:
1. Tailor routine to skin type: {skin_type}
2. Address detected issues: {issues_text}
3. Use standard skincare steps
4. Be specific with instructions
5. Recommend generic product types (not brands)

Respond ONLY with JSON in {lang_name}:
{{"morning_routine": [{{"order": 1, "step_name": "name", "product_type": "type", "instructions": "how to use", "ingredients_to_look_for": ["ing1"], "ingredients_to_avoid": ["ing1"]}}], "evening_routine": [...], "weekly_routine": [...], "products": [{{"product_type": "type", "name": "generic name", "description": "why", "key_ingredients": ["ing"], "suitable_for": ["{skin_type}"], "price_range": "$$"}}]}}"""
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"routine-gen-deterministic",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o").with_params(temperature=0)  # DETERMINISTIC
        
        user_message = UserMessage(
            text=f"""Create skincare routine for:
- Skin type: {skin_type}
- Issues: {issues_text}

Provide morning (4-5 steps), evening (4-5 steps), weekly (1-2 treatments), and 5-7 product recommendations.
Return ONLY JSON in {lang_name}."""
        )
        
        response = await chat.send_message(user_message)
        result = parse_json_response(response)
        
        if result:
            return validate_routine_response(result, skin_type)
        else:
            return get_fallback_routine(skin_type)
            
    except Exception as e:
        logger.error(f"Routine generation error: {str(e)}")
        return get_fallback_routine(skin_type)

def validate_routine_response(result: dict, skin_type: str) -> dict:
    """Validate routine response structure"""
    validated = {
        'morning_routine': [],
        'evening_routine': [],
        'weekly_routine': [],
        'products': []
    }
    
    for key in ['morning_routine', 'evening_routine', 'weekly_routine']:
        routine = result.get(key, [])
        if isinstance(routine, list):
            for step in routine:
                if isinstance(step, dict) and step.get('step_name'):
                    validated[key].append({
                        'order': step.get('order', len(validated[key]) + 1),
                        'step_name': str(step.get('step_name', '')),
                        'product_type': str(step.get('product_type', 'unknown')),
                        'instructions': str(step.get('instructions', '')),
                        'ingredients_to_look_for': step.get('ingredients_to_look_for', []),
                        'ingredients_to_avoid': step.get('ingredients_to_avoid', [])
                    })
    
    products = result.get('products', [])
    if isinstance(products, list):
        for product in products:
            if isinstance(product, dict) and product.get('product_type'):
                validated['products'].append({
                    'product_type': str(product.get('product_type', '')),
                    'name': str(product.get('name', '')),
                    'description': str(product.get('description', '')),
                    'key_ingredients': product.get('key_ingredients', []),
                    'suitable_for': product.get('suitable_for', [skin_type]),
                    'price_range': str(product.get('price_range', '$$'))
                })
    
    # If routines are empty, use fallback
    if not validated['morning_routine']:
        return get_fallback_routine(skin_type)
    
    return validated

def get_fallback_routine(skin_type: str) -> dict:
    """Return a basic fallback routine"""
    return {
        "morning_routine": [
            {"order": 1, "step_name": "Cleanser", "product_type": "cleanser", "instructions": "Gently massage onto damp skin, rinse with lukewarm water", "ingredients_to_look_for": ["glycerin", "ceramides"], "ingredients_to_avoid": ["alcohol", "sulfates"]},
            {"order": 2, "step_name": "Toner", "product_type": "toner", "instructions": "Apply with cotton pad or pat into skin", "ingredients_to_look_for": ["niacinamide", "hyaluronic acid"], "ingredients_to_avoid": ["alcohol"]},
            {"order": 3, "step_name": "Moisturizer", "product_type": "moisturizer", "instructions": "Apply evenly to face and neck", "ingredients_to_look_for": ["ceramides", "hyaluronic acid"], "ingredients_to_avoid": ["fragrance"]},
            {"order": 4, "step_name": "Sunscreen", "product_type": "sunscreen", "instructions": "Apply generously 15 minutes before sun exposure", "ingredients_to_look_for": ["SPF 30+", "zinc oxide"], "ingredients_to_avoid": ["oxybenzone"]}
        ],
        "evening_routine": [
            {"order": 1, "step_name": "Cleanser", "product_type": "cleanser", "instructions": "Double cleanse to remove makeup and sunscreen", "ingredients_to_look_for": ["oil-based first", "water-based second"], "ingredients_to_avoid": ["harsh sulfates"]},
            {"order": 2, "step_name": "Treatment Serum", "product_type": "serum", "instructions": "Apply to clean, dry skin", "ingredients_to_look_for": ["retinol", "vitamin C"], "ingredients_to_avoid": ["mixing actives"]},
            {"order": 3, "step_name": "Night Cream", "product_type": "moisturizer", "instructions": "Apply before bed", "ingredients_to_look_for": ["peptides", "ceramides"], "ingredients_to_avoid": ["heavy fragrances"]}
        ],
        "weekly_routine": [
            {"order": 1, "step_name": "Exfoliation", "product_type": "treatment", "instructions": "Use 1-2 times per week", "ingredients_to_look_for": ["AHA", "BHA"], "ingredients_to_avoid": ["physical scrubs"]},
            {"order": 2, "step_name": "Face Mask", "product_type": "treatment", "instructions": "Apply for 10-15 minutes, then rinse", "ingredients_to_look_for": ["clay", "hyaluronic acid"], "ingredients_to_avoid": ["irritating ingredients"]}
        ],
        "products": [
            {"product_type": "cleanser", "name": "Gentle Foaming Cleanser", "description": "A mild cleanser suitable for daily use", "key_ingredients": ["glycerin", "ceramides"], "suitable_for": [skin_type], "price_range": "$$"},
            {"product_type": "moisturizer", "name": "Hydrating Moisturizer", "description": "Lightweight hydration for all skin types", "key_ingredients": ["hyaluronic acid", "niacinamide"], "suitable_for": [skin_type], "price_range": "$$"},
            {"product_type": "sunscreen", "name": "Daily SPF 50 Sunscreen", "description": "Broad spectrum protection", "key_ingredients": ["zinc oxide", "vitamin E"], "suitable_for": ["all skin types"], "price_range": "$$"},
            {"product_type": "serum", "name": "Vitamin C Serum", "description": "Brightening and antioxidant protection", "key_ingredients": ["vitamin C", "vitamin E"], "suitable_for": [skin_type], "price_range": "$$$"}
        ]
    }

# ==================== SCAN ROUTES ====================

@api_router.post("/scan/analyze")
async def analyze_skin(
    request: SkinAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze skin from base64 image using DETERMINISTIC AI analysis.
    Score is calculated using a FIXED FORMULA, not by the LLM.
    """
    try:
        language = request.language or current_user.get('profile', {}).get('language', 'en')
        
        # Compute image hash for tracking/caching
        image_hash = compute_image_hash(request.image_base64)
        
        # Check for cached result (same image = same result)
        cached = await db.scan_cache.find_one({'image_hash': image_hash, 'language': language})
        if cached:
            logger.info(f"Using cached analysis for image hash: {image_hash}")
            # Return cached result but create new scan record
            analysis = cached['analysis']
            routine = cached['routine']
            products = cached['products']
            score_data = cached['score_data']
        else:
            # Perform AI analysis
            analysis = await analyze_skin_with_ai(request.image_base64, language)
            
            # Calculate DETERMINISTIC score from issues (NOT from LLM)
            score_data = calculate_deterministic_score(analysis.get('issues', []))
            
            # Generate routine
            routine_data = await generate_routine_with_ai(analysis, language)
            routine = {
                'morning_routine': routine_data.get('morning_routine', []),
                'evening_routine': routine_data.get('evening_routine', []),
                'weekly_routine': routine_data.get('weekly_routine', [])
            }
            products = routine_data.get('products', [])
            
            # Cache the result
            await db.scan_cache.update_one(
                {'image_hash': image_hash, 'language': language},
                {'$set': {
                    'image_hash': image_hash,
                    'language': language,
                    'analysis': analysis,
                    'routine': routine,
                    'products': products,
                    'score_data': score_data,
                    'created_at': datetime.utcnow()
                }},
                upsert=True
            )
        
        # Create scan record with all data
        scan = {
            'id': str(uuid.uuid4()),
            'user_id': current_user['id'],
            'image_base64': request.image_base64,
            'image_hash': image_hash,
            'analysis': {
                'skin_type': analysis.get('skin_type'),
                'skin_type_confidence': analysis.get('skin_type_confidence', 0.8),
                'skin_type_description': analysis.get('skin_type_description'),
                'issues': analysis.get('issues', []),
                'recommendations': analysis.get('recommendations', [])
            },
            'score_data': score_data,
            'routine': routine,
            'products': products,
            'created_at': datetime.utcnow(),
            'language': language
        }
        
        await db.scans.insert_one(scan)
        
        return {
            'id': scan['id'],
            'analysis': {
                'skin_type': scan['analysis']['skin_type'],
                'skin_type_confidence': scan['analysis']['skin_type_confidence'],
                'skin_type_description': scan['analysis']['skin_type_description'],
                'issues': scan['analysis']['issues'],
                'recommendations': scan['analysis']['recommendations'],
                # SCORE DATA - calculated deterministically
                'overall_score': score_data['score'],
                'score_label': score_data['label'],
                'score_description': score_data['description'],
                'score_factors': score_data['factors']
            },
            'routine': scan['routine'],
            'products': scan['products'],
            'created_at': scan['created_at'].isoformat(),
            'image_hash': image_hash
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scan analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/scan/history")
async def get_scan_history(current_user: dict = Depends(get_current_user)):
    """Get user's scan history with score data for progress tracking"""
    scans = await db.scans.find(
        {'user_id': current_user['id']}
    ).sort('created_at', -1).to_list(100)
    
    return [
        {
            'id': scan['id'],
            'analysis': scan.get('analysis'),
            'score_data': scan.get('score_data'),
            'created_at': scan['created_at'].isoformat() if isinstance(scan['created_at'], datetime) else scan['created_at'],
            'has_image': bool(scan.get('image_base64')),
            'image_hash': scan.get('image_hash')
        }
        for scan in scans
    ]

@api_router.get("/scan/{scan_id}")
async def get_scan_detail(scan_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed scan result"""
    scan = await db.scans.find_one({
        'id': scan_id,
        'user_id': current_user['id']
    })
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    analysis = scan.get('analysis', {})
    score_data = scan.get('score_data', {})
    
    return {
        'id': scan['id'],
        'image_base64': scan.get('image_base64'),
        'image_hash': scan.get('image_hash'),
        'analysis': {
            'skin_type': analysis.get('skin_type'),
            'skin_type_confidence': analysis.get('skin_type_confidence', 0.8),
            'skin_type_description': analysis.get('skin_type_description'),
            'issues': analysis.get('issues', []),
            'recommendations': analysis.get('recommendations', []),
            'overall_score': score_data.get('score', 75),
            'score_label': score_data.get('label', 'good'),
            'score_description': score_data.get('description', 'Good skin condition'),
            'score_factors': score_data.get('factors', [])
        },
        'routine': scan.get('routine'),
        'products': scan.get('products'),
        'created_at': scan['created_at'].isoformat() if isinstance(scan['created_at'], datetime) else scan['created_at']
    }

@api_router.delete("/scan/{scan_id}")
async def delete_scan(scan_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a scan"""
    result = await db.scans.delete_one({
        'id': scan_id,
        'user_id': current_user['id']
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return {"message": "Scan deleted successfully"}

# ==================== PROGRESS COMPARISON ====================

@api_router.get("/scan/compare/{scan_id_1}/{scan_id_2}")
async def compare_scans(scan_id_1: str, scan_id_2: str, current_user: dict = Depends(get_current_user)):
    """Compare two scans to show progress"""
    scan1 = await db.scans.find_one({'id': scan_id_1, 'user_id': current_user['id']})
    scan2 = await db.scans.find_one({'id': scan_id_2, 'user_id': current_user['id']})
    
    if not scan1 or not scan2:
        raise HTTPException(status_code=404, detail="One or both scans not found")
    
    score1 = scan1.get('score_data', {}).get('score', 75)
    score2 = scan2.get('score_data', {}).get('score', 75)
    
    issues1 = {i['name'].lower(): i['severity'] for i in scan1.get('analysis', {}).get('issues', [])}
    issues2 = {i['name'].lower(): i['severity'] for i in scan2.get('analysis', {}).get('issues', [])}
    
    # Calculate changes
    issue_changes = []
    all_issues = set(issues1.keys()) | set(issues2.keys())
    for issue in all_issues:
        old = issues1.get(issue, 0)
        new = issues2.get(issue, 0)
        if old != new:
            change = new - old
            issue_changes.append({
                'issue': issue,
                'old_severity': old,
                'new_severity': new,
                'change': change,
                'improved': change < 0
            })
    
    return {
        'scan1': {
            'id': scan1['id'],
            'date': scan1['created_at'].isoformat() if isinstance(scan1['created_at'], datetime) else scan1['created_at'],
            'score': score1
        },
        'scan2': {
            'id': scan2['id'],
            'date': scan2['created_at'].isoformat() if isinstance(scan2['created_at'], datetime) else scan2['created_at'],
            'score': score2
        },
        'score_change': score2 - score1,
        'score_improved': score2 > score1,
        'issue_changes': issue_changes
    }

# ==================== TRANSLATIONS ====================

BASE_TRANSLATIONS = {
    'en': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Welcome',
        'login': 'Login',
        'register': 'Register',
        'email': 'Email',
        'password': 'Password',
        'name': 'Name',
        'scan_skin': 'Scan Your Skin',
        'my_routines': 'My Routines',
        'progress': 'Progress',
        'profile': 'Profile',
        'settings': 'Settings',
        'logout': 'Logout',
        'morning_routine': 'Morning Routine',
        'evening_routine': 'Evening Routine',
        'weekly_routine': 'Weekly Routine',
        'skin_type': 'Skin Type',
        'skin_issues': 'Skin Issues',
        'overall_score': 'Overall Score',
        'recommendations': 'Recommendations',
        'products': 'Products',
        'take_photo': 'Take Photo',
        'upload_photo': 'Upload Photo',
        'analyzing': 'Analyzing your skin...',
        'analysis_complete': 'Analysis Complete',
        'view_results': 'View Results',
        'disclaimer': 'This analysis is for cosmetic guidance only and is not a medical diagnosis.',
        'language': 'Language',
        'dark_mode': 'Dark Mode',
        'delete_account': 'Delete Account',
        'confirm_delete': 'Are you sure you want to delete your account?',
        'cancel': 'Cancel',
        'confirm': 'Confirm',
        'error': 'Error',
        'success': 'Success',
        'loading': 'Loading...',
        'no_scans': 'No scans yet',
        'start_first_scan': 'Start your first skin scan',
        'oily': 'Oily',
        'dry': 'Dry',
        'combination': 'Combination',
        'normal': 'Normal',
        'sensitive': 'Sensitive',
        'home': 'Home',
        'change_name': 'Change Name',
        'change_email': 'Change Email',
        'change_password': 'Change Password',
        'forgot_password': 'Forgot Password?',
        'current_password': 'Current Password',
        'new_password': 'New Password',
        'confirm_password': 'Confirm Password',
        'reset_password': 'Reset Password',
        'account_settings': 'Account Settings',
        'score_poor': 'Poor skin condition',
        'score_below_average': 'Below average',
        'score_average': 'Average',
        'score_good': 'Good skin condition',
        'score_excellent': 'Excellent',
        'score_info': 'Score represents overall skin health based on detected issues and their severity.',
        'main_factors': 'Main factors affecting your score',
        'mild': 'mild',
        'moderate': 'moderate',
        'severe': 'severe',
        'confidence': 'confidence'
    },
    'fr': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Bienvenue',
        'login': 'Connexion',
        'register': "S'inscrire",
        'score_poor': 'Mauvais état de la peau',
        'score_below_average': 'En dessous de la moyenne',
        'score_average': 'Moyenne',
        'score_good': 'Bon état de la peau',
        'score_excellent': 'Excellent',
        'score_info': 'Le score représente la santé globale de la peau en fonction des problèmes détectés et de leur gravité.',
        'main_factors': 'Principaux facteurs affectant votre score',
        'mild': 'léger',
        'moderate': 'modéré',
        'severe': 'sévère',
        'home': 'Accueil'
    },
    'tr': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Hoş geldiniz',
        'score_poor': 'Kötü cilt durumu',
        'score_below_average': 'Ortalamanın altında',
        'score_average': 'Ortalama',
        'score_good': 'İyi cilt durumu',
        'score_excellent': 'Mükemmel',
        'home': 'Ana Sayfa'
    },
    'it': {'app_name': 'SkinAdvisor AI', 'welcome': 'Benvenuto', 'home': 'Home'},
    'es': {'app_name': 'SkinAdvisor AI', 'welcome': 'Bienvenido', 'home': 'Inicio'},
    'de': {'app_name': 'SkinAdvisor AI', 'welcome': 'Willkommen', 'home': 'Startseite'},
    'ar': {'app_name': 'SkinAdvisor AI', 'welcome': 'مرحباً', 'home': 'الرئيسية'},
    'zh': {'app_name': 'SkinAdvisor AI', 'welcome': '欢迎', 'home': '首页'},
    'hi': {'app_name': 'SkinAdvisor AI', 'welcome': 'स्वागत है', 'home': 'होम'}
}

@api_router.get("/translations/{language}")
async def get_translations(language: str):
    if language not in BASE_TRANSLATIONS:
        language = 'en'
    translations = {**BASE_TRANSLATIONS['en'], **BASE_TRANSLATIONS.get(language, {})}
    return translations

@api_router.get("/languages")
async def get_languages():
    return [
        {'code': 'en', 'name': 'English', 'rtl': False},
        {'code': 'fr', 'name': 'Français', 'rtl': False},
        {'code': 'tr', 'name': 'Türkçe', 'rtl': False},
        {'code': 'it', 'name': 'Italiano', 'rtl': False},
        {'code': 'es', 'name': 'Español', 'rtl': False},
        {'code': 'de', 'name': 'Deutsch', 'rtl': False},
        {'code': 'ar', 'name': 'العربية', 'rtl': True},
        {'code': 'zh', 'name': '中文', 'rtl': False},
        {'code': 'hi', 'name': 'हिन्दी', 'rtl': False}
    ]

# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "SkinAdvisor AI API", "version": "2.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
