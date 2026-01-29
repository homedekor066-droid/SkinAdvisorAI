# SkinAdvisor AI - Social Login Setup Guide

## Current Status
- ✅ Email/Password Login & Registration - WORKING
- ✅ Apple Sign-In - READY (works on iOS 13+ devices after build)
- ⚠️ Google Sign-In - NEEDS iOS CLIENT ID SETUP

---

## Part 1: Google Sign-In Setup (REQUIRED)

Your current Google Client ID is a **Web Client ID**. For iOS apps, you ALSO need an **iOS Client ID**.

### Steps to Create iOS Client ID:

1. **Go to Google Cloud Console**
   - https://console.cloud.google.com/apis/credentials
   - Select your project (or the one with ID: 993166704619)

2. **Create iOS OAuth Client**
   - Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
   - Application type: **iOS**
   - Name: `SkinAdvisor AI iOS`
   - Bundle ID: `com.skinadvisor.ai`
   - Click **Create**

3. **Copy the iOS Client ID**
   - It will look like: `993166704619-XXXXXXXXXX.apps.googleusercontent.com`
   - Save this ID!

4. **Update the App**
   - Open `/app/frontend/src/services/socialAuthService.ts`
   - Find line: `const GOOGLE_IOS_CLIENT_ID = '';`
   - Replace with: `const GOOGLE_IOS_CLIENT_ID = 'YOUR_NEW_IOS_CLIENT_ID';`

---

## Part 2: Apple Sign-In Setup

Apple Sign-In is already configured. It will work automatically on iOS 13+ devices.

**Requirements:**
- ✅ Apple Developer Account - You have this
- ✅ Apple Key (RC2WDHNB9D) - Already uploaded
- ✅ `usesAppleSignIn: true` in app.json - Already set
- ✅ `expo-apple-authentication` plugin - Already added

**Note:** Apple Sign-In only works on REAL iOS devices (not simulators or web).

---

## Part 3: Build & Deploy to iOS (TestFlight)

### Prerequisites
- Node.js installed on your computer
- EAS CLI: `npm install -g eas-cli`

### Step-by-Step Commands:

```bash
# 1. Open Terminal/Command Prompt and navigate to your project folder
cd path/to/your/frontend/folder

# 2. Login to Expo (use your Expo account)
eas login

# 3. Check your project is linked
eas project:info

# 4. Build for iOS
eas build --platform ios --profile production

# 5. Wait for build to complete (10-20 minutes)
# You'll get a URL to download the .ipa file

# 6. Submit to App Store Connect
eas submit --platform ios

# 7. Follow the prompts:
#    - Choose the build you just created
#    - Enter your Apple ID
#    - Enter app-specific password (create at appleid.apple.com)
```

### After Submission:
1. Go to **App Store Connect** (appstoreconnect.apple.com)
2. Select your app "SkinAdvisor AI"
3. Go to **TestFlight** tab
4. Wait for Apple to process (usually 15-30 minutes)
5. Add testers and distribute!

---

## Part 4: Build & Deploy to Android (Play Store)

### Step-by-Step Commands:

```bash
# 1. Build for Android
eas build --platform android --profile production

# 2. Wait for build to complete
# You'll get a URL to download the .aab file

# 3. Submit to Play Store
eas submit --platform android

# Or manually:
# - Go to play.google.com/console
# - Select your app
# - Go to "Production" or "Internal testing"
# - Click "Create new release"
# - Upload the .aab file
```

---

## Important Files to Update Before Building

### 1. app.json - Update these:
```json
{
  "expo": {
    "ios": {
      "buildNumber": "2"  // Increment for each new build
    },
    "android": {
      "versionCode": 2  // Increment for each new build
    },
    "extra": {
      "eas": {
        "projectId": "YOUR_EAS_PROJECT_ID"  // From eas init
      }
    }
  }
}
```

### 2. eas.json - Should look like:
```json
{
  "cli": {
    "version": ">= 3.0.0"
  },
  "build": {
    "production": {
      "node": "18.18.0",
      "distribution": "store",
      "ios": {
        "resourceClass": "m-medium"
      }
    }
  },
  "submit": {
    "production": {}
  }
}
```

---

## Troubleshooting

### "Email already registered" error
- This is CORRECT behavior - the email is already used
- Try a different email address

### Google Sign-In "Access Blocked" error
- You need to create an iOS Client ID (see Part 1)
- The web client ID doesn't work on iOS native apps

### Apple Sign-In not showing
- Only works on iOS 13+ real devices
- Won't work on simulators or web preview

### Build fails with version error
- Increment `buildNumber` in app.json
- Make sure no `autoIncrement` in eas.json

---

## Quick Reference Commands

```bash
# Check Expo login
eas whoami

# Build iOS
eas build --platform ios

# Build Android
eas build --platform android

# Submit iOS
eas submit --platform ios

# Submit Android
eas submit --platform android

# View build status
eas build:list
```
