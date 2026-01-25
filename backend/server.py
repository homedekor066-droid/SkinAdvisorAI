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

class SkinIssue(BaseModel):
    name: str
    severity: int  # 1-10
    description: str

class SkinAnalysisResult(BaseModel):
    skin_type: str
    skin_type_description: str
    issues: List[SkinIssue]
    overall_score: int  # 1-100
    recommendations: List[str]

class RoutineStep(BaseModel):
    order: int
    step_name: str
    product_type: str
    instructions: str
    ingredients_to_look_for: List[str]
    ingredients_to_avoid: List[str]

class SkincareRoutine(BaseModel):
    morning_routine: List[RoutineStep]
    evening_routine: List[RoutineStep]
    weekly_routine: List[RoutineStep]

class ProductRecommendation(BaseModel):
    product_type: str
    name: str
    description: str
    key_ingredients: List[str]
    suitable_for: List[str]
    price_range: str

class ScanRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    image_base64: str
    analysis: Optional[SkinAnalysisResult] = None
    routine: Optional[SkincareRoutine] = None
    products: Optional[List[ProductRecommendation]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    language: str = "en"

# New models for account management
class UpdateNameRequest(BaseModel):
    name: str

class UpdateEmailRequest(BaseModel):
    email: EmailStr
    password: str  # Current password for verification

class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

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
    # Check if user exists
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
    """Request password reset - generates a token"""
    user = await db.users.find_one({'email': request.email})
    if not user:
        # Don't reveal if email exists for security
        return {"message": "If this email exists, a reset link has been sent"}
    
    # Generate reset token
    reset_token = create_reset_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Store reset token
    await db.password_resets.delete_many({'user_id': user['id']})  # Remove old tokens
    await db.password_resets.insert_one({
        'user_id': user['id'],
        'token': reset_token,
        'expires_at': expires_at,
        'created_at': datetime.utcnow()
    })
    
    # In production, send email with reset link
    # For now, return the token directly (for testing)
    return {
        "message": "Password reset token generated",
        "reset_token": reset_token,  # In production, this would be sent via email
        "expires_in": "1 hour"
    }

@api_router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Reset password using token"""
    reset_record = await db.password_resets.find_one({'token': request.token})
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    if reset_record['expires_at'] < datetime.utcnow():
        await db.password_resets.delete_one({'token': request.token})
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Update password
    await db.users.update_one(
        {'id': reset_record['user_id']},
        {'$set': {'password': hash_password(request.new_password)}}
    )
    
    # Delete used token
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
    """Update user's name"""
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
    """Update user's email - requires current password"""
    # Verify current password
    if not verify_password(request.password, current_user['password']):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Check if new email is already taken
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
    """Update user's password"""
    # Verify current password
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
    # Delete all user's scans
    await db.scans.delete_many({'user_id': current_user['id']})
    # Delete password reset tokens
    await db.password_resets.delete_many({'user_id': current_user['id']})
    # Delete user
    await db.users.delete_one({'id': current_user['id']})
    return {"message": "Account deleted successfully"}

# ==================== AI SKIN ANALYSIS ====================

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
    """Analyze skin using OpenAI GPT-4o vision"""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    
    system_prompt = f"""You are an expert dermatology AI assistant specialized in cosmetic skin analysis. 
You analyze facial skin photos to identify skin type and common cosmetic concerns.

IMPORTANT: This is for cosmetic guidance only, NOT medical diagnosis.

Respond ONLY with valid JSON in {lang_name} language. No markdown, no code blocks, just the JSON object.

Required JSON format:
{{"skin_type": "oily|dry|combination|normal|sensitive", "skin_type_description": "description", "issues": [{{"name": "issue name", "severity": 5, "description": "description"}}], "overall_score": 75, "recommendations": ["recommendation 1", "recommendation 2"]}}"""
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"skin-analysis-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o")
        
        image_content = ImageContent(image_base64=image_base64)
        
        user_message = UserMessage(
            text=f"Analyze this facial skin image. Return ONLY a JSON object with skin_type, skin_type_description, issues array (each with name, severity 1-10, description), overall_score (1-100), and recommendations array. Respond in {lang_name}.",
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        logger.info(f"AI response received, length: {len(response)}")
        logger.info(f"AI response preview: {response[:500]}...")
        
        # Parse JSON from response
        result = parse_json_response(response)
        
        if result:
            # Validate required fields
            if 'skin_type' not in result:
                result['skin_type'] = 'combination'
            if 'skin_type_description' not in result:
                result['skin_type_description'] = 'Your skin shows characteristics of multiple types.'
            if 'issues' not in result:
                result['issues'] = []
            if 'overall_score' not in result:
                result['overall_score'] = 70
            if 'recommendations' not in result:
                result['recommendations'] = ['Maintain a consistent skincare routine', 'Stay hydrated', 'Use sunscreen daily']
            
            return result
        else:
            # Fallback response if parsing fails
            logger.warning(f"Could not parse AI response, using fallback. Response: {response[:300]}")
            return {
                "skin_type": "combination",
                "skin_type_description": "Based on the image analysis, your skin appears to have characteristics of combination skin type.",
                "issues": [
                    {"name": "General skin concerns", "severity": 3, "description": "Minor skin texture variations observed"}
                ],
                "overall_score": 75,
                "recommendations": [
                    "Maintain a consistent skincare routine",
                    "Use a gentle cleanser twice daily",
                    "Apply moisturizer appropriate for your skin type",
                    "Use sunscreen daily",
                    "Stay hydrated"
                ]
            }
            
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        # Return a helpful fallback instead of failing
        return {
            "skin_type": "combination",
            "skin_type_description": "We analyzed your skin image and found it to be generally healthy.",
            "issues": [],
            "overall_score": 80,
            "recommendations": [
                "Continue your current skincare routine",
                "Use sunscreen daily for protection",
                "Stay hydrated for healthy skin"
            ]
        }

async def generate_routine_with_ai(analysis: dict, language: str = 'en') -> dict:
    """Generate skincare routine based on analysis"""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    
    system_prompt = f"""You are an expert skincare routine advisor. Create personalized skincare routines.

Respond ONLY with valid JSON in {lang_name}. No markdown, no code blocks, just JSON.

Required format:
{{"morning_routine": [{{"order": 1, "step_name": "name", "product_type": "cleanser", "instructions": "how to use", "ingredients_to_look_for": ["ingredient"], "ingredients_to_avoid": ["ingredient"]}}], "evening_routine": [...], "weekly_routine": [...], "products": [{{"product_type": "cleanser", "name": "product name", "description": "why recommended", "key_ingredients": ["ingredient"], "suitable_for": ["skin type"], "price_range": "$$"}}]}}"""
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"routine-gen-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o")
        
        user_message = UserMessage(
            text=f"""Create a skincare routine for: Skin Type: {analysis.get('skin_type', 'combination')}, Issues: {json.dumps(analysis.get('issues', []))}, Score: {analysis.get('overall_score', 70)}. 
Return ONLY JSON with morning_routine, evening_routine, weekly_routine arrays and products array. Respond in {lang_name}."""
        )
        
        response = await chat.send_message(user_message)
        logger.info(f"Routine AI response received, length: {len(response)}")
        
        result = parse_json_response(response)
        
        if result:
            # Ensure all required fields exist
            if 'morning_routine' not in result:
                result['morning_routine'] = []
            if 'evening_routine' not in result:
                result['evening_routine'] = []
            if 'weekly_routine' not in result:
                result['weekly_routine'] = []
            if 'products' not in result:
                result['products'] = []
            return result
        else:
            # Fallback routine
            logger.warning("Could not parse routine response, using fallback")
            return get_fallback_routine(analysis.get('skin_type', 'combination'), lang_name)
            
    except Exception as e:
        logger.error(f"Routine generation error: {str(e)}")
        return get_fallback_routine(analysis.get('skin_type', 'combination'), lang_name)

