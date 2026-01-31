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

# Initialize OpenAI client with Emergent endpoint if using Emergent key
if OPENAI_API_KEY and OPENAI_API_KEY.startswith('sk-emergent'):
    openai_client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url="https://api.emergentmethods.ai/v1"
    )
elif OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None

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

# Social Authentication Models
class SocialAuthRequest(BaseModel):
    provider: str  # "google" or "apple"
    provider_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    id_token: Optional[str] = None
    language: str = "en"

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

def calculate_deterministic_score(issues: List[dict], skin_metrics: dict = None) -> dict:
    """
    PRD Phase 1: Calculate skin health score using DETERMINISTIC formula based on REAL SIGNALS.
    
    NEW: Score is now calculated from both:
    1. Skin metrics (tone_uniformity, texture, hydration, pores, redness) - weighted average
    2. Issue severity penalties - deductions for detected problems
    
    GOALS:
    - 90+ = top 3-5% (extremely rare)
    - 85-89 = top 10% (elite)
    - 70-84 = majority of users
    - <70 = common
    
    Score is calculated from MEASURABLE SIGNALS, not LLM opinion.
    """
    
    # ==================== CALCULATE BASE FROM METRICS (PRD Phase 1) ====================
    if skin_metrics:
        # Weighted average of skin metrics
        metric_weights = {
            'tone_uniformity': 0.25,
            'texture_smoothness': 0.25,
            'hydration_appearance': 0.20,
            'pore_visibility': 0.15,
            'redness_level': 0.15
        }
        
        metrics_score = 0
        total_weight = 0
        metrics_breakdown = []
        
        for metric_name, weight in metric_weights.items():
            if metric_name in skin_metrics:
                metric_data = skin_metrics[metric_name]
                score = metric_data.get('score', 70) if isinstance(metric_data, dict) else 70
                metrics_score += score * weight
                total_weight += weight
                metrics_breakdown.append({
                    'metric': metric_name.replace('_', ' ').title(),
                    'score': score,
                    'why': metric_data.get('why', '') if isinstance(metric_data, dict) else ''
                })
        
        if total_weight > 0:
            base_score = metrics_score / total_weight
        else:
            base_score = 75
    else:
        # Fallback to old base score if no metrics provided
        base_score = 75
        metrics_breakdown = []
    
    # ==================== APPLY ISSUE PENALTIES ====================
    score_factors = []
    total_deduction = 0
    
    # Track critical issues for hard cap rule
    critical_issues = {
        'acne': 0,
        'pores': 0,
        'uneven_tone': 0,
        'redness': 0,
    }
    
    max_severity = 0
    
    for issue in issues:
        issue_name = issue.get('name', '').lower().replace(' ', '_').replace('-', '_')
        severity = min(10, max(0, issue.get('severity', 0)))
        
        if severity > max_severity:
            max_severity = severity
        
        # Track critical issues
        for critical_key in critical_issues.keys():
            if critical_key in issue_name or issue_name in critical_key:
                critical_issues[critical_key] = max(critical_issues[critical_key], severity)
        
        # Find matching weight
        weight = 3  # Default weight
        for key, w in ISSUE_WEIGHTS.items():
            if key in issue_name or issue_name in key:
                weight = w
                break
        
        # Calculate deduction: severity * weight * 0.12 (slightly reduced from 0.15)
        deduction = severity * weight * 0.12
        total_deduction += deduction
        
        if severity > 0:
            severity_label = 'mild' if severity <= 3 else 'moderate' if severity <= 6 else 'severe'
            score_factors.append({
                'issue': issue.get('name', 'Unknown'),
                'severity': severity,
                'severity_label': severity_label,
                'deduction': round(deduction, 1),
                'why_this_result': issue.get('why_this_result', '')
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
    
    # Rule 4: 90+ ONLY allowed if ALL conditions met
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
        'factors': score_factors[:5],
        'metrics_breakdown': metrics_breakdown[:5] if metrics_breakdown else [],
        'base_score': round(base_score, 1),
        'total_deduction': round(total_deduction, 1),
        'calculation_method': 'metrics_based' if skin_metrics else 'issue_based'
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

@api_router.post("/auth/social", response_model=TokenResponse)
async def social_auth(request: SocialAuthRequest):
    """
    Handle social authentication (Google/Apple Sign-In).
    If user exists, log them in. If not, create a new account.
    """
    # Check if user already exists with this social provider
    existing_user = await db.users.find_one({
        f'social_{request.provider}_id': request.provider_id
    })
    
    if existing_user:
        # User exists - log them in
        token = create_token(existing_user['id'])
        return TokenResponse(
            access_token=token,
            user=UserResponse(
                id=existing_user['id'],
                email=existing_user['email'],
                name=existing_user['name'],
                profile=UserProfile(**existing_user.get('profile', {})) if existing_user.get('profile') else None,
                plan=existing_user.get('plan', 'free'),
                scan_count=existing_user.get('scan_count', 0),
                created_at=existing_user['created_at']
            )
        )
    
    # Check if email already exists (user might have registered with email before)
    if request.email:
        email_user = await db.users.find_one({'email': request.email})
        if email_user:
            # Link social account to existing user
            await db.users.update_one(
                {'id': email_user['id']},
                {'$set': {f'social_{request.provider}_id': request.provider_id}}
            )
            token = create_token(email_user['id'])
            return TokenResponse(
                access_token=token,
                user=UserResponse(
                    id=email_user['id'],
                    email=email_user['email'],
                    name=email_user['name'],
                    profile=UserProfile(**email_user.get('profile', {})) if email_user.get('profile') else None,
                    plan=email_user.get('plan', 'free'),
                    scan_count=email_user.get('scan_count', 0),
                    created_at=email_user['created_at']
                )
            )
    
    # Create new user with social auth
    user_id = str(uuid.uuid4())
    email = request.email or f"{request.provider}_{request.provider_id}@social.auth"
    name = request.name or f"{request.provider.capitalize()} User"
    
    new_user = {
        'id': user_id,
        'email': email,
        'name': name,
        'password': None,  # No password for social auth users
        f'social_{request.provider}_id': request.provider_id,
        'profile': {'language': request.language},
        'plan': 'free',
        'scan_count': 0,
        'created_at': datetime.utcnow()
    }
    
    await db.users.insert_one(new_user)
    token = create_token(user_id)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=email,
            name=name,
            profile=UserProfile(language=request.language),
            plan='free',
            scan_count=0,
            created_at=new_user['created_at']
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
    PRD Phase 1: Real Skin Analysis Engine
    
    Analyzes skin using OpenAI GPT-4o vision with DETERMINISTIC settings.
    Extracts REAL, MEASURABLE signals from the photo:
    - Skin metrics (tone_uniformity, texture, hydration, pores, redness)
    - Detected issues with severity and "why this result" explanation
    - Skin strengths (positive aspects)
    
    Temperature = 0 for consistent results (same image = same score).
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    
    # PRD Phase 1: Enhanced DETERMINISTIC PROMPT with real signals extraction
    system_prompt = f"""You are a professional dermatological AI analyzer for cosmetic skin assessment.
Your analysis must be CONSISTENT and DETERMINISTIC - the same image MUST produce the same results.

CRITICAL MEASUREMENT RULES:
1. Analyze ONLY what is visible in the image - no assumptions
2. Use FIXED numeric thresholds for ALL measurements
3. Provide "why_this_result" explanation for EVERY metric and issue
4. Identify STRENGTHS (positive aspects) not just problems
5. Be precise - scores must be reproducible

=== SKIN METRICS (0-100 scale, higher = better) ===
Measure these 5 core metrics based on VISIBLE signals:

1. tone_uniformity (0-100): How even is the skin color?
   - 90-100: Very uniform, minimal variation
   - 70-89: Mostly uniform, minor variations
   - 50-69: Noticeable unevenness
   - 0-49: Significant discoloration/patches

2. texture_smoothness (0-100): How smooth is the skin surface?
   - 90-100: Very smooth, no visible texture issues
   - 70-89: Generally smooth, minor irregularities
   - 50-69: Visible texture concerns
   - 0-49: Rough, bumpy texture

3. hydration_appearance (0-100): How hydrated does skin look?
   - 90-100: Plump, dewy appearance
   - 70-89: Healthy moisture levels
   - 50-69: Slightly dry/dull appearance
   - 0-49: Visibly dry, flaky, or dehydrated

4. pore_visibility (0-100): How refined are pores? (higher = less visible)
   - 90-100: Pores nearly invisible
   - 70-89: Minor pore visibility
   - 50-69: Noticeably visible pores
   - 0-49: Large, prominent pores

5. redness_level (0-100): How calm is the skin? (higher = less redness)
   - 90-100: No redness, calm complexion
   - 70-89: Minimal redness
   - 50-69: Moderate redness/inflammation
   - 0-49: Significant redness

=== SKIN TYPE CLASSIFICATION ===
Choose ONE based on visible characteristics:
- "oily": Visible shine, enlarged pores, especially in T-zone
- "dry": Flaky patches, tight appearance, fine dehydration lines
- "combination": Oily T-zone with dry/normal cheeks
- "normal": Balanced, minimal issues, healthy appearance
- "sensitive": Visible redness, reactive appearance

=== ISSUE DETECTION ===
For each detected issue provide:
- name: Specific issue name
- severity: Integer 1-10 (1-3=mild, 4-6=moderate, 7-10=severe)
- confidence: Float 0.5-1.0 (minimum 0.5 to report)
- description: Brief factual observation
- why_this_result: Explain what VISIBLE signals led to this detection
- priority: "primary", "secondary", or "minor"

=== STRENGTHS DETECTION ===
Identify 2-4 POSITIVE aspects of the skin:
- name: Strength name (e.g., "Good skin elasticity")
- description: Why this is a positive
- confidence: Float 0.5-1.0

Respond ONLY with valid JSON in {lang_name}. Structure:
{{
  "skin_type": "type",
  "skin_type_confidence": 0.9,
  "skin_type_description": "description with why",
  "skin_metrics": {{
    "tone_uniformity": {{"score": 75, "why": "reason"}},
    "texture_smoothness": {{"score": 70, "why": "reason"}},
    "hydration_appearance": {{"score": 80, "why": "reason"}},
    "pore_visibility": {{"score": 65, "why": "reason"}},
    "redness_level": {{"score": 85, "why": "reason"}}
  }},
  "strengths": [{{"name": "strength", "description": "why positive", "confidence": 0.9}}],
  "issues": [{{"name": "issue", "severity": 5, "confidence": 0.8, "description": "observation", "why_this_result": "visible signals", "priority": "primary"}}],
  "primary_concern": {{"name": "main issue", "severity": 6, "why_this_result": "explanation"}},
  "recommendations": ["advice1", "advice2"]
}}"""
    
    try:
        if not openai_client:
            logger.warning("OpenAI client not initialized, using fallback")
            return get_fallback_analysis(language)
        
        user_prompt = f"""Analyze this facial skin image with precision:

1. SKIN METRICS: Measure all 5 metrics (tone_uniformity, texture_smoothness, hydration_appearance, pore_visibility, redness_level) on 0-100 scale with "why" explanations
2. SKIN TYPE: Classify with confidence score
3. STRENGTHS: Identify 2-4 positive aspects of this skin
4. ISSUES: Detect concerns with severity (1-10), confidence, and "why_this_result" explanation
5. PRIMARY CONCERN: Identify the single most important issue to address
6. RECOMMENDATIONS: 3-5 specific skincare recommendations

Check for: acne, dark spots, wrinkles, fine lines, redness, large pores, dehydration, oiliness, uneven tone, blackheads, texture issues, sun damage, dark circles, dullness.

Return ONLY valid JSON. All descriptions in {lang_name}."""

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
            # Validate and normalize the response with PRD Phase 1 structure
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
    PRD Phase 1: Validate and normalize AI response with REAL SIGNALS.
    
    CRITICAL RULES:
    1. Extract and validate skin_metrics (5 core measurements)
    2. Extract strengths (positive aspects)
    3. Ensure issues have "why_this_result" explanations
    4. Identify primary_concern for free users
    5. ALWAYS return at least 1-3 optimization issues (no face is perfect)
    """
    
    # ==================== VALIDATE SKIN TYPE ====================
    valid_skin_types = ['oily', 'dry', 'combination', 'normal', 'sensitive']
    skin_type = result.get('skin_type', 'normal').lower()
    if skin_type not in valid_skin_types:
        skin_type = 'combination'
    
    skin_type_confidence = result.get('skin_type_confidence', 0.8)
    if not isinstance(skin_type_confidence, (int, float)):
        skin_type_confidence = 0.8
    skin_type_confidence = max(0.0, min(1.0, float(skin_type_confidence)))
    
    # ==================== VALIDATE SKIN METRICS (PRD Phase 1) ====================
    default_metrics = {
        'tone_uniformity': {'score': 70, 'why': 'Minor variations observed in skin tone'},
        'texture_smoothness': {'score': 72, 'why': 'Generally smooth with minor irregularities'},
        'hydration_appearance': {'score': 68, 'why': 'Skin shows adequate moisture levels'},
        'pore_visibility': {'score': 65, 'why': 'Pores visible in some areas'},
        'redness_level': {'score': 75, 'why': 'Minimal redness observed'}
    }
    
    raw_metrics = result.get('skin_metrics', {})
    validated_metrics = {}
    
    for metric_name, default_value in default_metrics.items():
        if metric_name in raw_metrics and isinstance(raw_metrics[metric_name], dict):
            metric_data = raw_metrics[metric_name]
            score = metric_data.get('score', default_value['score'])
            if not isinstance(score, (int, float)):
                score = default_value['score']
            score = int(max(0, min(100, score)))
            
            why = metric_data.get('why', default_value['why'])
            if not isinstance(why, str) or len(why) < 5:
                why = default_value['why']
            
            validated_metrics[metric_name] = {
                'score': score,
                'why': str(why)
            }
        else:
            validated_metrics[metric_name] = default_value
    
    # ==================== VALIDATE STRENGTHS (PRD Phase 1) ====================
    default_strengths = [
        {'name': 'Natural skin resilience', 'description': 'Your skin shows good natural recovery ability', 'confidence': 0.8},
        {'name': 'Even facial structure', 'description': 'Good overall facial balance', 'confidence': 0.75}
    ]
    
    raw_strengths = result.get('strengths', [])
    validated_strengths = []
    
    if isinstance(raw_strengths, list):
        for strength in raw_strengths:
            if isinstance(strength, dict) and strength.get('name'):
                confidence = strength.get('confidence', 0.75)
                if not isinstance(confidence, (int, float)):
                    confidence = 0.75
                confidence = max(0.5, min(1.0, float(confidence)))
                
                validated_strengths.append({
                    'name': str(strength.get('name', '')),
                    'description': str(strength.get('description', 'Positive aspect detected')),
                    'confidence': round(confidence, 2)
                })
    
    # Ensure at least 2 strengths
    if len(validated_strengths) < 2:
        existing_names = {s['name'].lower() for s in validated_strengths}
        for default_str in default_strengths:
            if default_str['name'].lower() not in existing_names:
                validated_strengths.append(default_str)
                if len(validated_strengths) >= 2:
                    break
    
    validated_strengths = validated_strengths[:4]  # Max 4 strengths
    
    # ==================== VALIDATE ISSUES (Enhanced with PRD Phase 1) ====================
    validated_issues = []
    raw_issues = result.get('issues', [])
    
    for issue in raw_issues:
        if not isinstance(issue, dict):
            continue
            
        name = issue.get('name', '')
        if not name:
            continue
            
        # Clamp severity to 1-10 (minimum 1 if detected)
        severity = issue.get('severity', 1)
        if not isinstance(severity, (int, float)):
            severity = 1
        severity = int(max(1, min(10, severity)))
        
        # Clamp confidence to 0.5-1.0
        confidence = issue.get('confidence', 0.7)
        if not isinstance(confidence, (int, float)):
            confidence = 0.7
        confidence = max(0.5, min(1.0, float(confidence)))
        
        # Validate priority
        priority = issue.get('priority', 'secondary')
        if priority not in ['primary', 'secondary', 'minor']:
            priority = 'secondary'
        
        # Get "why_this_result" explanation (PRD requirement)
        why_this_result = issue.get('why_this_result', '')
        if not isinstance(why_this_result, str) or len(why_this_result) < 10:
            why_this_result = 'Detected based on visible skin characteristics in the analyzed area'
        
        # Only include issues with confidence > 0.5
        if confidence >= 0.5:
            validated_issues.append({
                'name': str(name),
                'severity': severity,
                'confidence': round(confidence, 2),
                'description': str(issue.get('description', f'{name} detected')),
                'why_this_result': str(why_this_result),
                'priority': priority
            })
    
    # ==================== ENSURE MINIMUM ISSUES ====================
    if len(validated_issues) < 3:
        existing_names = {i['name'].lower() for i in validated_issues}
        
        for opt_issue in UNIVERSAL_OPTIMIZATION_ISSUES:
            if opt_issue['name'].lower() not in existing_names:
                validated_issues.append({
                    'name': opt_issue['name'],
                    'severity': opt_issue['severity'],
                    'confidence': opt_issue['confidence'],
                    'description': opt_issue['description'],
                    'why_this_result': 'Based on general skin health optimization principles',
                    'priority': 'minor'
                })
                if len(validated_issues) >= 3:
                    break
    
    # Sort by severity (highest first), then by priority
    priority_order = {'primary': 0, 'secondary': 1, 'minor': 2}
    validated_issues.sort(key=lambda x: (-x['severity'], priority_order.get(x['priority'], 1)))
    
    # ==================== VALIDATE PRIMARY CONCERN (PRD Phase 1 - for free users) ====================
    raw_primary = result.get('primary_concern', {})
    if validated_issues:
        # Use the highest severity issue as primary concern
        top_issue = validated_issues[0]
        primary_concern = {
            'name': top_issue['name'],
            'severity': top_issue['severity'],
            'why_this_result': top_issue.get('why_this_result', 'This is your most significant skin concern')
        }
    else:
        primary_concern = {
            'name': 'General skin optimization',
            'severity': 2,
            'why_this_result': 'Your skin is generally healthy but can benefit from consistent care'
        }
    
    # Override with AI's primary concern if valid
    if isinstance(raw_primary, dict) and raw_primary.get('name'):
        primary_concern = {
            'name': str(raw_primary.get('name', primary_concern['name'])),
            'severity': int(max(1, min(10, raw_primary.get('severity', primary_concern['severity'])))),
            'why_this_result': str(raw_primary.get('why_this_result', primary_concern['why_this_result']))
        }
    
    # ==================== VALIDATE RECOMMENDATIONS ====================
    recommendations = result.get('recommendations', [])
    if not isinstance(recommendations, list):
        recommendations = []
    recommendations = [str(r) for r in recommendations if r][:5]
    
    if not recommendations:
        recommendations = [
            "Maintain a consistent skincare routine",
            "Use sunscreen daily (SPF 30+)",
            "Stay hydrated - aim for 8 glasses of water daily"
        ]
    
    return {
        'skin_type': skin_type,
        'skin_type_confidence': round(skin_type_confidence, 2),
        'skin_type_description': result.get('skin_type_description', f'Your skin type appears to be {skin_type}'),
        'skin_metrics': validated_metrics,
        'strengths': validated_strengths,
        'issues': validated_issues,
        'primary_concern': primary_concern,
        'recommendations': recommendations
    }

def get_fallback_analysis(language: str) -> dict:
    """
    PRD Phase 1: Return a safe fallback analysis when AI fails.
    Includes skin_metrics, strengths, and enhanced issues structure.
    """
    return {
        'skin_type': 'combination',
        'skin_type_confidence': 0.6,
        'skin_type_description': 'Analysis completed. Your skin shows typical characteristics that can be improved with proper care.',
        'skin_metrics': {
            'tone_uniformity': {'score': 70, 'why': 'Minor variations observed in skin tone'},
            'texture_smoothness': {'score': 72, 'why': 'Generally smooth with minor irregularities'},
            'hydration_appearance': {'score': 68, 'why': 'Skin shows adequate moisture levels'},
            'pore_visibility': {'score': 65, 'why': 'Pores visible in some areas'},
            'redness_level': {'score': 75, 'why': 'Minimal redness observed'}
        },
        'strengths': [
            {'name': 'Natural skin resilience', 'description': 'Your skin shows good natural recovery ability', 'confidence': 0.8},
            {'name': 'Even facial structure', 'description': 'Good overall facial balance', 'confidence': 0.75}
        ],
        'issues': [
            {
                'name': 'Hydration optimization', 
                'severity': 2, 
                'confidence': 0.9, 
                'description': 'Skin hydration can always be improved for better elasticity and glow',
                'why_this_result': 'Based on general skin health optimization principles',
                'priority': 'secondary'
            },
            {
                'name': 'Pore refinement', 
                'severity': 2, 
                'confidence': 0.85, 
                'description': 'Pore appearance can be minimized with proper care',
                'why_this_result': 'Standard recommendation for most skin types',
                'priority': 'minor'
            },
            {
                'name': 'Skin barrier health', 
                'severity': 1, 
                'confidence': 0.9, 
                'description': 'Maintaining skin barrier integrity prevents future issues',
                'why_this_result': 'Preventive care recommendation',
                'priority': 'minor'
            },
        ],
        'primary_concern': {
            'name': 'Hydration optimization',
            'severity': 2,
            'why_this_result': 'Improving hydration is the most impactful first step for most skin types'
        },
        'recommendations': [
            'Use a gentle cleanser twice daily',
            'Apply moisturizer appropriate for your skin type',
            'Use sunscreen daily (SPF 30+)',
            'Stay hydrated - drink 2L water daily',
            'Consider adding a vitamin C serum for brightness'
        ]
    }

async def generate_routine_with_ai(analysis: dict, language: str = 'en') -> dict:
    """
    PRD Phase 2: Personalized Routine Engine
    
    Generate skincare routine based on REAL analysis with:
    1. Steps tailored to detected issues and skin metrics
    2. Sequential locking mechanism (Step N+1 requires completing Step N)
    3. "Why this step?" explanations linking to detected concerns
    4. Difficulty levels and time estimates
    """
    if not OPENAI_API_KEY:
        return get_fallback_routine(analysis.get('skin_type', 'normal'), analysis)
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    skin_type = analysis.get('skin_type', 'normal')
    issues = analysis.get('issues', [])
    skin_metrics = analysis.get('skin_metrics', {})
    primary_concern = analysis.get('primary_concern', {})
    
    # Build context from PRD Phase 1 data
    issues_text = ', '.join([f"{i['name']} (severity {i['severity']}, priority: {i.get('priority', 'secondary')})" for i in issues[:5]]) if issues else 'No major issues'
    
    # Extract metric insights for routine customization
    metrics_context = []
    if skin_metrics:
        for metric_name, metric_data in skin_metrics.items():
            if isinstance(metric_data, dict):
                score = metric_data.get('score', 70)
                if score < 70:  # Focus on areas needing improvement
                    metrics_context.append(f"{metric_name.replace('_', ' ')}: {score}/100 (needs attention)")
    metrics_text = ', '.join(metrics_context) if metrics_context else 'All metrics above average'
    
    system_prompt = f"""You are a skincare routine expert creating PERSONALIZED routines based on real skin analysis data.

=== ANALYSIS DATA ===
- Skin Type: {skin_type}
- Detected Issues: {issues_text}
- Metrics Needing Attention: {metrics_text}
- Primary Concern: {primary_concern.get('name', 'General optimization')}

=== PRD REQUIREMENTS ===
1. Each step MUST target a specific detected issue or metric
2. Include "why_this_step" explaining how it addresses the user's specific concerns
3. Steps should be ordered from essential to advanced
4. Include estimated time per step
5. Mark which issue/metric each step addresses (targets_issue)

=== ROUTINE STRUCTURE ===
Respond ONLY with JSON in {lang_name}:
{{
  "morning_routine": [
    {{
      "order": 1,
      "step_name": "name",
      "product_type": "type",
      "instructions": "detailed how-to",
      "why_this_step": "Addresses your [specific issue] by...",
      "targets_issue": "issue name from analysis",
      "time_minutes": 2,
      "ingredients_to_look_for": ["ing1"],
      "ingredients_to_avoid": ["ing1"],
      "is_essential": true
    }}
  ],
  "evening_routine": [...],
  "weekly_routine": [
    {{
      "order": 1,
      "step_name": "Weekly Treatment",
      "product_type": "mask",
      "instructions": "...",
      "why_this_step": "...",
      "targets_issue": "...",
      "frequency": "1-2x per week",
      "time_minutes": 15,
      "ingredients_to_look_for": [],
      "ingredients_to_avoid": [],
      "is_essential": false
    }}
  ],
  "products": [
    {{
      "product_type": "type",
      "name": "generic name",
      "description": "why recommended",
      "addresses_concern": "links to detected issue",
      "key_ingredients": ["ing"],
      "suitable_for": ["{skin_type}"],
      "price_range": "$$"
    }}
  ]
}}"""
    
    try:
        if not openai_client:
            logger.warning("OpenAI client not initialized, using fallback")
            return get_fallback_routine(skin_type, analysis)
        
        user_prompt = f"""Create a PERSONALIZED skincare routine for this specific analysis:

SKIN TYPE: {skin_type}
PRIMARY CONCERN: {primary_concern.get('name', 'General skin health')} - {primary_concern.get('why_this_result', '')}
DETECTED ISSUES: {issues_text}
METRICS TO IMPROVE: {metrics_text}

Requirements:
1. Morning routine: 4-5 steps, each targeting a specific concern
2. Evening routine: 4-5 steps, include treatment for primary concern  
3. Weekly routine: 1-2 treatments for intensive care
4. Products: 5-7 recommendations, each linked to a detected issue

For each step, explain WHY it's needed for THIS user's specific skin concerns.
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
            return validate_routine_response(result, skin_type, analysis)
        else:
            return get_fallback_routine(skin_type, analysis)
            
    except Exception as e:
        logger.error(f"Routine generation error: {str(e)}")
        return get_fallback_routine(skin_type, analysis)

def validate_routine_response(result: dict, skin_type: str, analysis: dict = None) -> dict:
    """
    PRD Phase 2: Validate routine response with sequential locking structure.
    
    Each step includes:
    - locked: boolean (for sequential unlock)
    - completed: boolean (for progress tracking)
    - why_this_step: explanation linking to user's concerns
    - targets_issue: which issue this step addresses
    """
    validated = {
        'morning_routine': [],
        'evening_routine': [],
        'weekly_routine': [],
        'products': []
    }
    
    for key in ['morning_routine', 'evening_routine', 'weekly_routine']:
        routine = result.get(key, [])
        if isinstance(routine, list):
            for idx, step in enumerate(routine):
                if isinstance(step, dict) and step.get('step_name'):
                    validated[key].append({
                        'order': step.get('order', idx + 1),
                        'step_name': str(step.get('step_name', '')),
                        'product_type': str(step.get('product_type', 'unknown')),
                        'instructions': str(step.get('instructions', '')),
                        # PRD Phase 2: "Why this step?" explanation
                        'why_this_step': str(step.get('why_this_step', 'Recommended for your skin type')),
                        'targets_issue': str(step.get('targets_issue', 'General skin health')),
                        'time_minutes': int(step.get('time_minutes', 2)),
                        'ingredients_to_look_for': step.get('ingredients_to_look_for', []),
                        'ingredients_to_avoid': step.get('ingredients_to_avoid', []),
                        'is_essential': bool(step.get('is_essential', idx < 3)),
                        # PRD Phase 2: Sequential locking - first step unlocked, rest locked
                        'locked': idx > 0,
                        'completed': False,
                        # Weekly specific
                        'frequency': step.get('frequency', '1x per week') if key == 'weekly_routine' else None
                    })
    
    products = result.get('products', [])
    if isinstance(products, list):
        for product in products:
            if isinstance(product, dict) and product.get('product_type'):
                validated['products'].append({
                    'product_type': str(product.get('product_type', '')),
                    'name': str(product.get('name', '')),
                    'description': str(product.get('description', '')),
                    # PRD Phase 2: Link product to concern
                    'addresses_concern': str(product.get('addresses_concern', 'General skin health')),
                    'key_ingredients': product.get('key_ingredients', []),
                    'suitable_for': product.get('suitable_for', [skin_type]),
                    'price_range': str(product.get('price_range', '$$'))
                })
    
    # If routines are empty, use fallback
    if not validated['morning_routine']:
        return get_fallback_routine(skin_type, analysis)
    
    return validated

def get_fallback_routine(skin_type: str, analysis: dict = None) -> dict:
    """
    PRD Phase 2: Return a personalized fallback routine.
    Includes sequential locking and links to detected issues.
    """
    primary_concern = 'General skin health'
    if analysis and analysis.get('primary_concern'):
        primary_concern = analysis['primary_concern'].get('name', 'General skin health')
    
    return {
        "morning_routine": [
            {
                "order": 1, 
                "step_name": "Gentle Cleanser", 
                "product_type": "cleanser", 
                "instructions": "Gently massage onto damp skin for 30-60 seconds, rinse with lukewarm water", 
                "why_this_step": "Removes overnight buildup and prepares skin for treatment products",
                "targets_issue": "Skin barrier health",
                "time_minutes": 2,
                "ingredients_to_look_for": ["glycerin", "ceramides"], 
                "ingredients_to_avoid": ["alcohol", "sulfates"],
                "is_essential": True,
                "locked": False,
                "completed": False
            },
            {
                "order": 2, 
                "step_name": "Hydrating Toner", 
                "product_type": "toner", 
                "instructions": "Apply with cotton pad or pat directly into skin while still damp", 
                "why_this_step": "Balances pH and adds first layer of hydration",
                "targets_issue": "Hydration optimization",
                "time_minutes": 1,
                "ingredients_to_look_for": ["niacinamide", "hyaluronic acid"], 
                "ingredients_to_avoid": ["alcohol"],
                "is_essential": True,
                "locked": True,
                "completed": False
            },
            {
                "order": 3, 
                "step_name": "Daily Moisturizer", 
                "product_type": "moisturizer", 
                "instructions": "Apply evenly to face and neck using upward motions", 
                "why_this_step": f"Locks in hydration and addresses {primary_concern}",
                "targets_issue": primary_concern,
                "time_minutes": 2,
                "ingredients_to_look_for": ["ceramides", "hyaluronic acid"], 
                "ingredients_to_avoid": ["fragrance"],
                "is_essential": True,
                "locked": True,
                "completed": False
            },
            {
                "order": 4, 
                "step_name": "Sunscreen SPF 30+", 
                "product_type": "sunscreen", 
                "instructions": "Apply generously 15 minutes before sun exposure. Reapply every 2 hours", 
                "why_this_step": "Prevents UV damage which worsens most skin concerns",
                "targets_issue": "Sun protection",
                "time_minutes": 2,
                "ingredients_to_look_for": ["SPF 30+", "zinc oxide", "titanium dioxide"], 
                "ingredients_to_avoid": ["oxybenzone"],
                "is_essential": True,
                "locked": True,
                "completed": False
            }
        ],
        "evening_routine": [
            {
                "order": 1, 
                "step_name": "Oil Cleanser", 
                "product_type": "cleanser", 
                "instructions": "Massage onto dry skin to dissolve makeup and sunscreen, then rinse", 
                "why_this_step": "First step of double cleanse - removes oil-based impurities",
                "targets_issue": "Pore refinement",
                "time_minutes": 2,
                "ingredients_to_look_for": ["jojoba oil", "squalane"], 
                "ingredients_to_avoid": ["mineral oil"],
                "is_essential": True,
                "locked": False,
                "completed": False
            },
            {
                "order": 2, 
                "step_name": "Water-Based Cleanser", 
                "product_type": "cleanser", 
                "instructions": "Gently cleanse to remove remaining residue", 
                "why_this_step": "Second cleanse ensures completely clean skin for treatments",
                "targets_issue": "Skin barrier health",
                "time_minutes": 2,
                "ingredients_to_look_for": ["gentle surfactants", "glycerin"], 
                "ingredients_to_avoid": ["harsh sulfates"],
                "is_essential": True,
                "locked": True,
                "completed": False
            },
            {
                "order": 3, 
                "step_name": "Treatment Serum", 
                "product_type": "serum", 
                "instructions": "Apply 2-3 drops to clean, dry skin. Pat gently to absorb", 
                "why_this_step": f"Active treatment targeting your {primary_concern}",
                "targets_issue": primary_concern,
                "time_minutes": 2,
                "ingredients_to_look_for": ["retinol", "vitamin C", "niacinamide"], 
                "ingredients_to_avoid": ["mixing actives"],
                "is_essential": True,
                "locked": True,
                "completed": False
            },
            {
                "order": 4, 
                "step_name": "Night Cream", 
                "product_type": "moisturizer", 
                "instructions": "Apply a thicker layer to support overnight repair", 
                "why_this_step": "Supports skin regeneration during sleep",
                "targets_issue": "Skin barrier health",
                "time_minutes": 2,
                "ingredients_to_look_for": ["peptides", "ceramides", "squalane"], 
                "ingredients_to_avoid": ["heavy fragrance"],
                "is_essential": True,
                "locked": True,
                "completed": False
            }
        ],
        "weekly_routine": [
            {
                "order": 1, 
                "step_name": "Exfoliating Treatment", 
                "product_type": "exfoliant", 
                "instructions": "Apply to clean skin, leave for recommended time, rinse thoroughly", 
                "why_this_step": "Removes dead skin cells and improves texture",
                "targets_issue": "Texture smoothness",
                "frequency": "1-2x per week",
                "time_minutes": 15,
                "ingredients_to_look_for": ["AHA", "BHA", "PHA"], 
                "ingredients_to_avoid": ["physical scrubs with sharp particles"],
                "is_essential": False,
                "locked": False,
                "completed": False
            },
            {
                "order": 2, 
                "step_name": "Hydrating Mask", 
                "product_type": "mask", 
                "instructions": "Apply a thick layer, relax for 15-20 minutes, rinse or remove", 
                "why_this_step": "Intensive hydration boost for improved skin plumpness",
                "targets_issue": "Hydration optimization",
                "frequency": "1x per week",
                "time_minutes": 20,
                "ingredients_to_look_for": ["hyaluronic acid", "aloe vera", "honey"], 
                "ingredients_to_avoid": ["alcohol"],
                "is_essential": False,
                "locked": True,
                "completed": False
            }
        ],
        "products": [
            {"product_type": "cleanser", "name": "Gentle Foaming Cleanser", "description": "Mild cleansing without stripping", "addresses_concern": "Skin barrier health", "key_ingredients": ["glycerin", "ceramides"], "suitable_for": [skin_type], "price_range": "$$"},
            {"product_type": "toner", "name": "Hydrating Essence Toner", "description": "Preps skin and adds hydration", "addresses_concern": "Hydration optimization", "key_ingredients": ["hyaluronic acid", "niacinamide"], "suitable_for": [skin_type], "price_range": "$$"},
            {"product_type": "serum", "name": "Active Treatment Serum", "description": f"Targets {primary_concern}", "addresses_concern": primary_concern, "key_ingredients": ["vitamin C", "niacinamide"], "suitable_for": [skin_type], "price_range": "$$$"},
            {"product_type": "moisturizer", "name": "Daily Hydrating Cream", "description": "Locks in moisture all day", "addresses_concern": "Hydration optimization", "key_ingredients": ["ceramides", "squalane"], "suitable_for": [skin_type], "price_range": "$$"},
            {"product_type": "sunscreen", "name": "Broad Spectrum SPF 50", "description": "Essential UV protection", "addresses_concern": "Sun protection", "key_ingredients": ["zinc oxide", "titanium dioxide"], "suitable_for": ["all skin types"], "price_range": "$$"}
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
            # Perform AI analysis (PRD Phase 1: Real Signals Extraction)
            analysis = await analyze_skin_with_ai(request.image_base64, language)
            
            # Calculate DETERMINISTIC score from REAL SIGNALS (PRD Phase 1)
            # Now uses both skin_metrics AND issues for accurate scoring
            score_data = calculate_deterministic_score(
                issues=analysis.get('issues', []),
                skin_metrics=analysis.get('skin_metrics', None)
            )
            
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
        
        # Create scan record with all data (always store full data) - PRD Phase 1 Enhanced
        scan = {
            'id': str(uuid.uuid4()),
            'user_id': current_user['id'],
            'image_base64': request.image_base64,
            'image_hash': image_hash,
            'analysis': {
                'skin_type': analysis.get('skin_type'),
                'skin_type_confidence': analysis.get('skin_type_confidence', 0.8),
                'skin_type_description': analysis.get('skin_type_description'),
                'skin_metrics': analysis.get('skin_metrics', {}),  # PRD Phase 1
                'strengths': analysis.get('strengths', []),  # PRD Phase 1
                'issues': analysis.get('issues', []),
                'primary_concern': analysis.get('primary_concern', {}),  # PRD Phase 1
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
            # PREMIUM USER: Return full response with PRD Phase 1 data
            return {
                'id': scan['id'],
                'user_plan': 'premium',
                'locked': False,
                'analysis': {
                    'skin_type': scan['analysis']['skin_type'],
                    'skin_type_confidence': scan['analysis']['skin_type_confidence'],
                    'skin_type_description': scan['analysis']['skin_type_description'],
                    # PRD Phase 1: Real measurable signals
                    'skin_metrics': scan['analysis'].get('skin_metrics', {}),
                    'strengths': scan['analysis'].get('strengths', []),
                    'issues': scan['analysis']['issues'],
                    'primary_concern': scan['analysis'].get('primary_concern', {}),
                    'recommendations': scan['analysis']['recommendations'],
                    'overall_score': score_data['score'],
                    'score_label': score_data['label'],
                    'score_description': score_data['description'],
                    'score_factors': score_data['factors'],
                    # PRD Phase 1: Metrics breakdown for transparency
                    'metrics_breakdown': score_data.get('metrics_breakdown', []),
                    'calculation_method': score_data.get('calculation_method', 'issue_based')
                },
                'routine': scan['routine'],
                'products': scan['products'],
                'diet_recommendations': diet_recommendations,
                'progress_tracking_enabled': True,
                'created_at': scan['created_at'].isoformat(),
                'image_hash': image_hash
            }
        else:
            # FREE USER (PRD Phase 3: Free Experience - Honest Curiosity)
            # Shows: 1 overall score, 1-2 strengths, primary concern only
            all_issues = scan['analysis']['issues']
            issue_count = len(all_issues)
            all_strengths = scan['analysis'].get('strengths', [])
            primary_concern = scan['analysis'].get('primary_concern', {})
            
            # PRD Phase 3: Free users get limited strengths (1-2 max)
            free_strengths = all_strengths[:2] if all_strengths else []
            
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
            
            return {
                'id': scan['id'],
                'user_plan': 'free',
                'locked': True,
                'analysis': {
                    'skin_type': scan['analysis']['skin_type'],
                    'overall_score': score_data['score'],
                    'score_label': score_data['label'],
                    # PRD Phase 3: Free users see strengths (builds trust)
                    'strengths': free_strengths,
                    # PRD Phase 3: Free users see PRIMARY concern only (drives curiosity)
                    'primary_concern': {
                        'name': primary_concern.get('name', 'Skin concern detected'),
                        'why_this_result': primary_concern.get('why_this_result', 'Based on your skin analysis')
                    },
                    # Issue names visible, details locked
                    'issue_count': issue_count,
                    'issues_preview': issues_preview,
                },
                'locked_features': [
                    'issue_details',
                    'skin_metrics',
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
        # PREMIUM USER: Return full response with PRD Phase 1 data
        return {
            'id': scan['id'],
            'user_plan': 'premium',
            'locked': False,
            'image_base64': scan.get('image_base64'),
            'image_hash': scan.get('image_hash'),
            'analysis': {
                'skin_type': analysis.get('skin_type'),
                'skin_type_confidence': analysis.get('skin_type_confidence', 0.8),
                'skin_type_description': analysis.get('skin_type_description'),
                # PRD Phase 1: Real measurable signals
                'skin_metrics': analysis.get('skin_metrics', {}),
                'strengths': analysis.get('strengths', []),
                'issues': analysis.get('issues', []),
                'primary_concern': analysis.get('primary_concern', {}),
                'recommendations': analysis.get('recommendations', []),
                'overall_score': score_data.get('score', 75),
                'score_label': score_data.get('label', 'good'),
                'score_description': score_data.get('description', 'Good skin condition'),
                'score_factors': score_data.get('factors', []),
                # PRD Phase 1: Metrics breakdown for transparency
                'metrics_breakdown': score_data.get('metrics_breakdown', []),
                'calculation_method': score_data.get('calculation_method', 'issue_based')
            },
            'routine': scan.get('routine'),
            'products': scan.get('products'),
            'diet_recommendations': diet_recommendations,
            'progress_tracking_enabled': True,
            'created_at': scan['created_at'].isoformat() if isinstance(scan['created_at'], datetime) else scan['created_at']
        }
    else:
        # FREE USER (PRD Phase 3: Free Experience - Honest Curiosity)
        all_issues = analysis.get('issues', [])
        issue_count = len(all_issues)
        all_strengths = analysis.get('strengths', [])
        primary_concern = analysis.get('primary_concern', {})
        
        # PRD Phase 3: Free users get limited strengths (1-2 max)
        free_strengths = all_strengths[:2] if all_strengths else []
        
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
                # PRD Phase 3: Free users see strengths (builds trust)
                'strengths': free_strengths,
                # PRD Phase 3: Free users see PRIMARY concern only (drives curiosity)
                'primary_concern': {
                    'name': primary_concern.get('name', 'Skin concern detected'),
                    'why_this_result': primary_concern.get('why_this_result', 'Based on your skin analysis')
                },
                # Issue names visible, details locked
                'issue_count': issue_count,
                'issues_preview': issues_preview,
            },
            'locked_features': [
                'issue_details',
                'skin_metrics',
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

# ==================== PRD PHASE 2: ROUTINE PROGRESS TRACKING ====================

class RoutineStepUpdate(BaseModel):
    scan_id: str
    routine_type: str  # 'morning_routine', 'evening_routine', 'weekly_routine'
    step_order: int
    completed: bool

@api_router.post("/routine/complete-step")
async def complete_routine_step(
    request: RoutineStepUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    PRD Phase 2: Mark a routine step as completed and unlock the next step.
    Sequential locking: Step N+1 requires completing Step N.
    """
    # Only premium users can track routine progress
    if current_user.get('plan', 'free') != 'premium':
        raise HTTPException(
            status_code=403,
            detail="Routine progress tracking is a Premium feature"
        )
    
    # Find the scan
    scan = await db.scans.find_one({
        'id': request.scan_id,
        'user_id': current_user['id']
    })
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    routine = scan.get('routine', {})
    routine_steps = routine.get(request.routine_type, [])
    
    if not routine_steps:
        raise HTTPException(status_code=400, detail=f"No {request.routine_type} found")
    
    # Find the step
    step_index = None
    for idx, step in enumerate(routine_steps):
        if step.get('order') == request.step_order:
            step_index = idx
            break
    
    if step_index is None:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Check if step is locked (can't complete a locked step)
    if routine_steps[step_index].get('locked', False):
        raise HTTPException(
            status_code=400,
            detail="Cannot complete a locked step. Complete previous steps first."
        )
    
    # Update step completion
    routine_steps[step_index]['completed'] = request.completed
    
    # If completing a step, unlock the next step
    if request.completed and step_index + 1 < len(routine_steps):
        routine_steps[step_index + 1]['locked'] = False
    
    # If un-completing a step, re-lock all subsequent steps and mark them incomplete
    if not request.completed:
        for subsequent_idx in range(step_index + 1, len(routine_steps)):
            routine_steps[subsequent_idx]['locked'] = True
            routine_steps[subsequent_idx]['completed'] = False
    
    # Update the routine in database
    routine[request.routine_type] = routine_steps
    
    await db.scans.update_one(
        {'id': request.scan_id, 'user_id': current_user['id']},
        {'$set': {'routine': routine}}
    )
    
    # Calculate progress statistics
    total_steps = len(routine_steps)
    completed_steps = sum(1 for s in routine_steps if s.get('completed', False))
    progress_percent = round((completed_steps / total_steps) * 100) if total_steps > 0 else 0
    
    return {
        'success': True,
        'routine_type': request.routine_type,
        'step_order': request.step_order,
        'completed': request.completed,
        'progress': {
            'completed_steps': completed_steps,
            'total_steps': total_steps,
            'progress_percent': progress_percent
        },
        'next_step_unlocked': request.completed and step_index + 1 < len(routine_steps),
        'routine': routine_steps
    }

@api_router.get("/routine/progress/{scan_id}")
async def get_routine_progress(
    scan_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    PRD Phase 2: Get routine progress for a scan.
    Returns completion stats for morning, evening, and weekly routines.
    """
    if current_user.get('plan', 'free') != 'premium':
        raise HTTPException(
            status_code=403,
            detail="Routine progress tracking is a Premium feature"
        )
    
    scan = await db.scans.find_one({
        'id': scan_id,
        'user_id': current_user['id']
    })
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    routine = scan.get('routine', {})
    
    def calculate_progress(steps):
        if not steps:
            return {'completed': 0, 'total': 0, 'percent': 0}
        total = len(steps)
        completed = sum(1 for s in steps if s.get('completed', False))
        return {
            'completed': completed,
            'total': total,
            'percent': round((completed / total) * 100) if total > 0 else 0
        }
    
    return {
        'scan_id': scan_id,
        'morning_routine': {
            'progress': calculate_progress(routine.get('morning_routine', [])),
            'steps': routine.get('morning_routine', [])
        },
        'evening_routine': {
            'progress': calculate_progress(routine.get('evening_routine', [])),
            'steps': routine.get('evening_routine', [])
        },
        'weekly_routine': {
            'progress': calculate_progress(routine.get('weekly_routine', [])),
            'steps': routine.get('weekly_routine', [])
        },
        'overall_progress': {
            'morning': calculate_progress(routine.get('morning_routine', []))['percent'],
            'evening': calculate_progress(routine.get('evening_routine', []))['percent'],
            'weekly': calculate_progress(routine.get('weekly_routine', []))['percent']
        }
    }

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

# ==================== PRD PHASE 3: WEEKLY CHALLENGES ====================

# Challenge templates tied to skin issues and metrics
CHALLENGE_TEMPLATES = {
    # Hydration challenges
    'hydration': [
        {
            'id': 'water_8_glasses',
            'title': 'Hydration Hero',
            'description': 'Drink at least 8 glasses of water daily for 7 days',
            'why_this_challenge': 'Your hydration score shows room for improvement. Proper hydration plumps skin from within.',
            'duration_days': 7,
            'target_metric': 'hydration_appearance',
            'difficulty': 'easy',
            'daily_goal': '8 glasses of water',
            'tips': ['Set hourly reminders', 'Keep a water bottle with you', 'Track your intake'],
            'expected_impact': 'Improved skin plumpness and reduced fine lines'
        },
        {
            'id': 'hyaluronic_acid_week',
            'title': 'Moisture Lock Week',
            'description': 'Apply hyaluronic acid serum every day for 7 days',
            'why_this_challenge': 'Hyaluronic acid attracts and holds moisture, directly addressing your hydration needs.',
            'duration_days': 7,
            'target_metric': 'hydration_appearance',
            'difficulty': 'medium',
            'daily_goal': 'Apply HA serum to damp skin',
            'tips': ['Apply to slightly damp skin', 'Follow with moisturizer', 'Use morning and night'],
            'expected_impact': '15-20% improvement in hydration appearance'
        }
    ],
    # Texture challenges
    'texture': [
        {
            'id': 'gentle_exfoliation',
            'title': 'Smooth Skin Week',
            'description': 'Exfoliate 2-3 times this week with a gentle AHA/BHA',
            'why_this_challenge': 'Your texture score indicates dead skin buildup. Chemical exfoliation reveals smoother skin.',
            'duration_days': 7,
            'target_metric': 'texture_smoothness',
            'difficulty': 'medium',
            'daily_goal': 'Exfoliate on designated days (Mon, Wed, Fri)',
            'tips': ['Start with low concentration', 'Always use sunscreen after', 'Skip if irritation occurs'],
            'expected_impact': 'Smoother, more refined skin texture'
        },
        {
            'id': 'double_cleanse_week',
            'title': 'Deep Clean Challenge',
            'description': 'Double cleanse every evening for 7 days',
            'why_this_challenge': 'Proper cleansing removes debris that causes texture issues.',
            'duration_days': 7,
            'target_metric': 'texture_smoothness',
            'difficulty': 'easy',
            'daily_goal': 'Oil cleanser + water cleanser nightly',
            'tips': ['Oil first to remove makeup/SPF', 'Gentle water-based cleanser second', 'Be gentle, no harsh scrubbing'],
            'expected_impact': 'Clearer pores and smoother texture'
        }
    ],
    # Redness/sensitivity challenges
    'redness': [
        {
            'id': 'soothe_and_calm',
            'title': 'Calm Skin Challenge',
            'description': 'Use only calming products for 7 days - no actives',
            'why_this_challenge': 'Your redness indicates inflammation. A break from actives lets skin recover.',
            'duration_days': 7,
            'target_metric': 'redness_level',
            'difficulty': 'easy',
            'daily_goal': 'Cleanse, soothe, moisturize only',
            'tips': ['Look for centella, aloe, green tea', 'Avoid fragrance and alcohol', 'Skip retinol and acids'],
            'expected_impact': 'Reduced redness and calmer complexion'
        },
        {
            'id': 'ice_rolling',
            'title': 'Cool Down Week',
            'description': 'Use cold therapy on your face daily for 7 days',
            'why_this_challenge': 'Cold constricts blood vessels and reduces inflammation.',
            'duration_days': 7,
            'target_metric': 'redness_level',
            'difficulty': 'easy',
            'daily_goal': '2-3 minutes of ice rolling or cold compress',
            'tips': ['Use ice roller from freezer', 'Never apply ice directly', 'Do after cleansing, before serums'],
            'expected_impact': 'Reduced puffiness and redness'
        }
    ],
    # Pore challenges
    'pores': [
        {
            'id': 'niacinamide_week',
            'title': 'Pore Minimizing Week',
            'description': 'Apply niacinamide serum daily for 7 days',
            'why_this_challenge': 'Niacinamide regulates oil and visibly reduces pore appearance.',
            'duration_days': 7,
            'target_metric': 'pore_visibility',
            'difficulty': 'easy',
            'daily_goal': 'Apply 5% niacinamide serum twice daily',
            'tips': ['Can be layered with other products', 'Start with once daily if new', 'Pairs well with hyaluronic acid'],
            'expected_impact': 'Refined pore appearance and balanced oil'
        },
        {
            'id': 'clay_mask_week',
            'title': 'Deep Pore Cleanse',
            'description': 'Use a clay mask 2x this week on T-zone',
            'why_this_challenge': 'Clay draws out impurities and tightens pore appearance.',
            'duration_days': 7,
            'target_metric': 'pore_visibility',
            'difficulty': 'easy',
            'daily_goal': 'Clay mask on Tuesday and Saturday',
            'tips': ['Focus on T-zone', 'Remove before fully dry', 'Follow with hydrating toner'],
            'expected_impact': 'Cleaner, less visible pores'
        }
    ],
    # Tone/brightness challenges
    'tone': [
        {
            'id': 'vitamin_c_week',
            'title': 'Glow Up Challenge',
            'description': 'Use Vitamin C serum every morning for 7 days',
            'why_this_challenge': 'Your uneven tone will benefit from Vitamin C\'s brightening and antioxidant effects.',
            'duration_days': 7,
            'target_metric': 'tone_uniformity',
            'difficulty': 'medium',
            'daily_goal': 'Vitamin C serum in AM before sunscreen',
            'tips': ['Store in cool, dark place', 'Apply to clean, dry skin', 'Always follow with SPF'],
            'expected_impact': 'Brighter, more even skin tone'
        },
        {
            'id': 'spf_commitment',
            'title': 'Sun Shield Week',
            'description': 'Apply SPF 30+ every day, reapply if outdoors',
            'why_this_challenge': 'UV exposure worsens uneven tone. Consistent SPF prevents further damage.',
            'duration_days': 7,
            'target_metric': 'tone_uniformity',
            'difficulty': 'easy',
            'daily_goal': 'SPF every morning, reapply every 2 hours if outside',
            'tips': ['Apply as final skincare step', 'Don\'t forget ears and neck', 'Use 2 finger lengths of product'],
            'expected_impact': 'Prevention of further dark spots and tone issues'
        }
    ],
    # General/consistency challenges
    'consistency': [
        {
            'id': 'routine_streak',
            'title': '7-Day Streak',
            'description': 'Complete your full morning AND evening routine for 7 consecutive days',
            'why_this_challenge': 'Consistency is key to seeing results. Build the habit this week.',
            'duration_days': 7,
            'target_metric': 'overall',
            'difficulty': 'medium',
            'daily_goal': 'Complete both AM and PM routines',
            'tips': ['Set reminders', 'Prep products the night before', 'Track your completions'],
            'expected_impact': 'Establishes habits for long-term skin health'
        },
        {
            'id': 'sleep_challenge',
            'title': 'Beauty Sleep Week',
            'description': 'Get 7-8 hours of sleep every night for 7 days',
            'why_this_challenge': 'Skin repairs during sleep. Insufficient rest affects all skin metrics.',
            'duration_days': 7,
            'target_metric': 'overall',
            'difficulty': 'medium',
            'daily_goal': '7-8 hours of quality sleep',
            'tips': ['Set a consistent bedtime', 'Avoid screens 1 hour before bed', 'Keep room cool and dark'],
            'expected_impact': 'Better skin recovery and reduced dark circles'
        }
    ]
}

def generate_weekly_challenges(analysis: dict, user_id: str) -> List[dict]:
    """
    PRD Phase 3: Generate personalized weekly challenges based on skin analysis.
    
    Challenges are:
    1. Tied to detected issues and low-scoring metrics
    2. Realistic and achievable
    3. Specific to user's skin type
    """
    challenges = []
    skin_metrics = analysis.get('skin_metrics', {})
    issues = analysis.get('issues', [])
    primary_concern = analysis.get('primary_concern', {})
    
    # Find metrics needing improvement (score < 75)
    low_metrics = []
    for metric_name, metric_data in skin_metrics.items():
        if isinstance(metric_data, dict):
            score = metric_data.get('score', 70)
            if score < 75:
                low_metrics.append({
                    'name': metric_name,
                    'score': score,
                    'priority': 1 if score < 60 else 2
                })
    
    # Sort by priority (lowest scores first)
    low_metrics.sort(key=lambda x: x['score'])
    
    # Map metrics to challenge categories
    metric_to_category = {
        'hydration_appearance': 'hydration',
        'texture_smoothness': 'texture',
        'redness_level': 'redness',
        'pore_visibility': 'pores',
        'tone_uniformity': 'tone'
    }
    
    # Generate challenges for lowest 2 metrics
    used_categories = set()
    for metric in low_metrics[:2]:
        category = metric_to_category.get(metric['name'])
        if category and category not in used_categories:
            category_challenges = CHALLENGE_TEMPLATES.get(category, [])
            if category_challenges:
                # Pick first challenge from category
                challenge = category_challenges[0].copy()
                challenge['assigned_for_metric'] = metric['name']
                challenge['current_metric_score'] = metric['score']
                challenge['start_date'] = datetime.utcnow().isoformat()
                challenge['end_date'] = (datetime.utcnow() + timedelta(days=challenge['duration_days'])).isoformat()
                challenge['progress'] = {
                    'days_completed': 0,
                    'total_days': challenge['duration_days'],
                    'is_active': True
                }
                challenges.append(challenge)
                used_categories.add(category)
    
    # Always add a consistency challenge if we have less than 2
    if len(challenges) < 2:
        consistency_challenges = CHALLENGE_TEMPLATES.get('consistency', [])
        if consistency_challenges:
            challenge = consistency_challenges[0].copy()
            challenge['assigned_for_metric'] = 'overall'
            challenge['current_metric_score'] = None
            challenge['start_date'] = datetime.utcnow().isoformat()
            challenge['end_date'] = (datetime.utcnow() + timedelta(days=challenge['duration_days'])).isoformat()
            challenge['progress'] = {
                'days_completed': 0,
                'total_days': challenge['duration_days'],
                'is_active': True
            }
            challenges.append(challenge)
    
    return challenges[:3]  # Max 3 challenges at a time

class ChallengeProgressUpdate(BaseModel):
    challenge_id: str
    day_completed: bool

@api_router.get("/challenges/current")
async def get_current_challenges(current_user: dict = Depends(get_current_user)):
    """
    PRD Phase 3: Get user's current weekly challenges.
    Generates new challenges based on latest scan if none exist.
    """
    if current_user.get('plan', 'free') != 'premium':
        return {
            'locked': True,
            'message': 'Weekly challenges are a Premium feature',
            'preview': {
                'challenge_count': 3,
                'sample_titles': ['Hydration Hero', 'Smooth Skin Week', '7-Day Streak']
            }
        }
    
    user_id = current_user['id']
    
    # Check for existing active challenges
    active_challenges = await db.challenges.find_one({
        'user_id': user_id,
        'is_active': True
    })
    
    if active_challenges:
        return {
            'locked': False,
            'challenges': active_challenges.get('challenges', []),
            'week_start': active_challenges.get('week_start'),
            'week_end': active_challenges.get('week_end')
        }
    
    # Generate new challenges from latest scan
    latest_scan = await db.scans.find_one(
        {'user_id': user_id},
        sort=[('created_at', -1)]
    )
    
    if not latest_scan:
        return {
            'locked': False,
            'challenges': [],
            'message': 'Complete a skin scan to get personalized challenges'
        }
    
    # Generate challenges
    analysis = latest_scan.get('analysis', {})
    challenges = generate_weekly_challenges(analysis, user_id)
    
    # Save challenges
    week_start = datetime.utcnow()
    week_end = week_start + timedelta(days=7)
    
    await db.challenges.insert_one({
        'user_id': user_id,
        'challenges': challenges,
        'is_active': True,
        'week_start': week_start,
        'week_end': week_end,
        'scan_id': latest_scan.get('id'),
        'created_at': datetime.utcnow()
    })
    
    return {
        'locked': False,
        'challenges': challenges,
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat()
    }

@api_router.post("/challenges/progress")
async def update_challenge_progress(
    request: ChallengeProgressUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    PRD Phase 3: Update progress on a weekly challenge.
    """
    if current_user.get('plan', 'free') != 'premium':
        raise HTTPException(status_code=403, detail="Premium feature")
    
    user_id = current_user['id']
    
    # Find active challenges
    active = await db.challenges.find_one({
        'user_id': user_id,
        'is_active': True
    })
    
    if not active:
        raise HTTPException(status_code=404, detail="No active challenges found")
    
    challenges = active.get('challenges', [])
    challenge_found = False
    
    for challenge in challenges:
        if challenge.get('id') == request.challenge_id:
            challenge_found = True
            progress = challenge.get('progress', {})
            
            if request.day_completed:
                progress['days_completed'] = min(
                    progress.get('days_completed', 0) + 1,
                    progress.get('total_days', 7)
                )
            
            # Check if challenge is complete
            if progress['days_completed'] >= progress['total_days']:
                progress['is_active'] = False
                challenge['completed'] = True
                challenge['completed_at'] = datetime.utcnow().isoformat()
            
            challenge['progress'] = progress
            break
    
    if not challenge_found:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Update in database
    await db.challenges.update_one(
        {'_id': active['_id']},
        {'$set': {'challenges': challenges}}
    )
    
    return {
        'success': True,
        'challenge_id': request.challenge_id,
        'challenges': challenges
    }

@api_router.post("/challenges/refresh")
async def refresh_challenges(current_user: dict = Depends(get_current_user)):
    """
    PRD Phase 3: Generate new weekly challenges (e.g., at start of new week).
    Deactivates old challenges and creates new ones.
    """
    if current_user.get('plan', 'free') != 'premium':
        raise HTTPException(status_code=403, detail="Premium feature")
    
    user_id = current_user['id']
    
    # Deactivate old challenges
    await db.challenges.update_many(
        {'user_id': user_id, 'is_active': True},
        {'$set': {'is_active': False}}
    )
    
    # Get latest scan
    latest_scan = await db.scans.find_one(
        {'user_id': user_id},
        sort=[('created_at', -1)]
    )
    
    if not latest_scan:
        return {
            'success': True,
            'challenges': [],
            'message': 'No scan found. Complete a scan to get challenges.'
        }
    
    # Generate new challenges
    analysis = latest_scan.get('analysis', {})
    challenges = generate_weekly_challenges(analysis, user_id)
    
    week_start = datetime.utcnow()
    week_end = week_start + timedelta(days=7)
    
    await db.challenges.insert_one({
        'user_id': user_id,
        'challenges': challenges,
        'is_active': True,
        'week_start': week_start,
        'week_end': week_end,
        'scan_id': latest_scan.get('id'),
        'created_at': datetime.utcnow()
    })
    
    return {
        'success': True,
        'challenges': challenges,
        'week_start': week_start.isoformat(),
        'week_end': week_end.isoformat()
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
