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
from openai import OpenAI
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

# OpenAI API Key for production
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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
    age_range: Optional[str] = None  # New field for questionnaire
    gender: Optional[str] = None
    skin_goals: Optional[List[str]] = []
    skin_type: Optional[str] = None  # New field for questionnaire
    country: Optional[str] = None
    language: str = "en"

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    profile: Optional[UserProfile] = None
    plan: str = "free"
    scan_count: int = 0
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# ==================== SUBSCRIPTION MODELS ====================

class SubscriptionStatus(BaseModel):
    plan: str  # "free" or "premium"
    scan_count: int
    scan_limit: int  # 1 for free, unlimited (-1) for premium
    can_scan: bool
    features: Dict[str, bool]

class UpgradeRequest(BaseModel):
    plan: str = "premium"  # For now just premium

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
# STRICT SCORING: 85+ should be elite (top 10%), 90+ extremely rare (top 3-5%)

# Issue weights for score calculation - STRONGER PENALTIES
ISSUE_WEIGHTS = {
    'acne': 6,           # Strong penalty
    'pores': 4,          # Moderate penalty
    'large_pores': 4,
    'uneven_tone': 3,
    'uneven_skin_tone': 3,
    'redness': 4,
    'rosacea': 5,
    'dehydration': 5,
    'dryness': 3,
    'oiliness': 3,
    'dark_spots': 3,
    'hyperpigmentation': 3,
    'wrinkles': 4,
    'fine_lines': 2,
    'texture': 3,
    'blackheads': 3,
    'whiteheads': 3,
    'sun_damage': 4,
    'dark_circles': 2,
    'sensitivity': 3,
    'inflammation': 4,
}