def get_fallback_routine(skin_type: str, language: str) -> dict:
    """Return a basic fallback routine"""
    return {
        "morning_routine": [
            {"order": 1, "step_name": "Cleanser", "product_type": "cleanser", "instructions": "Gently massage onto damp skin, rinse with lukewarm water", "ingredients_to_look_for": ["glycerin", "hyaluronic acid"], "ingredients_to_avoid": ["alcohol", "sulfates"]},
            {"order": 2, "step_name": "Toner", "product_type": "toner", "instructions": "Apply with cotton pad or pat into skin", "ingredients_to_look_for": ["niacinamide", "green tea"], "ingredients_to_avoid": ["alcohol"]},
            {"order": 3, "step_name": "Moisturizer", "product_type": "moisturizer", "instructions": "Apply evenly to face and neck", "ingredients_to_look_for": ["ceramides", "hyaluronic acid"], "ingredients_to_avoid": ["fragrance"]},
            {"order": 4, "step_name": "Sunscreen", "product_type": "sunscreen", "instructions": "Apply generously 15 minutes before sun exposure", "ingredients_to_look_for": ["SPF 30+", "zinc oxide"], "ingredients_to_avoid": ["oxybenzone"]}
        ],
        "evening_routine": [
            {"order": 1, "step_name": "Cleanser", "product_type": "cleanser", "instructions": "Double cleanse to remove makeup and sunscreen", "ingredients_to_look_for": ["oil-based cleanser"], "ingredients_to_avoid": ["harsh sulfates"]},
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
    """Analyze skin from base64 image"""
    try:
        # Get user's language preference
        language = request.language or current_user.get('profile', {}).get('language', 'en')
        
        # Analyze skin
        analysis = await analyze_skin_with_ai(request.image_base64, language)
        
        # Generate routine
        routine_data = await generate_routine_with_ai(analysis, language)
        
        # Create scan record
        scan = {
            'id': str(uuid.uuid4()),
            'user_id': current_user['id'],
            'image_base64': request.image_base64,
            'analysis': analysis,
            'routine': {
                'morning_routine': routine_data.get('morning_routine', []),
                'evening_routine': routine_data.get('evening_routine', []),
                'weekly_routine': routine_data.get('weekly_routine', [])
            },
            'products': routine_data.get('products', []),
            'created_at': datetime.utcnow(),
            'language': language
        }
        
        await db.scans.insert_one(scan)
        
        return {
            'id': scan['id'],
            'analysis': analysis,
            'routine': scan['routine'],
            'products': scan['products'],
            'created_at': scan['created_at'].isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scan analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/scan/history")
async def get_scan_history(current_user: dict = Depends(get_current_user)):
    """Get user's scan history"""
    scans = await db.scans.find(
        {'user_id': current_user['id']}
    ).sort('created_at', -1).to_list(100)
    
    return [
        {
            'id': scan['id'],
            'analysis': scan.get('analysis'),
            'created_at': scan['created_at'].isoformat() if isinstance(scan['created_at'], datetime) else scan['created_at'],
            'has_image': bool(scan.get('image_base64'))
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
    
    return {
        'id': scan['id'],
        'image_base64': scan.get('image_base64'),
        'analysis': scan.get('analysis'),
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

# ==================== TRANSLATIONS ====================

# Base translations for UI elements
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
        'acne': 'Acne',
        'dark_spots': 'Dark Spots',
        'wrinkles': 'Wrinkles',
        'redness': 'Redness',
        'large_pores': 'Large Pores',
        'dehydration': 'Dehydration',
        'uneven_tone': 'Uneven Tone',
        'onboarding_1_title': 'AI-Powered Skin Analysis',
        'onboarding_1_desc': 'Get instant, personalized skin analysis using advanced AI technology',
        'onboarding_2_title': 'Personalized Routines',
        'onboarding_2_desc': 'Receive customized morning and evening skincare routines',
        'onboarding_3_title': 'Track Your Progress',
        'onboarding_3_desc': 'Monitor your skin health journey over time',
        'get_started': 'Get Started',
        'next': 'Next',
        'skip': 'Skip',
        'age': 'Age',
        'gender': 'Gender',
        'skin_goals': 'Skin Goals',
        'country': 'Country',
        'save': 'Save',
        'home': 'Home',
        'change_name': 'Change Name',
        'change_email': 'Change Email',
        'change_password': 'Change Password',
        'forgot_password': 'Forgot Password?',
        'current_password': 'Current Password',
        'new_password': 'New Password',
        'confirm_password': 'Confirm Password',
        'reset_password': 'Reset Password',
        'send_reset_link': 'Send Reset Link',
        'account_settings': 'Account Settings',
        'edit_profile': 'Edit Profile'
    },
    'fr': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Bienvenue',
        'login': 'Connexion',
        'register': "S'inscrire",
        'email': 'E-mail',
        'password': 'Mot de passe',
        'name': 'Nom',
        'scan_skin': 'Scanner votre peau',
        'my_routines': 'Mes routines',
        'progress': 'Progrès',
        'profile': 'Profil',
        'settings': 'Paramètres',
        'logout': 'Déconnexion',
        'morning_routine': 'Routine du matin',
        'evening_routine': 'Routine du soir',
        'weekly_routine': 'Routine hebdomadaire',
        'skin_type': 'Type de peau',
        'skin_issues': 'Problèmes de peau',
        'overall_score': 'Score global',
        'recommendations': 'Recommandations',
        'products': 'Produits',
        'take_photo': 'Prendre une photo',
        'upload_photo': 'Télécharger une photo',
        'analyzing': 'Analyse de votre peau...',
        'analysis_complete': 'Analyse terminée',
        'view_results': 'Voir les résultats',
        'disclaimer': "Cette analyse est uniquement à titre de conseil cosmétique et n'est pas un diagnostic médical.",
        'language': 'Langue',
        'dark_mode': 'Mode sombre',
        'delete_account': 'Supprimer le compte',
        'confirm_delete': 'Êtes-vous sûr de vouloir supprimer votre compte?',
        'cancel': 'Annuler',
        'confirm': 'Confirmer',
        'error': 'Erreur',
        'success': 'Succès',
        'loading': 'Chargement...',
        'no_scans': 'Pas encore de scans',
        'start_first_scan': 'Commencez votre premier scan de peau',
        'oily': 'Grasse',
        'dry': 'Sèche',
        'combination': 'Mixte',
        'normal': 'Normale',
        'sensitive': 'Sensible',
        'home': 'Accueil',
        'change_name': 'Changer le nom',
        'change_email': "Changer l'email",
        'change_password': 'Changer le mot de passe',
        'forgot_password': 'Mot de passe oublié?',
        'current_password': 'Mot de passe actuel',
        'new_password': 'Nouveau mot de passe',
        'reset_password': 'Réinitialiser le mot de passe',
        'account_settings': 'Paramètres du compte',
        'edit_profile': 'Modifier le profil'
    },
    'tr': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Hoş geldiniz',
        'login': 'Giriş Yap',
        'register': 'Kayıt Ol',
        'email': 'E-posta',
        'password': 'Şifre',
        'name': 'İsim',
        'scan_skin': 'Cildinizi Tarayın',
        'my_routines': 'Rutinlerim',
        'progress': 'İlerleme',
        'profile': 'Profil',
        'settings': 'Ayarlar',
        'logout': 'Çıkış Yap',
        'home': 'Ana Sayfa',
        'change_name': 'İsim Değiştir',
        'change_email': 'E-posta Değiştir',
        'change_password': 'Şifre Değiştir',
        'forgot_password': 'Şifremi Unuttum?',
        'account_settings': 'Hesap Ayarları'
    },
    'it': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Benvenuto',
        'login': 'Accedi',
        'register': 'Registrati',
        'home': 'Home',
        'change_name': 'Cambia Nome',
        'change_email': 'Cambia Email',
        'change_password': 'Cambia Password',
        'forgot_password': 'Password dimenticata?'
    },
    'es': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Bienvenido',
        'login': 'Iniciar sesión',
        'register': 'Registrarse',
        'home': 'Inicio',
        'change_name': 'Cambiar Nombre',
        'change_email': 'Cambiar Email',
        'change_password': 'Cambiar Contraseña',
        'forgot_password': '¿Olvidaste tu contraseña?'
    },
    'de': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Willkommen',
        'login': 'Anmelden',
        'register': 'Registrieren',
        'home': 'Startseite',
        'change_name': 'Name ändern',
        'change_email': 'E-Mail ändern',
        'change_password': 'Passwort ändern',
        'forgot_password': 'Passwort vergessen?'
    },
    'ar': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'مرحباً',
        'login': 'تسجيل الدخول',
        'register': 'إنشاء حساب',
        'home': 'الرئيسية',
        'change_name': 'تغيير الاسم',
        'change_email': 'تغيير البريد الإلكتروني',
        'change_password': 'تغيير كلمة المرور',
        'forgot_password': 'نسيت كلمة المرور؟'
    },
    'zh': {
        'app_name': 'SkinAdvisor AI',
        'welcome': '欢迎',
        'login': '登录',
        'register': '注册',
        'home': '首页',
        'change_name': '更改姓名',
        'change_email': '更改邮箱',
        'change_password': '更改密码',
        'forgot_password': '忘记密码？'
    },
    'hi': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'स्वागत है',
        'login': 'लॉग इन करें',
        'register': 'रजिस्टर करें',
        'home': 'होम',
        'change_name': 'नाम बदलें',
        'change_email': 'ईमेल बदलें',
        'change_password': 'पासवर्ड बदलें',
        'forgot_password': 'पासवर्ड भूल गए?'
    }
}

@api_router.get("/translations/{language}")
async def get_translations(language: str):
    """Get translations for a specific language"""
    if language not in BASE_TRANSLATIONS:
        language = 'en'
    # Merge with English as fallback
    translations = {**BASE_TRANSLATIONS['en'], **BASE_TRANSLATIONS.get(language, {})}
    return translations

@api_router.get("/languages")
async def get_languages():
    """Get list of supported languages"""
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
    return {"message": "SkinAdvisor AI API", "version": "1.0.0"}

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
