# SkinAdvisor AI - App Store Submission Guide

## App Information

### Basic Details
- **App Name**: SkinAdvisor AI
- **Subtitle**: AI-Powered Skin Analysis
- **Bundle ID (iOS)**: com.skinadvisor.ai
- **Package Name (Android)**: com.skinadvisor.ai
- **Version**: 1.0.0
- **Build Number**: 1

---

## App Store Connect (iOS) Metadata

### App Description (4000 characters max)
```
SkinAdvisor AI is your personal AI-powered dermatologist in your pocket. Get instant, professional-grade skin analysis using advanced artificial intelligence technology.

🔍 INSTANT SKIN ANALYSIS
Simply take a photo of your face, and our AI will analyze your skin in seconds. Get detailed insights about:
• Skin type (oily, dry, combination, normal, sensitive)
• Detected skin issues (acne, wrinkles, dark spots, redness)
• Personalized skin health score

💊 PERSONALIZED SKINCARE ROUTINE
Receive a customized daily skincare routine tailored to your specific skin needs:
• Morning and evening routines
• Product recommendations
• Step-by-step instructions

🥗 DIET & NUTRITION GUIDANCE
Discover how your diet affects your skin:
• Foods to eat for better skin
• Foods to avoid
• Supplement recommendations

📈 TRACK YOUR PROGRESS
Monitor your skin improvement over time:
• Before & after comparisons
• Score history
• Streak rewards for consistency

🌍 MULTI-LANGUAGE SUPPORT
Available in 9 languages: English, French, Turkish, Italian, Spanish, German, Arabic, Chinese, and Hindi.

PREMIUM FEATURES:
• Unlimited skin scans
• Complete skincare routines
• Detailed diet plans
• Product recommendations
• Progress tracking with photos

Start your journey to healthier, clearer skin today with SkinAdvisor AI!

Note: This app provides general skincare guidance and is not a substitute for professional medical advice. Always consult a dermatologist for serious skin concerns.
```

### Keywords (100 characters max)
```
skin,skincare,acne,dermatology,beauty,face,analysis,AI,routine,health,glow,pores,wrinkles,care
```

### Promotional Text (170 characters max)
```
Get AI-powered skin analysis instantly! Personalized skincare routines, diet tips, and progress tracking. Start your journey to healthier skin today.
```

### What's New (Version 1.0.0)
```
Welcome to SkinAdvisor AI! 

• AI-powered skin analysis
• Personalized skincare routines
• Diet & nutrition recommendations
• Progress tracking
• Multi-language support (9 languages)
• Premium subscription for unlimited access
```

---

## Google Play Store Metadata

### Short Description (80 characters max)
```
AI skin analysis, personalized routines & diet tips for healthier, clearer skin
```

### Full Description (4000 characters max)
```
[Same as iOS App Description above]
```

---

## Screenshots Requirements

### iOS Screenshots (Required Sizes)
1. **iPhone 6.7" (1290 x 2796 px)** - iPhone 15 Pro Max
2. **iPhone 6.5" (1284 x 2778 px)** - iPhone 14 Plus
3. **iPhone 5.5" (1242 x 2208 px)** - iPhone 8 Plus
4. **iPad Pro 12.9" (2048 x 2732 px)** - If supporting tablets

### Android Screenshots (Required)
1. **Phone** (min 320px, max 3840px)
2. **7-inch tablet** (optional)
3. **10-inch tablet** (optional)

### Suggested Screenshot Content
1. **Onboarding/Welcome Screen** - Show the app introduction
2. **Scan Screen** - Camera interface for skin scanning
3. **Results Screen** - Show skin analysis with score
4. **Routine Screen** - Daily skincare routine
5. **Progress Screen** - Before/after comparison
6. **Paywall Screen** - Premium features overview

---

## App Privacy

### Data Collection
- **Email Address**: Used for account creation
- **Photos**: Used for skin analysis (processed on device and server)
- **Usage Data**: Analytics for app improvement

### Privacy Policy URL
https://skinadvisor.ai/privacy

### Terms of Service URL
https://skinadvisor.ai/terms

---

## In-App Purchases

### Subscription Products

| Product ID | Name | Price | Duration |
|------------|------|-------|----------|
| monthly | Monthly Premium | $9.99 | 1 month |
| yearly | Yearly Premium | $59.99 | 1 year |
| lifetime | Lifetime Premium | $99.99 | Forever |

### Subscription Description
```
SkinAdvisor AI Premium unlocks:
• Unlimited skin scans
• Complete daily skincare routines
• Personalized diet & nutrition plans
• Product recommendations
• Progress tracking with photos
• Priority support

Payment will be charged to your Apple ID/Google Play account at confirmation of purchase. Subscription automatically renews unless auto-renew is turned off at least 24 hours before the end of the current period. Your account will be charged for renewal within 24 hours prior to the end of the current period. You can manage and cancel your subscriptions by going to your account settings on the App Store/Google Play after purchase.
```

---

## App Review Information

### Demo Account
- **Email**: demo@skinadvisor.ai
- **Password**: Demo123!

### Review Notes
```
SkinAdvisor AI uses artificial intelligence to analyze skin from photos. The app requires camera/photo library access to function.

To test the app:
1. Create an account or use the demo account above
2. Take a photo of any face (or upload one)
3. View the skin analysis results
4. Explore the skincare routine recommendations

Note: The AI analysis is for cosmetic/informational purposes only and includes a medical disclaimer.
```

### Contact Information
- **First Name**: [Your First Name]
- **Last Name**: [Your Last Name]
- **Phone**: [Your Phone Number]
- **Email**: [Your Email]

---

## Age Rating

### iOS Content Descriptions
- No objectionable content
- No gambling
- No horror/fear themes
- No mature/suggestive themes
- No profanity
- No drugs/alcohol/tobacco
- No violence
- Medical/Treatment Information: **Yes** (informational only)

**Recommended Rating**: 4+ (All Ages)

### Android Content Rating
- **ESRB**: Everyone
- **PEGI**: 3
- Complete the content rating questionnaire in Google Play Console

---

## Submission Checklist

### Before Submitting
- [ ] App icon (1024x1024 for iOS, 512x512 for Android)
- [ ] Screenshots for all required device sizes
- [ ] Privacy Policy URL is live and accessible
- [ ] Terms of Service URL is live and accessible
- [ ] Test all in-app purchase flows
- [ ] Verify "Restore Purchases" button works
- [ ] Test on multiple device sizes
- [ ] Review medical disclaimer is visible

### iOS Specific
- [ ] Configure App Store Connect API key in RevenueCat
- [ ] Create in-app purchases in App Store Connect
- [ ] Set up subscription group
- [ ] Submit for App Review

### Android Specific
- [ ] Upload Google Play Service Account JSON to RevenueCat
- [ ] Create subscriptions in Google Play Console
- [ ] Complete Data Safety form
- [ ] Complete Content Rating questionnaire
- [ ] Submit for review

---

## Build Commands

### Development Build
```bash
eas build --platform all --profile development
```

### Preview Build (Internal Testing)
```bash
eas build --platform all --profile preview
```

### Production Build
```bash
eas build --platform all --profile production
```

### Submit to Stores
```bash
# iOS
eas submit --platform ios --profile production

# Android
eas submit --platform android --profile production
```

---

## Support URLs

- **Support Email**: support@skinadvisor.ai
- **Website**: https://skinadvisor.ai
- **Privacy Policy**: https://skinadvisor.ai/privacy
- **Terms of Service**: https://skinadvisor.ai/terms