# Score ranges with labels - Updated for YELLOW-focused psychology
SCORE_LABELS = {
    (0, 39): {'label': 'needs_care', 'description': 'Your skin requires focused care'},
    (40, 59): {'label': 'needs_attention', 'description': 'Your skin needs attention'},
    (60, 74): {'label': 'average', 'description': 'Average - room for improvement'},
    (75, 89): {'label': 'good', 'description': 'Good - but can be better'},
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
    Calculate skin health score using STRICT DETERMINISTIC formula.
    
    GOALS:
    - 90+ = top 3-5% (extremely rare)
    - 85-89 = top 10% (elite)
    - 70-84 = majority of users
    - <70 = common
    
    Score is calculated ONLY from detected issues and their severity.
    LLM does NOT control this score.
    """
    # LOWER base score: 75 (max 78 with bonuses)
    base_score = 75
    
    score_factors = []
    total_deduction = 0
    
    # Track critical issues for hard cap rule
    critical_issues = {
        'acne': 0,
        'pores': 0,
        'uneven_tone': 0,
        'redness': 0,
    }
    
    max_severity = 0  # Track highest severity for elite score check
    
    for issue in issues:
        issue_name = issue.get('name', '').lower().replace(' ', '_').replace('-', '_')
        severity = min(10, max(0, issue.get('severity', 0)))  # Clamp 0-10
        
        # Track max severity
        if severity > max_severity:
            max_severity = severity
        
        # Track critical issues
        for critical_key in critical_issues.keys():
            if critical_key in issue_name or issue_name in critical_key:
                critical_issues[critical_key] = max(critical_issues[critical_key], severity)
        
        # Find matching weight - use STRONGER penalties
        weight = 3  # Default weight (increased)
        for key, w in ISSUE_WEIGHTS.items():
            if key in issue_name or issue_name in key:
                weight = w
                break
        
        # Calculate deduction: severity * weight (NO normalization - direct impact)
        deduction = severity * weight * 0.15  # Each severity point = weight * 0.15 points
        total_deduction += deduction
        
        if severity > 0:
            severity_label = 'mild' if severity <= 3 else 'moderate' if severity <= 6 else 'severe'
            score_factors.append({
                'issue': issue.get('name', 'Unknown'),
                'severity': severity,
                'severity_label': severity_label,
                'deduction': round(deduction, 1)
            })
    
    # Calculate preliminary score
    preliminary_score = base_score - total_deduction
    
    # ==================== HARD CAP RULES ====================
    
    # Rule 1: If ANY critical issue has severity >= 3, cap at 84
    has_critical_issue = any(sev >= 3 for sev in critical_issues.values())
    if has_critical_issue:
        preliminary_score = min(preliminary_score, 84)
    
    # Rule 2: If ANY issue has severity >= 5, cap at 79
    if max_severity >= 5:
        preliminary_score = min(preliminary_score, 79)
    
    # Rule 3: If ANY issue has severity >= 7, cap at 74
    if max_severity >= 7:
        preliminary_score = min(preliminary_score, 74)
    
    # Rule 4: 90+ ONLY allowed if ALL conditions met:
    # - All severities <= 1
    # - Total deduction < 5
    can_be_elite = (max_severity <= 1) and (total_deduction < 5)
    if not can_be_elite and preliminary_score >= 85:
        preliminary_score = min(preliminary_score, 84)
    
    # Rule 5: 90+ requires exceptionally good skin
    if preliminary_score >= 90 and not (max_severity == 0 and total_deduction < 2):
        preliminary_score = min(preliminary_score, 89)
    
    # Final score clamping
    final_score = max(0, min(100, round(preliminary_score)))
    
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

# ==================== DIET & NUTRITION SYSTEM (DETERMINISTIC) ====================

# Foods database - categorized by benefit
FOODS_DATABASE = {
    'omega_3_rich': [
        {'name': 'Fatty fish (salmon, mackerel)', 'reason': 'Rich in omega-3 fatty acids that reduce inflammation'},
        {'name': 'Walnuts', 'reason': 'Plant-based omega-3 source for skin repair'},
        {'name': 'Chia seeds', 'reason': 'High in omega-3 and antioxidants'},
        {'name': 'Flaxseeds', 'reason': 'Contains alpha-linolenic acid for skin health'},
    ],
    'antioxidant_rich': [
        {'name': 'Berries (blueberries, strawberries)', 'reason': 'Packed with antioxidants that fight free radicals'},
        {'name': 'Dark leafy greens (spinach, kale)', 'reason': 'Rich in vitamins A, C, E for skin renewal'},
        {'name': 'Green tea', 'reason': 'Contains catechins that protect skin from damage'},
        {'name': 'Tomatoes', 'reason': 'Lycopene helps protect against sun damage'},
    ],
    'zinc_rich': [
        {'name': 'Pumpkin seeds', 'reason': 'High in zinc which helps heal blemishes'},
        {'name': 'Chickpeas', 'reason': 'Plant-based zinc source for skin repair'},
        {'name': 'Lean beef', 'reason': 'Excellent zinc source for cell regeneration'},
        {'name': 'Oysters', 'reason': 'Highest natural source of zinc'},
    ],
    'vitamin_c_rich': [
        {'name': 'Citrus fruits (oranges, lemons)', 'reason': 'Vitamin C boosts collagen production'},
        {'name': 'Bell peppers', 'reason': 'Very high in vitamin C for skin brightening'},
        {'name': 'Kiwi', 'reason': 'Packed with vitamin C and E for radiance'},
        {'name': 'Papaya', 'reason': 'Contains papain enzyme and vitamin C'},
    ],
    'vitamin_e_rich': [
        {'name': 'Almonds', 'reason': 'Rich in vitamin E that protects skin cells'},
        {'name': 'Sunflower seeds', 'reason': 'High in vitamin E and selenium'},
        {'name': 'Avocados', 'reason': 'Healthy fats and vitamin E for moisturized skin'},
    ],
    'hydrating_foods': [
        {'name': 'Cucumber', 'reason': '95% water content for hydration'},
        {'name': 'Watermelon', 'reason': 'Hydrating and contains lycopene'},
        {'name': 'Celery', 'reason': 'High water content and vitamins'},
        {'name': 'Coconut water', 'reason': 'Natural electrolytes for hydration'},
    ],
    'anti_inflammatory': [
        {'name': 'Turmeric', 'reason': 'Curcumin reduces inflammation and redness'},
        {'name': 'Ginger', 'reason': 'Anti-inflammatory compounds soothe skin'},
        {'name': 'Extra virgin olive oil', 'reason': 'Oleocanthal has anti-inflammatory effects'},
        {'name': 'Fatty fish', 'reason': 'Omega-3s calm inflammatory skin conditions'},
    ],
    'probiotic_rich': [
        {'name': 'Yogurt (unsweetened)', 'reason': 'Probiotics support gut-skin connection'},
        {'name': 'Kefir', 'reason': 'Fermented dairy improves skin clarity'},
        {'name': 'Sauerkraut', 'reason': 'Fermented foods balance skin microbiome'},
        {'name': 'Kimchi', 'reason': 'Probiotics and vitamins for clear skin'},
    ],
    'whole_grains': [
        {'name': 'Brown rice', 'reason': 'Low glycemic, reduces sebum production'},
        {'name': 'Quinoa', 'reason': 'Complete protein with B vitamins'},
        {'name': 'Oats', 'reason': 'Beta-glucan soothes skin from within'},
    ],
}

FOODS_TO_AVOID = {
    'high_sugar': [
        {'name': 'Sugary drinks (sodas, sweetened juices)', 'reason': 'Spikes blood sugar, triggers breakouts'},
        {'name': 'Candy and sweets', 'reason': 'High glycemic foods worsen acne'},
        {'name': 'Pastries and cakes', 'reason': 'Refined sugar increases inflammation'},
    ],
    'processed_foods': [
        {'name': 'Fast food', 'reason': 'High in unhealthy fats and sodium'},
        {'name': 'Processed snacks (chips, crackers)', 'reason': 'Often contain inflammatory oils'},
        {'name': 'Ultra-processed foods', 'reason': 'Additives can trigger skin reactions'},
    ],
    'dairy_limit': [
        {'name': 'Milk (especially skim)', 'reason': 'May increase sebum production and breakouts'},
        {'name': 'Ice cream', 'reason': 'Dairy and sugar combination can worsen acne'},
    ],
    'fried_foods': [
        {'name': 'Fried foods', 'reason': 'Excess oil can clog pores and cause inflammation'},
        {'name': 'Deep-fried snacks', 'reason': 'Trans fats damage skin cell membranes'},
    ],
    'refined_carbs': [
        {'name': 'White bread', 'reason': 'High glycemic index increases oil production'},
        {'name': 'White pasta', 'reason': 'Spikes insulin which can trigger breakouts'},
        {'name': 'White rice (excess)', 'reason': 'Refined carbs promote inflammation'},
    ],
    'alcohol': [
        {'name': 'Alcohol', 'reason': 'Dehydrates skin and dilates blood vessels'},
        {'name': 'Cocktails with sugar', 'reason': 'Alcohol plus sugar accelerates aging'},
    ],
    'caffeine_excess': [
        {'name': 'Excess coffee (>3 cups)', 'reason': 'Can dehydrate skin if overconsumed'},
        {'name': 'Energy drinks', 'reason': 'High caffeine and sugar damage skin'},
    ],
    'spicy_foods': [
        {'name': 'Very spicy dishes', 'reason': 'Can trigger flushing and worsen redness'},
        {'name': 'Hot peppers (excess)', 'reason': 'May aggravate rosacea and sensitive skin'},
    ],
}

SUPPLEMENTS_DATABASE = {
    'omega_3': {'name': 'Omega-3 Fish Oil', 'reason': 'Supports skin barrier and reduces inflammation'},
    'vitamin_d': {'name': 'Vitamin D', 'reason': 'Supports skin cell growth and repair'},
    'zinc': {'name': 'Zinc', 'reason': 'Helps heal blemishes and control oil production'},
    'vitamin_c': {'name': 'Vitamin C', 'reason': 'Antioxidant that supports collagen production'},
    'vitamin_e': {'name': 'Vitamin E', 'reason': 'Protects skin cells from oxidative damage'},
    'probiotics': {'name': 'Probiotics', 'reason': 'Supports gut-skin axis for clearer complexion'},
    'biotin': {'name': 'Biotin', 'reason': 'Supports healthy skin, hair, and nails'},
    'collagen': {'name': 'Collagen peptides', 'reason': 'May improve skin elasticity and hydration'},
    'evening_primrose': {'name': 'Evening Primrose Oil', 'reason': 'GLA fatty acid for dry, sensitive skin'},
}

HYDRATION_TIPS = {
    'general': "Aim for 8 glasses (2 liters) of water daily. Increase intake if exercising or in hot weather.",
    'dry_skin': "Drink at least 10 glasses of water daily and include hydrating foods like cucumber and watermelon.",
    'oily_skin': "Stay well hydrated - 8 glasses daily. Proper hydration can actually help regulate oil production.",
    'acne': "Drink plenty of water to flush toxins. Add lemon for vitamin C boost. Avoid sugary drinks.",
    'dehydrated': "Increase water intake to 10-12 glasses daily. Consider electrolyte-rich coconut water.",
    'sensitive': "Room temperature water is gentler. Herbal teas like chamomile can also soothe from within.",
}

def generate_diet_recommendations(skin_type: str, issues: List[dict]) -> dict:
    """
    Generate DETERMINISTIC diet recommendations based on skin type and issues.
    Same skin type + same issues = same recommendations (no randomness).
    """
    eat_more = []
    avoid = []
    supplements = []
    
    # Create a set of detected issue names (normalized)
    issue_names = set()
    issue_severities = {}
    for issue in issues:
        name = issue.get('name', '').lower()
        severity = issue.get('severity', 0)
        issue_names.add(name)
        issue_severities[name] = severity
    
    # Helper to check if any issue matches keywords
    def has_issue(keywords):
        for keyword in keywords:
            for issue_name in issue_names:
                if keyword in issue_name:
                    return True, issue_severities.get(issue_name, 0)
        return False, 0
    
    # ========== ACNE-RELATED ==========
    has_acne, acne_severity = has_issue(['acne', 'pimple', 'breakout', 'blemish', 'blackhead', 'whitehead'])
    if has_acne and acne_severity > 3:
        eat_more.extend(FOODS_DATABASE['omega_3_rich'][:2])
        eat_more.extend(FOODS_DATABASE['zinc_rich'][:2])
        eat_more.extend(FOODS_DATABASE['antioxidant_rich'][:2])
        avoid.extend(FOODS_TO_AVOID['high_sugar'][:2])
        avoid.extend(FOODS_TO_AVOID['dairy_limit'])
        avoid.extend(FOODS_TO_AVOID['fried_foods'][:1])
        supplements.append(SUPPLEMENTS_DATABASE['zinc'])
        supplements.append(SUPPLEMENTS_DATABASE['omega_3'])
    elif has_acne:
        eat_more.extend(FOODS_DATABASE['zinc_rich'][:1])
        eat_more.extend(FOODS_DATABASE['antioxidant_rich'][:1])
        avoid.extend(FOODS_TO_AVOID['high_sugar'][:1])
    
    # ========== OILY SKIN ==========
    if skin_type == 'oily':
        eat_more.extend(FOODS_DATABASE['whole_grains'][:2])
        eat_more.extend(FOODS_DATABASE['antioxidant_rich'][2:3])  # Green tea
        avoid.extend(FOODS_TO_AVOID['refined_carbs'][:2])
        avoid.extend(FOODS_TO_AVOID['fried_foods'][:1])
    
    # ========== DRY SKIN ==========
    if skin_type == 'dry':
        eat_more.extend(FOODS_DATABASE['vitamin_e_rich'])
        eat_more.extend(FOODS_DATABASE['omega_3_rich'][:2])
        eat_more.extend(FOODS_DATABASE['hydrating_foods'][:2])
        avoid.extend(FOODS_TO_AVOID['alcohol'])
        avoid.extend(FOODS_TO_AVOID['caffeine_excess'][:1])
        supplements.append(SUPPLEMENTS_DATABASE['omega_3'])
        supplements.append(SUPPLEMENTS_DATABASE['evening_primrose'])
    
    # ========== DEHYDRATION ==========
    has_dehydration, dehydration_severity = has_issue(['dehydration', 'dehydrated', 'dry'])
    if has_dehydration and dehydration_severity > 3:
        eat_more.extend(FOODS_DATABASE['hydrating_foods'])
        eat_more.extend(FOODS_DATABASE['omega_3_rich'][:1])
        avoid.extend(FOODS_TO_AVOID['caffeine_excess'])
        avoid.extend(FOODS_TO_AVOID['alcohol'][:1])
    
    # ========== REDNESS/INFLAMMATION ==========
    has_redness, redness_severity = has_issue(['redness', 'inflammation', 'rosacea', 'irritation', 'sensitive'])
    if has_redness and redness_severity > 3:
        eat_more.extend(FOODS_DATABASE['anti_inflammatory'])
        eat_more.extend(FOODS_DATABASE['omega_3_rich'][:1])
        avoid.extend(FOODS_TO_AVOID['spicy_foods'])
        avoid.extend(FOODS_TO_AVOID['alcohol'])
        avoid.extend(FOODS_TO_AVOID['processed_foods'][:1])
        supplements.append(SUPPLEMENTS_DATABASE['omega_3'])
    elif has_redness:
        eat_more.extend(FOODS_DATABASE['anti_inflammatory'][:2])
        avoid.extend(FOODS_TO_AVOID['spicy_foods'][:1])
    
    # ========== UNEVEN TONE / DULL SKIN ==========
    has_uneven, uneven_severity = has_issue(['uneven', 'dull', 'dark spot', 'hyperpigmentation', 'pigment'])
    if has_uneven:
        eat_more.extend(FOODS_DATABASE['vitamin_c_rich'][:3])
        eat_more.extend(FOODS_DATABASE['vitamin_e_rich'][:2])
        avoid.extend(FOODS_TO_AVOID['processed_foods'][:2])
        supplements.append(SUPPLEMENTS_DATABASE['vitamin_c'])
        supplements.append(SUPPLEMENTS_DATABASE['vitamin_e'])
    
    # ========== WRINKLES / AGING ==========
    has_aging, aging_severity = has_issue(['wrinkle', 'fine line', 'aging', 'sagging'])
    if has_aging and aging_severity > 3:
        eat_more.extend(FOODS_DATABASE['antioxidant_rich'][:3])
        eat_more.extend(FOODS_DATABASE['vitamin_c_rich'][:2])
        eat_more.extend(FOODS_DATABASE['omega_3_rich'][:1])
        avoid.extend(FOODS_TO_AVOID['high_sugar'][:2])
        avoid.extend(FOODS_TO_AVOID['alcohol'][:1])
        supplements.append(SUPPLEMENTS_DATABASE['collagen'])
        supplements.append(SUPPLEMENTS_DATABASE['vitamin_c'])
    
    # ========== SENSITIVE SKIN ==========
    if skin_type == 'sensitive':
        eat_more.extend(FOODS_DATABASE['anti_inflammatory'][:2])
        eat_more.extend(FOODS_DATABASE['probiotic_rich'][:2])
        avoid.extend(FOODS_TO_AVOID['spicy_foods'])
        avoid.extend(FOODS_TO_AVOID['alcohol'][:1])
        supplements.append(SUPPLEMENTS_DATABASE['probiotics'])
    
    # ========== LARGE PORES ==========
    has_pores, pores_severity = has_issue(['pore', 'large pore'])
    if has_pores and pores_severity > 4:
        eat_more.extend(FOODS_DATABASE['antioxidant_rich'][:2])
        eat_more.extend(FOODS_DATABASE['vitamin_c_rich'][:1])
        avoid.extend(FOODS_TO_AVOID['fried_foods'])
        avoid.extend(FOODS_TO_AVOID['refined_carbs'][:1])
    
    # ========== GENERAL SKIN HEALTH (if few issues) ==========
    if len(eat_more) < 3:
        eat_more.extend(FOODS_DATABASE['antioxidant_rich'][:2])
        eat_more.extend(FOODS_DATABASE['hydrating_foods'][:1])
    
    if len(avoid) < 2:
        avoid.extend(FOODS_TO_AVOID['processed_foods'][:1])
        avoid.extend(FOODS_TO_AVOID['high_sugar'][:1])
    
    if len(supplements) < 2:
        supplements.append(SUPPLEMENTS_DATABASE['vitamin_d'])
        supplements.append(SUPPLEMENTS_DATABASE['omega_3'])
    
    # Remove duplicates while preserving order
    def dedupe(items):
        seen = set()
        result = []
        for item in items:
            key = item['name']
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result
    
    eat_more = dedupe(eat_more)[:8]  # Max 8 items
    avoid = dedupe(avoid)[:6]  # Max 6 items
    supplements = dedupe(supplements)[:4]  # Max 4 items
    
    # Determine hydration tip based on conditions
    hydration_tip = HYDRATION_TIPS['general']
    if skin_type == 'dry' or has_dehydration[0] if isinstance(has_dehydration, tuple) else has_dehydration:
        hydration_tip = HYDRATION_TIPS['dry_skin']
    elif skin_type == 'oily':
        hydration_tip = HYDRATION_TIPS['oily_skin']
    elif has_acne:
        hydration_tip = HYDRATION_TIPS['acne']
    elif skin_type == 'sensitive' or has_redness:
        hydration_tip = HYDRATION_TIPS['sensitive']
    
    return {
        'eat_more': eat_more,
        'avoid': avoid,
        'hydration_tip': hydration_tip,
        'supplements_optional': supplements
    }

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
        'plan': 'free',  # NEW: Default plan is free
        'scan_count': 0,  # NEW: Track number of scans
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
            plan=user['plan'],
            scan_count=user['scan_count'],
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
            plan=user.get('plan', 'free'),
            scan_count=user.get('scan_count', 0),
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
        plan=current_user.get('plan', 'free'),
        scan_count=current_user.get('scan_count', 0),
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

# Minimum optimization issues that should ALWAYS be suggested
# (because no face is truly perfect)
UNIVERSAL_OPTIMIZATION_ISSUES = [
    {'name': 'Hydration optimization', 'severity': 2, 'confidence': 0.9, 'description': 'Skin hydration can always be improved for better elasticity and glow'},
    {'name': 'Pore refinement', 'severity': 2, 'confidence': 0.85, 'description': 'Pore appearance can be minimized with proper care'},
    {'name': 'Skin barrier health', 'severity': 1, 'confidence': 0.9, 'description': 'Maintaining skin barrier integrity prevents future issues'},
    {'name': 'Anti-aging prevention', 'severity': 1, 'confidence': 0.95, 'description': 'Preventive care helps maintain youthful skin longer'},
    {'name': 'Tone uniformity', 'severity': 2, 'confidence': 0.8, 'description': 'Minor tone variations can be improved with consistent care'},
]

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
    if not OPENAI_API_KEY:
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
        if not openai_client:
            logger.warning("OpenAI client not initialized, using fallback")
            return get_fallback_analysis(language)
        
        user_prompt = f"""Analyze this facial skin image systematically:

1. SKIN TYPE: Classify based on visible characteristics
2. ISSUES: Detect and rate each visible issue (severity 0-10, confidence 0-1)
3. RECOMMENDATIONS: Provide 3-5 specific skincare recommendations

Check for: acne, dark spots, wrinkles, fine lines, redness, large pores, dehydration, oiliness, uneven tone, blackheads, texture issues, sun damage, dark circles.

Return ONLY JSON. Respond in {lang_name}."""

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
        )
        
        response_text = response.choices[0].message.content
        logger.info(f"AI response length: {len(response_text)}")
        
        result = parse_json_response(response_text)
        
        if result:
            # Validate and normalize the response
            validated = validate_ai_response(result, language)
            return validated
        else:
            logger.warning(f"Could not parse AI response: {response_text[:300]}")
            return get_fallback_analysis(language)
            
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        return get_fallback_analysis(language)

def validate_ai_response(result: dict, language: str) -> dict:
    """
    Validate and normalize AI response to ensure consistency.
    
    CRITICAL RULES:
    1. ALWAYS return at least 1-3 optimization issues (no face is perfect)
    2. Ensure skin_type is valid
    3. Normalize all values to expected ranges
    """
    
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
    
    # Validate issues from AI
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
    
    # ==================== CRITICAL: ENSURE MINIMUM ISSUES ====================
    # No face is perfect - ALWAYS return at least 1-3 optimization issues
    # This prevents the "score > 70 but 0 issues" bug
    
    if len(validated_issues) < 3:
        # Get issue names already present
        existing_names = {i['name'].lower() for i in validated_issues}
        
        # Add universal optimization issues that aren't already detected
        for opt_issue in UNIVERSAL_OPTIMIZATION_ISSUES:
            if opt_issue['name'].lower() not in existing_names:
                validated_issues.append({
                    'name': opt_issue['name'],
                    'severity': opt_issue['severity'],
                    'confidence': opt_issue['confidence'],
                    'description': opt_issue['description']
                })
                if len(validated_issues) >= 3:
                    break
    
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
    """
    Return a safe fallback analysis when AI fails.
    ALWAYS includes minimum optimization issues (no face is perfect).
    """
    return {
        'skin_type': 'combination',
        'skin_type_confidence': 0.6,
        'skin_type_description': 'Analysis completed. Your skin shows typical characteristics that can be improved with proper care.',
        'issues': [
            {'name': 'Hydration optimization', 'severity': 2, 'confidence': 0.9, 'description': 'Skin hydration can always be improved for better elasticity and glow'},
            {'name': 'Pore refinement', 'severity': 2, 'confidence': 0.85, 'description': 'Pore appearance can be minimized with proper care'},
            {'name': 'Skin barrier health', 'severity': 1, 'confidence': 0.9, 'description': 'Maintaining skin barrier integrity prevents future issues'},
        ],
        'recommendations': [
            'Use a gentle cleanser twice daily',
            'Apply moisturizer appropriate for your skin type',
            'Use sunscreen daily (SPF 30+)',
            'Stay hydrated - drink 2L water daily',
            'Consider adding a vitamin C serum for brightness'
        ]
    }

async def generate_routine_with_ai(analysis: dict, language: str = 'en') -> dict:
    """Generate skincare routine based on analysis with DETERMINISTIC settings"""
    if not OPENAI_API_KEY:
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
        if not openai_client:
            logger.warning("OpenAI client not initialized, using fallback")
            return get_fallback_routine(skin_type)
        
        user_prompt = f"""Create skincare routine for:
- Skin type: {skin_type}
- Issues: {issues_text}

Provide morning (4-5 steps), evening (4-5 steps), weekly (1-2 treatments), and 5-7 product recommendations.
Return ONLY JSON in {lang_name}."""

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        response_text = response.choices[0].message.content
        result = parse_json_response(response_text)
        
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

# Constants for subscription limits
FREE_SCAN_LIMIT = 1  # Free users get 1 scan total (lifetime)

@api_router.post("/scan/analyze")
async def analyze_skin(
    request: SkinAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze skin from base64 image using DETERMINISTIC AI analysis.
    Score is calculated using a FIXED FORMULA, not by the LLM.
    
    FREE USERS: Get limited response (score, skin_type, main_issues, preview counts)
    PREMIUM USERS: Get full response (routine, diet, products, explanations)
    """
    try:
        user_plan = current_user.get('plan', 'free')
        scan_count = current_user.get('scan_count', 0)
        
        # ==================== SCAN LIMIT CHECK (SERVER-SIDE ENFORCEMENT) ====================
        if user_plan == 'free' and scan_count >= FREE_SCAN_LIMIT:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "scan_limit_reached",
                    "message": "You've used your free scan. Upgrade to Premium to continue.",
                    "scan_count": scan_count,
                    "scan_limit": FREE_SCAN_LIMIT,
                    "upgrade_required": True
                }
            )
        
        language = request.language or current_user.get('profile', {}).get('language', 'en')
        
        # Compute image hash for tracking/caching
        image_hash = compute_image_hash(request.image_base64)
        
        # Check for cached result (same image = same result)
        cached = await db.scan_cache.find_one({'image_hash': image_hash, 'language': language})
        if cached:
            logger.info(f"Using cached analysis for image hash: {image_hash}")
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
        
        # Generate DETERMINISTIC diet recommendations
        diet_recommendations = generate_diet_recommendations(
            skin_type=analysis.get('skin_type', 'normal'),
            issues=analysis.get('issues', [])
        )
        
        # Create scan record with all data (always store full data)
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
            'diet_recommendations': diet_recommendations,
            'created_at': datetime.utcnow(),
            'language': language
        }
        
        await db.scans.insert_one(scan)
        
        # ==================== INCREMENT SCAN COUNT ====================
        new_scan_count = scan_count + 1
        await db.users.update_one(
            {'id': current_user['id']},
            {'$set': {'scan_count': new_scan_count}}
        )
        
        # ==================== RETURN RESPONSE BASED ON PLAN ====================
        if user_plan == 'premium':
            # PREMIUM USER: Return full response
            return {
                'id': scan['id'],
                'user_plan': 'premium',
                'locked': False,
                'analysis': {
                    'skin_type': scan['analysis']['skin_type'],
                    'skin_type_confidence': scan['analysis']['skin_type_confidence'],
                    'skin_type_description': scan['analysis']['skin_type_description'],
                    'issues': scan['analysis']['issues'],
                    'recommendations': scan['analysis']['recommendations'],
                    'overall_score': score_data['score'],
                    'score_label': score_data['label'],
                    'score_description': score_data['description'],
                    'score_factors': score_data['factors']
                },
                'routine': scan['routine'],
                'products': scan['products'],
                'diet_recommendations': diet_recommendations,
                'progress_tracking_enabled': True,
                'created_at': scan['created_at'].isoformat(),
                'image_hash': image_hash
            }
        else:
            # FREE USER: Return issues visible but LOCKED (details hidden)
            # User MUST see issues exist - builds trust and conversion
            all_issues = scan['analysis']['issues']
            issue_count = len(all_issues)
            
            # Return issue names ONLY (no severity, no description - those are locked)
            issues_preview = [
                {
                    'name': issue.get('name', 'Skin concern detected'),
                    'locked': True,  # Severity and description are locked
                    'severity_locked': True,
                    'description_locked': True
                }
                for issue in all_issues
            ]
            
            return {
                'id': scan['id'],
                'user_plan': 'free',
                'locked': True,
                'analysis': {
                    'skin_type': scan['analysis']['skin_type'],
                    'overall_score': score_data['score'],
                    'score_label': score_data['label'],
                    # FREE USERS SEE: Issue names and count (but details locked)
                    'issue_count': issue_count,
                    'issues_preview': issues_preview,  # Names visible, details locked
                },
                'locked_features': [
                    'issue_details',       # Severity, description locked
                    'full_routine',
                    'diet_plan', 
                    'product_recommendations',
                    'progress_tracking',
                    'detailed_explanations'
                ],
                'preview': {
                    'issue_count': issue_count,
                    'routine_steps_count': len(routine.get('morning_routine', [])) + len(routine.get('evening_routine', [])) + len(routine.get('weekly_routine', [])),
                    'diet_items_count': len(diet_recommendations.get('eat_more', [])) + len(diet_recommendations.get('avoid', [])),
                    'products_count': len(products)
                },
                'created_at': scan['created_at'].isoformat(),
                'image_hash': image_hash,
                'upgrade_message': "You discovered what's affecting your skin. Unlock full analysis to see severity and solutions."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scan analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/scan/history")
async def get_scan_history(current_user: dict = Depends(get_current_user)):
    """Get user's scan history with score data and images for progress tracking"""
    scans = await db.scans.find(
        {'user_id': current_user['id']}
    ).sort('created_at', -1).to_list(100)
    
    result = []
    for scan in scans:
        analysis = scan.get('analysis', {})
        score_data = scan.get('score_data', {})
        
        # Ensure overall_score is always present in analysis
        overall_score = analysis.get('overall_score') or score_data.get('score', 65)
        
        # Merge overall_score into analysis for frontend consistency
        analysis_with_score = {
            **analysis,
            'overall_score': overall_score
        }
        
        result.append({
            'id': scan['id'],
            'analysis': analysis_with_score,
            'score_data': score_data,
            'created_at': scan['created_at'].isoformat() if isinstance(scan['created_at'], datetime) else scan['created_at'],
            'image_base64': scan.get('image_base64'),
            'image_hash': scan.get('image_hash')
        })
    
    return result

@api_router.get("/scan/{scan_id}")
async def get_scan_detail(scan_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed scan result - respects paywall for free users"""
    scan = await db.scans.find_one({
        'id': scan_id,
        'user_id': current_user['id']
    })
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    user_plan = current_user.get('plan', 'free')
    analysis = scan.get('analysis', {})
    score_data = scan.get('score_data', {})
    
    # Generate diet recommendations if not stored (for older scans)
    diet_recommendations = scan.get('diet_recommendations')
    if not diet_recommendations:
        diet_recommendations = generate_diet_recommendations(
            skin_type=analysis.get('skin_type', 'normal'),
            issues=analysis.get('issues', [])
        )
    
    # ==================== RETURN RESPONSE BASED ON PLAN ====================
    if user_plan == 'premium':
        # PREMIUM USER: Return full response
        return {
            'id': scan['id'],
            'user_plan': 'premium',
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
            'diet_recommendations': diet_recommendations,
            'progress_tracking_enabled': True,
            'created_at': scan['created_at'].isoformat() if isinstance(scan['created_at'], datetime) else scan['created_at']
        }
    else:
        # FREE USER: Return issues visible but LOCKED (details hidden)
        # User MUST see issues exist - builds trust and conversion
        all_issues = analysis.get('issues', [])
        issue_count = len(all_issues)
        
        # Return issue names ONLY (no severity, no description - those are locked)
        issues_preview = [
            {
                'name': issue.get('name', 'Skin concern detected'),
                'locked': True,
                'severity_locked': True,
                'description_locked': True
            }
            for issue in all_issues
        ]
        
        routine = scan.get('routine', {})
        products = scan.get('products', [])
        
        return {
            'id': scan['id'],
            'user_plan': 'free',
            'locked': True,
            'image_base64': scan.get('image_base64'),
            'image_hash': scan.get('image_hash'),
            'analysis': {
                'skin_type': analysis.get('skin_type'),
                'overall_score': score_data.get('score', 75),
                'score_label': score_data.get('label', 'good'),
                # FREE USERS SEE: Issue names and count (but details locked)
                'issue_count': issue_count,
                'issues_preview': issues_preview,
            },
            'locked_features': [
                'issue_details',
                'full_routine',
                'diet_plan',
                'product_recommendations',
                'progress_tracking',
                'detailed_explanations'
            ],
            'preview': {
                'issue_count': issue_count,
                'routine_steps_count': len(routine.get('morning_routine', [])) + len(routine.get('evening_routine', [])) + len(routine.get('weekly_routine', [])),
                'diet_items_count': len(diet_recommendations.get('eat_more', [])) + len(diet_recommendations.get('avoid', [])),
                'products_count': len(products)
            },
            'created_at': scan['created_at'].isoformat() if isinstance(scan['created_at'], datetime) else scan['created_at'],
            'upgrade_message': "Unlock full skin analysis, routine & diet plan"
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

# ==================== SUBSCRIPTION ENDPOINTS ====================

@api_router.get("/subscription/status")
async def get_subscription_status(current_user: dict = Depends(get_current_user)):
    """Get user's subscription status and limits"""
    user_plan = current_user.get('plan', 'free')
    scan_count = current_user.get('scan_count', 0)
    
    if user_plan == 'premium':
        return SubscriptionStatus(
            plan='premium',
            scan_count=scan_count,
            scan_limit=-1,  # Unlimited
            can_scan=True,
            features={
                'unlimited_scans': True,
                'full_routine': True,
                'diet_plan': True,
                'product_recommendations': True,
                'progress_tracking': True,
                'detailed_explanations': True
            }
        )
    else:
        return SubscriptionStatus(
            plan='free',
            scan_count=scan_count,
            scan_limit=FREE_SCAN_LIMIT,
            can_scan=scan_count < FREE_SCAN_LIMIT,
            features={
                'unlimited_scans': False,
                'full_routine': False,
                'diet_plan': False,
                'product_recommendations': False,
                'progress_tracking': False,
                'detailed_explanations': False
            }
        )

@api_router.post("/subscription/upgrade")
async def upgrade_subscription(request: UpgradeRequest, current_user: dict = Depends(get_current_user)):
    """
    Upgrade user to premium (MOCK - for testing)
    In production, this would integrate with Apple/Google IAP or Stripe
    """
    if request.plan != 'premium':
        raise HTTPException(status_code=400, detail="Invalid plan. Only 'premium' is supported.")
    
    # Update user's plan in database
    await db.users.update_one(
        {'id': current_user['id']},
        {'$set': {'plan': 'premium'}}
    )
    
    logger.info(f"User {current_user['id']} upgraded to premium (MOCK)")
    
    return {
        "success": True,
        "message": "Successfully upgraded to Premium!",
        "plan": "premium",
        "features_unlocked": [
            "Unlimited skin scans",
            "Full personalized routine",
            "Diet & nutrition plan",
            "Product recommendations",
            "Progress tracking",
            "Detailed explanations"
        ]
    }

@api_router.get("/subscription/pricing")
async def get_pricing():
    """Get subscription pricing info"""
    return {
        "monthly": {
            "price": 9.99,
            "currency": "EUR",
            "display": "€9.99/month",
            "period": "month"
        },
        "yearly": {
            "price": 59.99,
            "currency": "EUR",
            "display": "€59.99/year",
            "period": "year",
            "savings": "50%",
            "monthly_equivalent": 5.00
        },
        "features": [
            "Full daily skincare routine",
            "Personalized diet & foods to avoid",
            "Unlimited skin scans",
            "Progress tracking & before/after",
            "Product recommendations",
            "Detailed explanations"
        ]
    }

# ==================== ROUTINE PROGRESS ENDPOINTS ====================

class RoutineProgressUpdate(BaseModel):
    completed_tasks: List[str]
    streak: int
    daily_completion_rate: float

@api_router.get("/routine/progress")
async def get_routine_progress(current_user: dict = Depends(get_current_user)):
    """Get user's routine progress and streak bonus info"""
    progress = await db.routine_progress.find_one({'user_id': current_user['id']})
    
    if not progress:
        return {
            'streak': 0,
            'total_days_completed': 0,
            'bonus_points': 0,
            'last_completed_date': None,
            'weekly_completion_rate': 0.0
        }
    
    # Calculate bonus points: +3 for every 7-day streak
    streak = progress.get('streak', 0)
    bonus_points = (streak // 7) * 3
    
    return {
        'streak': streak,
        'total_days_completed': progress.get('total_days_completed', 0),
        'bonus_points': bonus_points,
        'last_completed_date': progress.get('last_completed_date'),
        'weekly_completion_rate': progress.get('weekly_completion_rate', 0.0)
    }

@api_router.post("/routine/complete-day")
async def complete_routine_day(current_user: dict = Depends(get_current_user)):
    """Mark today's routine as completed and update streak"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    progress = await db.routine_progress.find_one({'user_id': current_user['id']})
    
    if progress:
        last_date = progress.get('last_completed_date')
        current_streak = progress.get('streak', 0)
        total_days = progress.get('total_days_completed', 0)
        
        if last_date:
            if isinstance(last_date, str):
                last_date = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
            
            days_diff = (today - last_date.replace(tzinfo=None)).days
            
            if days_diff == 0:
                # Already completed today
                return {
                    'streak': current_streak,
                    'bonus_earned': 0,
                    'message': 'Already completed today!'
                }
            elif days_diff == 1:
                # Consecutive day - increase streak
                new_streak = current_streak + 1
            else:
                # Streak broken - start over
                new_streak = 1
        else:
            new_streak = 1
        
        total_days += 1
    else:
        new_streak = 1
        total_days = 1
    
    # Calculate bonus earned
    old_bonus = ((progress.get('streak', 0) if progress else 0) // 7) * 3
    new_bonus = (new_streak // 7) * 3
    bonus_earned = new_bonus - old_bonus
    
    # Update progress
    await db.routine_progress.update_one(
        {'user_id': current_user['id']},
        {
            '$set': {
                'user_id': current_user['id'],
                'streak': new_streak,
                'total_days_completed': total_days,
                'last_completed_date': today.isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
        },
        upsert=True
    )
    
    # If bonus earned, notify
    message = f'{new_streak} day streak!'
    if bonus_earned > 0:
        message = f'🎉 {new_streak} day streak! +{bonus_earned} bonus points earned!'
    
    return {
        'streak': new_streak,
        'total_days_completed': total_days,
        'bonus_earned': bonus_earned,
        'total_bonus': new_bonus,
        'message': message
    }

@api_router.post("/routine/reset-streak")
async def reset_streak(current_user: dict = Depends(get_current_user)):
    """Reset user's streak (for testing or manual reset)"""
    await db.routine_progress.update_one(
        {'user_id': current_user['id']},
        {'$set': {'streak': 0, 'last_completed_date': None}},
        upsert=True
    )
    return {'success': True, 'message': 'Streak reset'}

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
        'confidence': 'confidence',
        'quick_actions': 'Quick Actions',
        'latest_analysis': 'Latest Analysis',
        'issues_detected': 'issues detected',
        'score': 'Score',
        'onboarding_1_title': 'Scan Your Skin',
        'onboarding_1_desc': 'Take a photo of your face and get instant AI-powered skin analysis',
        'onboarding_2_title': 'Track Progress',
        'onboarding_2_desc': 'Monitor your skin health over time with detailed reports',
        'onboarding_3_title': 'Get Recommendations',
        'onboarding_3_desc': 'Receive personalized skincare routines and product suggestions',
        'next': 'Next',
        'get_started': 'Get Started',
        'skip': 'Skip'
    },
    'fr': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Bienvenue',
        'login': 'Connexion',
        'register': "S'inscrire",
        'email': 'Email',
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
        'analyzing': 'Analyse en cours...',
        'analysis_complete': 'Analyse terminée',
        'view_results': 'Voir les résultats',
        'disclaimer': 'Cette analyse est uniquement à des fins cosmétiques et ne constitue pas un diagnostic médical.',
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
        'start_first_scan': 'Commencez votre premier scan',
        'oily': 'Grasse',
        'dry': 'Sèche',
        'combination': 'Mixte',
        'normal': 'Normale',
        'sensitive': 'Sensible',
        'home': 'Accueil',
        'score_poor': 'Mauvais état de la peau',
        'score_below_average': 'En dessous de la moyenne',
        'score_average': 'Moyenne',
        'score_good': 'Bon état de la peau',
        'score_excellent': 'Excellent',
        'quick_actions': 'Actions rapides',
        'latest_analysis': 'Dernière analyse',
        'issues_detected': 'problèmes détectés',
        'score': 'Score',
        'onboarding_1_title': 'Analysez votre peau',
        'onboarding_1_desc': 'Prenez une photo de votre visage et obtenez une analyse instantanée par IA',
        'onboarding_2_title': 'Suivez vos progrès',
        'onboarding_2_desc': 'Surveillez la santé de votre peau au fil du temps',
        'onboarding_3_title': 'Recevez des recommandations',
        'onboarding_3_desc': 'Obtenez des routines de soins personnalisées',
        'next': 'Suivant',
        'get_started': 'Commencer',
        'skip': 'Passer'
    },
    'tr': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Hoş geldiniz',
        'login': 'Giriş',
        'register': 'Kayıt ol',
        'email': 'E-posta',
        'password': 'Şifre',
        'name': 'Ad',
        'scan_skin': 'Cildinizi Tarayın',
        'my_routines': 'Rutinlerim',
        'progress': 'İlerleme',
        'profile': 'Profil',
        'settings': 'Ayarlar',
        'logout': 'Çıkış',
        'morning_routine': 'Sabah Rutini',
        'evening_routine': 'Akşam Rutini',
        'weekly_routine': 'Haftalık Rutin',
        'skin_type': 'Cilt Tipi',
        'skin_issues': 'Cilt Sorunları',
        'overall_score': 'Genel Puan',
        'recommendations': 'Öneriler',
        'products': 'Ürünler',
        'take_photo': 'Fotoğraf Çek',
        'upload_photo': 'Fotoğraf Yükle',
        'analyzing': 'Cildiniz analiz ediliyor...',
        'analysis_complete': 'Analiz Tamamlandı',
        'view_results': 'Sonuçları Gör',
        'disclaimer': 'Bu analiz yalnızca kozmetik amaçlıdır ve tıbbi bir teşhis değildir.',
        'language': 'Dil',
        'dark_mode': 'Karanlık Mod',
        'home': 'Ana Sayfa',
        'score_poor': 'Kötü cilt durumu',
        'score_below_average': 'Ortalamanın altında',
        'score_average': 'Ortalama',
        'score_good': 'İyi cilt durumu',
        'score_excellent': 'Mükemmel',
        'oily': 'Yağlı',
        'dry': 'Kuru',
        'combination': 'Karma',
        'normal': 'Normal',
        'sensitive': 'Hassas',
        'quick_actions': 'Hızlı İşlemler',
        'latest_analysis': 'Son Analiz',
        'issues_detected': 'sorun tespit edildi',
        'score': 'Puan',
        'onboarding_1_title': 'Cildinizi Tarayın',
        'onboarding_1_desc': 'Yüzünüzün fotoğrafını çekin ve anında yapay zeka analizi alın',
        'onboarding_2_title': 'İlerlemenizi Takip Edin',
        'onboarding_2_desc': 'Cilt sağlığınızı zaman içinde izleyin',
        'onboarding_3_title': 'Öneriler Alın',
        'onboarding_3_desc': 'Kişiselleştirilmiş cilt bakım rutinleri alın',
        'next': 'İleri',
        'get_started': 'Başla',
        'skip': 'Atla'
    },
    'it': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Benvenuto',
        'login': 'Accedi',
        'register': 'Registrati',
        'scan_skin': 'Scansiona la pelle',
        'my_routines': 'Le mie routine',
        'progress': 'Progressi',
        'profile': 'Profilo',
        'settings': 'Impostazioni',
        'products': 'Prodotti',
        'home': 'Home',
        'skin_type': 'Tipo di pelle',
        'skin_issues': 'Problemi della pelle',
        'quick_actions': 'Azioni rapide',
        'latest_analysis': 'Ultima analisi',
        'issues_detected': 'problemi rilevati',
        'score': 'Punteggio',
        'onboarding_1_title': 'Scansiona la tua pelle',
        'onboarding_1_desc': 'Scatta una foto del tuo viso e ottieni un\'analisi istantanea',
        'onboarding_2_title': 'Monitora i progressi',
        'onboarding_2_desc': 'Monitora la salute della tua pelle nel tempo',
        'onboarding_3_title': 'Ricevi consigli',
        'onboarding_3_desc': 'Ottieni routine personalizzate per la cura della pelle',
        'next': 'Avanti',
        'get_started': 'Inizia',
        'skip': 'Salta'
    },
    'es': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Bienvenido',
        'login': 'Iniciar sesión',
        'register': 'Registrarse',
        'scan_skin': 'Escanear tu piel',
        'my_routines': 'Mis rutinas',
        'progress': 'Progreso',
        'profile': 'Perfil',
        'settings': 'Ajustes',
        'products': 'Productos',
        'home': 'Inicio',
        'skin_type': 'Tipo de piel',
        'skin_issues': 'Problemas de piel',
        'quick_actions': 'Acciones rápidas',
        'latest_analysis': 'Último análisis',
        'issues_detected': 'problemas detectados',
        'score': 'Puntuación',
        'onboarding_1_title': 'Escanea tu piel',
        'onboarding_1_desc': 'Toma una foto de tu rostro y obtén un análisis instantáneo',
        'onboarding_2_title': 'Sigue tu progreso',
        'onboarding_2_desc': 'Monitorea la salud de tu piel con el tiempo',
        'onboarding_3_title': 'Recibe recomendaciones',
        'onboarding_3_desc': 'Obtén rutinas de cuidado personalizadas',
        'next': 'Siguiente',
        'get_started': 'Comenzar',
        'skip': 'Omitir'
    },
    'de': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Willkommen',
        'login': 'Anmelden',
        'register': 'Registrieren',
        'scan_skin': 'Haut scannen',
        'my_routines': 'Meine Routinen',
        'progress': 'Fortschritt',
        'profile': 'Profil',
        'settings': 'Einstellungen',
        'products': 'Produkte',
        'home': 'Startseite',
        'skin_type': 'Hauttyp',
        'skin_issues': 'Hautprobleme',
        'quick_actions': 'Schnellaktionen',
        'latest_analysis': 'Letzte Analyse',
        'issues_detected': 'Probleme erkannt',
        'score': 'Punktzahl',
        'onboarding_1_title': 'Scannen Sie Ihre Haut',
        'onboarding_1_desc': 'Machen Sie ein Foto Ihres Gesichts und erhalten Sie eine sofortige Analyse',
        'onboarding_2_title': 'Fortschritt verfolgen',
        'onboarding_2_desc': 'Überwachen Sie Ihre Hautgesundheit im Laufe der Zeit',
        'onboarding_3_title': 'Empfehlungen erhalten',
        'onboarding_3_desc': 'Erhalten Sie personalisierte Hautpflege-Routinen',
        'next': 'Weiter',
        'get_started': 'Loslegen',
        'skip': 'Überspringen'
    },
    'ar': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'مرحباً',
        'login': 'تسجيل الدخول',
        'register': 'إنشاء حساب',
        'scan_skin': 'فحص بشرتك',
        'my_routines': 'روتيني',
        'progress': 'التقدم',
        'profile': 'الملف الشخصي',
        'settings': 'الإعدادات',
        'products': 'المنتجات',
        'home': 'الرئيسية',
        'skin_type': 'نوع البشرة',
        'skin_issues': 'مشاكل البشرة',
        'quick_actions': 'إجراءات سريعة',
        'latest_analysis': 'آخر تحليل',
        'issues_detected': 'مشاكل تم اكتشافها',
        'score': 'النتيجة',
        'onboarding_1_title': 'امسح بشرتك',
        'onboarding_1_desc': 'التقط صورة لوجهك واحصل على تحليل فوري',
        'onboarding_2_title': 'تتبع تقدمك',
        'onboarding_2_desc': 'راقب صحة بشرتك مع مرور الوقت',
        'onboarding_3_title': 'احصل على توصيات',
        'onboarding_3_desc': 'احصل على روتين مخصص للعناية بالبشرة',
        'next': 'التالي',
        'get_started': 'ابدأ',
        'skip': 'تخطي'
    },
    'zh': {
        'app_name': 'SkinAdvisor AI',
        'welcome': '欢迎',
        'login': '登录',
        'register': '注册',
        'scan_skin': '扫描皮肤',
        'my_routines': '我的日常',
        'progress': '进度',
        'profile': '个人资料',
        'settings': '设置',
        'products': '产品',
        'home': '首页',
        'skin_type': '皮肤类型',
        'skin_issues': '皮肤问题',
        'quick_actions': '快捷操作',
        'latest_analysis': '最新分析',
        'issues_detected': '检测到的问题',
        'score': '分数',
        'onboarding_1_title': '扫描您的皮肤',
        'onboarding_1_desc': '拍摄面部照片，获得即时AI分析',
        'onboarding_2_title': '跟踪进度',
        'onboarding_2_desc': '随时监测您的皮肤健康状况',
        'onboarding_3_title': '获取建议',
        'onboarding_3_desc': '获得个性化的护肤方案',
        'next': '下一步',
        'get_started': '开始',
        'skip': '跳过'
    },
    'hi': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'स्वागत है',
        'login': 'लॉगिन',
        'register': 'रजिस्टर',
        'scan_skin': 'त्वचा स्कैन करें',
        'my_routines': 'मेरी दिनचर्या',
        'progress': 'प्रगति',
        'profile': 'प्रोफ़ाइल',
        'settings': 'सेटिंग्स',
        'products': 'उत्पाद',
        'home': 'होम',
        'skin_type': 'त्वचा का प्रकार',
        'skin_issues': 'त्वचा की समस्याएं',
        'quick_actions': 'त्वरित कार्य',
        'latest_analysis': 'नवीनतम विश्लेषण',
        'issues_detected': 'समस्याएं पाई गईं',
        'score': 'स्कोर',
        'onboarding_1_title': 'अपनी त्वचा स्कैन करें',
        'onboarding_1_desc': 'अपने चेहरे की फोटो लें और तुरंत AI विश्लेषण प्राप्त करें',
        'onboarding_2_title': 'प्रगति ट्रैक करें',
        'onboarding_2_desc': 'समय के साथ अपनी त्वचा की सेहत पर नज़र रखें',
        'onboarding_3_title': 'सुझाव प्राप्त करें',
        'onboarding_3_desc': 'व्यक्तिगत त्वचा देखभाल रूटीन प्राप्त करें',
        'next': 'अगला',
        'get_started': 'शुरू करें',
        'skip': 'छोड़ें'
    }
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
