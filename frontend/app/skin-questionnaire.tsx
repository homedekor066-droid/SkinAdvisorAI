import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Dimensions,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../src/context/ThemeContext';
import { useI18n } from '../src/context/I18nContext';
import { useAuth } from '../src/context/AuthContext';
import { Button } from '../src/components';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';

const { width } = Dimensions.get('window');

// Legal URLs
const PRIVACY_POLICY_URL = 'https://sites.google.com/view/skincare-ia-privacy';
const TERMS_OF_SERVICE_URL = 'https://sites.google.com/view/skincare-ia-terms';

type QuestionnaireStep = 'disclaimer' | 'gender' | 'age' | 'skin_goal' | 'skin_type';

interface QuestionnaireData {
  gender?: string;
  age_range?: string;
  skin_goal?: string;
  skin_type?: string;
}

const genderOptions = [
  { id: 'male', label: 'Male', emoji: '👨' },
  { id: 'female', label: 'Female', emoji: '👩' },
  { id: 'other', label: 'Other', emoji: '🧑' },
];

const ageOptions = [
  { id: 'under_15', label: 'Under 15', emoji: '🚲' },
  { id: '16_18', label: '16-18', emoji: '🛴' },
  { id: '19_25', label: '19-25', emoji: '🚗' },
  { id: '26_45', label: '26-45', emoji: '🚙' },
  { id: '46_65', label: '46-65', emoji: '🚐' },
  { id: 'over_65', label: 'Over 65', emoji: '🚌' },
];

const skinGoalOptions = [
  { 
    id: 'clear_acne', 
    label: 'Clear Acne', 
    description: 'Get rid of pimples, blackheads, acne marks, clogged pores, etc.',
    emoji: '🫧' 
  },
  { 
    id: 'anti_aging', 
    label: 'Fight skin aging', 
    description: 'Prevent wrinkles, dark spots, improve firmness, maintain skin health, etc.',
    emoji: '⏳' 
  },
  { 
    id: 'other', 
    label: 'Other', 
    description: 'Another skin-related goal.',
    emoji: '❓' 
  },
];

const skinTypeOptions = [
  { 
    id: 'oily', 
    label: 'Oily skin', 
    description: 'Shiny, with visibly enlarged pores',
    emoji: '🌧️' 
  },
  { 
    id: 'dry', 
    label: 'Dry Skin', 
    description: 'Flaky, rough, tight pores',
    emoji: '🌤️' 
  },
  { 
    id: 'combination', 
    label: 'Combination', 
    description: 'Dry in some areas, oily in some (T zone)',
    emoji: '⛅' 
  },
  { 
    id: 'normal', 
    label: 'Normal Skin', 
    description: 'Balanced, neither oily nor dry',
    emoji: '☁️' 
  },
];

