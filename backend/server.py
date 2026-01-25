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

@api_router.delete("/account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    # Delete all user's scans
    await db.scans.delete_many({'user_id': current_user['id']})
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

async def analyze_skin_with_ai(image_base64: str, language: str = 'en') -> dict:
    """Analyze skin using OpenAI GPT-4o vision"""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    
    system_prompt = f"""You are an expert dermatology AI assistant specialized in cosmetic skin analysis. 
You analyze facial skin photos to identify skin type and common cosmetic concerns.

IMPORTANT DISCLAIMER: This is for cosmetic guidance only, NOT medical diagnosis.

Respond in {lang_name} language.

Analyze the provided facial image and return a JSON response with this exact structure:
{{
    "skin_type": "oily" | "dry" | "combination" | "normal" | "sensitive",
    "skin_type_description": "Brief explanation of the skin type in {lang_name}",
    "issues": [
        {{
            "name": "Issue name (e.g., acne, dark spots, wrinkles, redness, large pores, dehydration, uneven tone)",
            "severity": 1-10,
            "description": "Brief description in {lang_name}"
        }}
    ],
    "overall_score": 1-100 (100 being perfect skin health),
    "recommendations": ["List of 3-5 general skincare recommendations in {lang_name}"]
}}

Only return the JSON, no additional text."""
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"skin-analysis-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o")
        
        image_content = ImageContent(image_base64=image_base64)
        
        user_message = UserMessage(
            text="Please analyze this facial skin image and provide the skin analysis in JSON format.",
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        
        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            raise ValueError("Could not parse AI response")
            
    except Exception as e:
        logger.error(f"AI analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

async def generate_routine_with_ai(analysis: dict, language: str = 'en') -> dict:
    """Generate skincare routine based on analysis"""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    lang_name = LANGUAGE_PROMPTS.get(language, 'English')
    
    system_prompt = f"""You are an expert skincare routine advisor. Based on skin analysis results, 
you create personalized skincare routines with specific product recommendations.

Respond in {lang_name} language.

Create a comprehensive skincare routine and return a JSON response with this exact structure:
{{
    "morning_routine": [
        {{
            "order": 1,
            "step_name": "Step name in {lang_name}",
            "product_type": "cleanser" | "toner" | "serum" | "moisturizer" | "sunscreen" | "treatment",
            "instructions": "How to apply in {lang_name}",
            "ingredients_to_look_for": ["list of beneficial ingredients"],
            "ingredients_to_avoid": ["list of ingredients to avoid"]
        }}
    ],
    "evening_routine": [...],
    "weekly_routine": [...],
    "products": [
        {{
            "product_type": "cleanser" | "toner" | "serum" | "moisturizer" | "sunscreen" | "treatment",
            "name": "Generic product name",
            "description": "Why this product type is recommended in {lang_name}",
            "key_ingredients": ["main ingredients"],
            "suitable_for": ["skin types this is good for"],
            "price_range": "$" | "$$" | "$$$"
        }}
    ]
}}

Only return the JSON, no additional text."""
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"routine-gen-{uuid.uuid4()}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o")
        
        user_message = UserMessage(
            text=f"""Based on this skin analysis, create a personalized skincare routine:

Skin Type: {analysis.get('skin_type', 'unknown')}
Issues: {json.dumps(analysis.get('issues', []))}
Overall Score: {analysis.get('overall_score', 50)}

Please provide morning, evening, and weekly routines with product recommendations."""
        )
        
        response = await chat.send_message(user_message)
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            raise ValueError("Could not parse AI response")
            
    except Exception as e:
        logger.error(f"Routine generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Routine generation failed: {str(e)}")

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
        'home': 'Home'
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
        'acne': 'Acné',
        'dark_spots': 'Taches sombres',
        'wrinkles': 'Rides',
        'redness': 'Rougeurs',
        'large_pores': 'Pores dilatés',
        'dehydration': 'Déshydratation',
        'uneven_tone': 'Teint inégal',
        'onboarding_1_title': 'Analyse de peau par IA',
        'onboarding_1_desc': 'Obtenez une analyse personnalisée instantanée grâce à la technologie IA avancée',
        'onboarding_2_title': 'Routines personnalisées',
        'onboarding_2_desc': 'Recevez des routines de soins personnalisées matin et soir',
        'onboarding_3_title': 'Suivez vos progrès',
        'onboarding_3_desc': 'Surveillez votre santé cutanée au fil du temps',
        'get_started': 'Commencer',
        'next': 'Suivant',
        'skip': 'Passer',
        'age': 'Âge',
        'gender': 'Genre',
        'skin_goals': 'Objectifs de peau',
        'country': 'Pays',
        'save': 'Enregistrer',
        'home': 'Accueil'
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
        'morning_routine': 'Sabah Rutini',
        'evening_routine': 'Akşam Rutini',
        'weekly_routine': 'Haftalık Rutin',
        'skin_type': 'Cilt Tipi',
        'skin_issues': 'Cilt Sorunları',
        'overall_score': 'Genel Skor',
        'recommendations': 'Öneriler',
        'products': 'Ürünler',
        'take_photo': 'Fotoğraf Çek',
        'upload_photo': 'Fotoğraf Yükle',
        'analyzing': 'Cildiniz analiz ediliyor...',
        'analysis_complete': 'Analiz Tamamlandı',
        'view_results': 'Sonuçları Görüntüle',
        'disclaimer': 'Bu analiz yalnızca kozmetik rehberlik amaçlıdır ve tıbbi bir tanı değildir.',
        'language': 'Dil',
        'dark_mode': 'Karanlık Mod',
        'delete_account': 'Hesabı Sil',
        'confirm_delete': 'Hesabınızı silmek istediğinizden emin misiniz?',
        'cancel': 'İptal',
        'confirm': 'Onayla',
        'error': 'Hata',
        'success': 'Başarılı',
        'loading': 'Yükleniyor...',
        'no_scans': 'Henüz tarama yok',
        'start_first_scan': 'İlk cilt taramanızı başlatın',
        'oily': 'Yağlı',
        'dry': 'Kuru',
        'combination': 'Karma',
        'normal': 'Normal',
        'sensitive': 'Hassas',
        'acne': 'Akne',
        'dark_spots': 'Koyu Lekeler',
        'wrinkles': 'Kırışıklıklar',
        'redness': 'Kızarıklık',
        'large_pores': 'Geniş Gözenekler',
        'dehydration': 'Dehidrasyon',
        'uneven_tone': 'Düzensiz Ton',
        'onboarding_1_title': 'AI Destekli Cilt Analizi',
        'onboarding_1_desc': 'Gelişmiş AI teknolojisi ile anında kişiselleştirilmiş cilt analizi alın',
        'onboarding_2_title': 'Kişiselleştirilmiş Rutinler',
        'onboarding_2_desc': 'Özelleştirilmiş sabah ve akşam cilt bakım rutinleri alın',
        'onboarding_3_title': 'İlerlemenizi Takip Edin',
        'onboarding_3_desc': 'Cilt sağlığı yolculuğunuzu zaman içinde izleyin',
        'get_started': 'Başla',
        'next': 'İleri',
        'skip': 'Atla',
        'age': 'Yaş',
        'gender': 'Cinsiyet',
        'skin_goals': 'Cilt Hedefleri',
        'country': 'Ülke',
        'save': 'Kaydet',
        'home': 'Ana Sayfa'
    },
    'it': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Benvenuto',
        'login': 'Accedi',
        'register': 'Registrati',
        'email': 'Email',
        'password': 'Password',
        'name': 'Nome',
        'scan_skin': 'Scansiona la tua pelle',
        'my_routines': 'Le mie routine',
        'progress': 'Progressi',
        'profile': 'Profilo',
        'settings': 'Impostazioni',
        'logout': 'Esci',
        'morning_routine': 'Routine mattutina',
        'evening_routine': 'Routine serale',
        'weekly_routine': 'Routine settimanale',
        'skin_type': 'Tipo di pelle',
        'skin_issues': 'Problemi della pelle',
        'overall_score': 'Punteggio generale',
        'recommendations': 'Raccomandazioni',
        'products': 'Prodotti',
        'take_photo': 'Scatta foto',
        'upload_photo': 'Carica foto',
        'analyzing': 'Analisi della pelle in corso...',
        'analysis_complete': 'Analisi completata',
        'view_results': 'Visualizza risultati',
        'disclaimer': 'Questa analisi è solo per orientamento cosmetico e non è una diagnosi medica.',
        'language': 'Lingua',
        'dark_mode': 'Modalità scura',
        'delete_account': 'Elimina account',
        'confirm_delete': 'Sei sicuro di voler eliminare il tuo account?',
        'cancel': 'Annulla',
        'confirm': 'Conferma',
        'error': 'Errore',
        'success': 'Successo',
        'loading': 'Caricamento...',
        'no_scans': 'Nessuna scansione ancora',
        'start_first_scan': 'Inizia la tua prima scansione della pelle',
        'oily': 'Grassa',
        'dry': 'Secca',
        'combination': 'Mista',
        'normal': 'Normale',
        'sensitive': 'Sensibile',
        'home': 'Home'
    },
    'es': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Bienvenido',
        'login': 'Iniciar sesión',
        'register': 'Registrarse',
        'email': 'Correo electrónico',
        'password': 'Contraseña',
        'name': 'Nombre',
        'scan_skin': 'Escanea tu piel',
        'my_routines': 'Mis rutinas',
        'progress': 'Progreso',
        'profile': 'Perfil',
        'settings': 'Configuración',
        'logout': 'Cerrar sesión',
        'morning_routine': 'Rutina matutina',
        'evening_routine': 'Rutina nocturna',
        'weekly_routine': 'Rutina semanal',
        'skin_type': 'Tipo de piel',
        'skin_issues': 'Problemas de piel',
        'overall_score': 'Puntuación general',
        'recommendations': 'Recomendaciones',
        'products': 'Productos',
        'take_photo': 'Tomar foto',
        'upload_photo': 'Subir foto',
        'analyzing': 'Analizando tu piel...',
        'analysis_complete': 'Análisis completado',
        'view_results': 'Ver resultados',
        'disclaimer': 'Este análisis es solo para orientación cosmética y no es un diagnóstico médico.',
        'language': 'Idioma',
        'dark_mode': 'Modo oscuro',
        'delete_account': 'Eliminar cuenta',
        'home': 'Inicio'
    },
    'de': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'Willkommen',
        'login': 'Anmelden',
        'register': 'Registrieren',
        'email': 'E-Mail',
        'password': 'Passwort',
        'name': 'Name',
        'scan_skin': 'Haut scannen',
        'my_routines': 'Meine Routinen',
        'progress': 'Fortschritt',
        'profile': 'Profil',
        'settings': 'Einstellungen',
        'logout': 'Abmelden',
        'morning_routine': 'Morgenroutine',
        'evening_routine': 'Abendroutine',
        'weekly_routine': 'Wöchentliche Routine',
        'skin_type': 'Hauttyp',
        'skin_issues': 'Hautprobleme',
        'overall_score': 'Gesamtpunktzahl',
        'recommendations': 'Empfehlungen',
        'products': 'Produkte',
        'take_photo': 'Foto aufnehmen',
        'upload_photo': 'Foto hochladen',
        'analyzing': 'Analyse Ihrer Haut...',
        'analysis_complete': 'Analyse abgeschlossen',
        'view_results': 'Ergebnisse anzeigen',
        'disclaimer': 'Diese Analyse dient nur der kosmetischen Beratung und ist keine medizinische Diagnose.',
        'language': 'Sprache',
        'dark_mode': 'Dunkelmodus',
        'delete_account': 'Konto löschen',
        'home': 'Startseite'
    },
    'ar': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'مرحباً',
        'login': 'تسجيل الدخول',
        'register': 'إنشاء حساب',
        'email': 'البريد الإلكتروني',
        'password': 'كلمة المرور',
        'name': 'الاسم',
        'scan_skin': 'فحص بشرتك',
        'my_routines': 'روتيني',
        'progress': 'التقدم',
        'profile': 'الملف الشخصي',
        'settings': 'الإعدادات',
        'logout': 'تسجيل الخروج',
        'morning_routine': 'روتين الصباح',
        'evening_routine': 'روتين المساء',
        'weekly_routine': 'روتين أسبوعي',
        'skin_type': 'نوع البشرة',
        'skin_issues': 'مشاكل البشرة',
        'overall_score': 'النتيجة الإجمالية',
        'recommendations': 'التوصيات',
        'products': 'المنتجات',
        'take_photo': 'التقط صورة',
        'upload_photo': 'تحميل صورة',
        'analyzing': 'جاري تحليل بشرتك...',
        'analysis_complete': 'اكتمل التحليل',
        'view_results': 'عرض النتائج',
        'disclaimer': 'هذا التحليل للإرشاد التجميلي فقط وليس تشخيصاً طبياً.',
        'language': 'اللغة',
        'dark_mode': 'الوضع الداكن',
        'delete_account': 'حذف الحساب',
        'home': 'الرئيسية'
    },
    'zh': {
        'app_name': 'SkinAdvisor AI',
        'welcome': '欢迎',
        'login': '登录',
        'register': '注册',
        'email': '电子邮件',
        'password': '密码',
        'name': '姓名',
        'scan_skin': '扫描您的皮肤',
        'my_routines': '我的护肤程序',
        'progress': '进度',
        'profile': '个人资料',
        'settings': '设置',
        'logout': '退出登录',
        'morning_routine': '早间护肤',
        'evening_routine': '晚间护肤',
        'weekly_routine': '每周护理',
        'skin_type': '皮肤类型',
        'skin_issues': '皮肤问题',
        'overall_score': '综合评分',
        'recommendations': '建议',
        'products': '产品',
        'take_photo': '拍照',
        'upload_photo': '上传照片',
        'analyzing': '正在分析您的皮肤...',
        'analysis_complete': '分析完成',
        'view_results': '查看结果',
        'disclaimer': '此分析仅供美容指导，不构成医学诊断。',
        'language': '语言',
        'dark_mode': '深色模式',
        'delete_account': '删除账户',
        'home': '首页'
    },
    'hi': {
        'app_name': 'SkinAdvisor AI',
        'welcome': 'स्वागत है',
        'login': 'लॉग इन करें',
        'register': 'रजिस्टर करें',
        'email': 'ईमेल',
        'password': 'पासवर्ड',
        'name': 'नाम',
        'scan_skin': 'अपनी त्वचा स्कैन करें',
        'my_routines': 'मेरी दिनचर्या',
        'progress': 'प्रगति',
        'profile': 'प्रोफ़ाइल',
        'settings': 'सेटिंग्स',
        'logout': 'लॉग आउट',
        'morning_routine': 'सुबह की दिनचर्या',
        'evening_routine': 'शाम की दिनचर्या',
        'weekly_routine': 'साप्ताहिक दिनचर्या',
        'skin_type': 'त्वचा का प्रकार',
        'skin_issues': 'त्वचा की समस्याएं',
        'overall_score': 'कुल स्कोर',
        'recommendations': 'सिफारिशें',
        'products': 'उत्पाद',
        'take_photo': 'फोटो लें',
        'upload_photo': 'फोटो अपलोड करें',
        'analyzing': 'आपकी त्वचा का विश्लेषण हो रहा है...',
        'analysis_complete': 'विश्लेषण पूर्ण',
        'view_results': 'परिणाम देखें',
        'disclaimer': 'यह विश्लेषण केवल कॉस्मेटिक मार्गदर्शन के लिए है और यह चिकित्सा निदान नहीं है।',
        'language': 'भाषा',
        'dark_mode': 'डार्क मोड',
        'delete_account': 'खाता हटाएं',
        'home': 'होम'
    }
}

@api_router.get("/translations/{language}")
async def get_translations(language: str):
    """Get translations for a specific language"""
    if language not in BASE_TRANSLATIONS:
        language = 'en'
    return BASE_TRANSLATIONS.get(language, BASE_TRANSLATIONS['en'])

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