export default function SkinQuestionnaireScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { updateProfile } = useAuth();
  const router = useRouter();

  const [currentStep, setCurrentStep] = useState<QuestionnaireStep>('disclaimer');
  const [data, setData] = useState<QuestionnaireData>({});
  const [loading, setLoading] = useState(false);

  const steps: QuestionnaireStep[] = ['disclaimer', 'gender', 'age', 'skin_goal', 'skin_type'];
  const currentStepIndex = steps.indexOf(currentStep);

  const handleBack = () => {
    if (currentStepIndex > 0) {
      setCurrentStep(steps[currentStepIndex - 1]);
    }
  };

  const handleSkip = async () => {
    // Skip to home without saving questionnaire data
    router.replace('/(tabs)/home');
  };

  const handleContinue = async () => {
    if (currentStepIndex < steps.length - 1) {
      setCurrentStep(steps[currentStepIndex + 1]);
    } else {
      // Save questionnaire data and navigate to home
      setLoading(true);
      try {
        await updateProfile({
          gender: data.gender,
          age_range: data.age_range,
          skin_goals: data.skin_goal ? [data.skin_goal] : [],
          skin_type: data.skin_type,
        });
      } catch (error) {
        console.error('Failed to save questionnaire data:', error);
      } finally {
        setLoading(false);
        router.replace('/(tabs)/home');
      }
    }
  };

  const renderDisclaimer = () => (
    <View style={styles.stepContainer}>
      <View style={[styles.iconCircle, { backgroundColor: theme.primary + '20' }]}>
        <Text style={styles.disclaimerIcon}>😊</Text>
      </View>
      
      <Text style={[styles.title, { color: theme.text }]}>Disclaimer</Text>
      
      <View style={[styles.disclaimerCard, { backgroundColor: theme.card }]}>
        <View style={styles.disclaimerItem}>
          <View style={[styles.disclaimerIconContainer, { backgroundColor: theme.error + '20' }]}>
            <Ionicons name="close-circle" size={24} color={theme.error} />
          </View>
          <Text style={[styles.disclaimerText, { color: theme.text }]}>
            This app does not provide medical advice or diagnoses.
          </Text>
        </View>
        
        <View style={styles.disclaimerItem}>
          <View style={[styles.disclaimerIconContainer, { backgroundColor: theme.success + '20' }]}>
            <Ionicons name="person" size={24} color={theme.success} />
          </View>
          <Text style={[styles.disclaimerText, { color: theme.text }]}>
            Consult with a professional before making medical decisions.
          </Text>
        </View>
        
        <View style={styles.disclaimerItem}>
          <View style={[styles.disclaimerIconContainer, { backgroundColor: theme.warning + '20' }]}>
            <Ionicons name="warning" size={24} color={theme.warning} />
          </View>
          <Text style={[styles.disclaimerText, { color: theme.text }]}>
            Try recommendations at your own risk.
          </Text>
        </View>
      </View>
      
      <Text style={[styles.legalText, { color: theme.textSecondary }]}>
        By continuing, you agree to our{' '}
        <Text 
          style={{ color: theme.primary }} 
          onPress={() => WebBrowser.openBrowserAsync(PRIVACY_POLICY_URL)}
        >
          Privacy Policy
        </Text>
        {' '}and{' '}
        <Text 
          style={{ color: theme.primary }} 
          onPress={() => WebBrowser.openBrowserAsync(TERMS_OF_SERVICE_URL)}
        >
          Terms of Service
        </Text>
        .
      </Text>
    </View>
  );

  const renderGenderSelection = () => (
    <View style={styles.stepContainer}>
      <Text style={[styles.title, { color: theme.text }]}>What's your gender?</Text>
      <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
        This will help us customize your routine
      </Text>
      
      {genderOptions.map((option) => (
        <TouchableOpacity
          key={option.id}
          style={[
            styles.optionCard,
            { 
              backgroundColor: theme.card,
              borderColor: data.gender === option.id ? theme.primary : theme.border,
              borderWidth: data.gender === option.id ? 2 : 1,
            }
          ]}
          onPress={() => setData({ ...data, gender: option.id })}
        >
          <Text style={styles.optionEmoji}>{option.emoji}</Text>
          <Text style={[styles.optionLabel, { color: theme.text }]}>{option.label}</Text>
          {data.gender === option.id && (
            <Ionicons name="checkmark-circle" size={24} color={theme.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderAgeSelection = () => (
    <View style={styles.stepContainer}>
      <Text style={[styles.title, { color: theme.text }]}>Select your age range</Text>
      <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
        This helps us understand your skin needs
      </Text>
      
      {ageOptions.map((option) => (
        <TouchableOpacity
          key={option.id}
          style={[
            styles.optionCard,
            { 
              backgroundColor: theme.card,
              borderColor: data.age_range === option.id ? theme.primary : theme.border,
              borderWidth: data.age_range === option.id ? 2 : 1,
            }
          ]}
          onPress={() => setData({ ...data, age_range: option.id })}
        >
          <Text style={styles.optionEmoji}>{option.emoji}</Text>
          <Text style={[styles.optionLabel, { color: theme.text }]}>{option.label}</Text>
          {data.age_range === option.id && (
            <Ionicons name="checkmark-circle" size={24} color={theme.primary} />
          )}
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderSkinGoalSelection = () => (
    <View style={styles.stepContainer}>
      <Text style={[styles.title, { color: theme.text }]}>What is your skin goal?</Text>
      <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
        SkinAdvisor AI will create a routine accordingly
      </Text>
      
      {skinGoalOptions.map((option) => (
        <TouchableOpacity
          key={option.id}
          style={[
            styles.goalCard,
            { 
              backgroundColor: theme.card,
              borderColor: data.skin_goal === option.id ? theme.primary : theme.border,
              borderWidth: data.skin_goal === option.id ? 2 : 1,
            }
          ]}
          onPress={() => setData({ ...data, skin_goal: option.id })}
        >
          <View style={styles.goalHeader}>
            <Text style={styles.goalEmoji}>{option.emoji}</Text>
            <Text style={[styles.goalLabel, { color: theme.text }]}>{option.label}</Text>
            {data.skin_goal === option.id && (
              <Ionicons name="checkmark-circle" size={24} color={theme.primary} />
            )}
          </View>
          <Text style={[styles.goalDescription, { color: theme.textSecondary }]}>
            {option.description}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderSkinTypeSelection = () => (
    <View style={styles.stepContainer}>
      <Text style={[styles.title, { color: theme.text }]}>What is your skin type?</Text>
      <Text style={[styles.subtitle, { color: theme.textSecondary }]}>
        Different skin types have different needs
      </Text>
      
      {skinTypeOptions.map((option) => (
        <TouchableOpacity
          key={option.id}
          style={[
            styles.goalCard,
            { 
              backgroundColor: theme.card,
              borderColor: data.skin_type === option.id ? theme.primary : theme.border,
              borderWidth: data.skin_type === option.id ? 2 : 1,
            }
          ]}
          onPress={() => setData({ ...data, skin_type: option.id })}
        >
          <View style={styles.goalHeader}>
            <Text style={styles.goalEmoji}>{option.emoji}</Text>
            <Text style={[styles.goalLabel, { color: theme.text }]}>{option.label}</Text>
            {data.skin_type === option.id && (
              <Ionicons name="checkmark-circle" size={24} color={theme.primary} />
            )}
          </View>
          <Text style={[styles.goalDescription, { color: theme.textSecondary }]}>
            {option.description}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderCurrentStep = () => {
    switch (currentStep) {
      case 'disclaimer':
        return renderDisclaimer();
      case 'gender':
        return renderGenderSelection();
      case 'age':
        return renderAgeSelection();
      case 'skin_goal':
        return renderSkinGoalSelection();
      case 'skin_type':
        return renderSkinTypeSelection();
      default:
        return null;
    }
  };

  const canContinue = () => {
    switch (currentStep) {
      case 'disclaimer':
        return true;
      case 'gender':
        return !!data.gender;
      case 'age':
        return !!data.age_range;
      case 'skin_goal':
        return !!data.skin_goal;
      case 'skin_type':
        return !!data.skin_type;
      default:
        return false;
    }
  };

  const getContinueButtonText = () => {
    if (currentStep === 'disclaimer') {
      return "Sounds good!";
    }
    if (currentStepIndex === steps.length - 1) {
      return "Finish";
    }
    return "Continue";
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        {currentStepIndex > 0 ? (
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={24} color={theme.primary} />
            <Text style={[styles.backText, { color: theme.primary }]}>Back</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.backButton} />
        )}
        
        {/* Progress dots */}
        <View style={styles.progressDots}>
          {steps.map((step, index) => (
            <View
              key={step}
              style={[
                styles.dot,
                {
                  backgroundColor: index <= currentStepIndex ? theme.primary : theme.border,
                }
              ]}
            />
          ))}
        </View>
        
        <View style={styles.backButton} />
      </View>

      {/* Content */}
      <ScrollView 
        style={styles.content}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {renderCurrentStep()}
      </ScrollView>

      {/* Footer */}
      <View style={styles.footer}>
        {currentStep !== 'disclaimer' && (
          <TouchableOpacity onPress={handleSkip}>
            <Text style={[styles.skipText, { color: theme.textSecondary }]}>
              Skip this step
            </Text>
          </TouchableOpacity>
        )}
        
        <Button
          title={getContinueButtonText()}
          onPress={handleContinue}
          loading={loading}
          disabled={!canContinue()}
          style={styles.continueButton}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 80,
  },
  backText: {
    fontSize: 16,
    marginLeft: 4,
  },
  progressDots: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  content: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  stepContainer: {
    flex: 1,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    marginBottom: 24,
    marginTop: 20,
  },
  disclaimerIcon: {
    fontSize: 40,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 15,
    marginBottom: 24,
  },
  disclaimerCard: {
    borderRadius: 16,
    padding: 20,
    marginBottom: 24,
  },
  disclaimerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  disclaimerIconContainer: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
  },
  legalText: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 22,
  },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
  },
  optionEmoji: {
    fontSize: 28,
    marginRight: 16,
  },
  optionLabel: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
  },
  goalCard: {
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
  },
  goalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  goalEmoji: {
    fontSize: 28,
    marginRight: 12,
  },
  goalLabel: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
  },
  goalDescription: {
    fontSize: 14,
    marginTop: 8,
    marginLeft: 44,
    lineHeight: 20,
  },
  footer: {
    paddingHorizontal: 24,
    paddingBottom: 24,
    paddingTop: 12,
  },
  skipText: {
    fontSize: 15,
    textAlign: 'center',
    marginBottom: 16,
  },
  continueButton: {
    width: '100%',
  },
});
