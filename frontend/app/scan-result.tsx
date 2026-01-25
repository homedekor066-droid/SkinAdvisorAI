import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { useI18n } from '../src/context/I18nContext';
import { useAuth } from '../src/context/AuthContext';
import { skinService, ScanResult, DietRecommendations } from '../src/services/skinService';
import { Card, Button } from '../src/components';
import { Ionicons } from '@expo/vector-icons';
import { format } from 'date-fns';
import { BlurView } from 'expo-blur';

// Score color mapping - YELLOW focused for improvement motivation
const getScoreColor = (score: number) => {
  if (score >= 90) return '#4CAF50'; // Excellent - Soft Green (rare)
  if (score >= 75) return '#FFC107'; // Good - Yellow (needs improvement)
  if (score >= 60) return '#FFB300'; // Average - Yellow (needs improvement)
  if (score >= 40) return '#FF9800'; // Needs attention - Orange
  return '#F44336'; // Poor - Red
};

// Score label mapping - improvement-focused messaging
const getScoreInfo = (score: number, t: (key: string) => string) => {
  if (score >= 90) return { 
    label: 'Excellent', 
    icon: 'star' as const,
    message: 'Your skin is in great condition. Maintain your routine for lasting results.',
    improvement: '5-10%'
  };
  if (score >= 75) return { 
    label: 'Good', 
    icon: 'checkmark-circle' as const,
    message: 'Your skin is in good condition, but there is still room for improvement.',
    improvement: '10-15%'
  };
  if (score >= 60) return { 
    label: 'Average', 
    icon: 'remove-circle' as const,
    message: 'Your skin shows potential. With the right routine, significant improvement is possible.',
    improvement: '15-25%'
  };
  if (score >= 40) return { 
    label: 'Needs Attention', 
    icon: 'alert-circle' as const,
    message: 'Your skin needs attention. A consistent routine can make a real difference.',
    improvement: '25-40%'
  };
  return { 
    label: 'Needs Care', 
    icon: 'close-circle' as const,
    message: 'Your skin requires focused care. Start with the basics for visible improvement.',
    improvement: '40-60%'
  };
};

// Optimization opportunities based on score
const getOptimizationOpportunities = (score: number, skinType: string) => {
  const opportunities = [];
  
  // Always show some opportunities to encourage improvement
  if (score < 95) {
    opportunities.push({ icon: 'water-outline', text: 'Hydration optimization' });
  }
  if (score < 90) {
    opportunities.push({ icon: 'sparkles-outline', text: 'Pore refinement' });
  }
  if (score < 85) {
    opportunities.push({ icon: 'shield-outline', text: 'Skin barrier strengthening' });
  }
  if (score < 80) {
    opportunities.push({ icon: 'hourglass-outline', text: 'Anti-aging prevention' });
  }
  if (score < 75) {
    opportunities.push({ icon: 'color-palette-outline', text: 'Tone uniformity' });
  }
  if (score < 70) {
    opportunities.push({ icon: 'sunny-outline', text: 'Sun damage repair' });
  }
  
  // Always return at least 3 opportunities
  if (opportunities.length < 3) {
    if (!opportunities.find(o => o.text === 'Hydration optimization')) {
      opportunities.push({ icon: 'water-outline', text: 'Hydration optimization' });
    }
    if (!opportunities.find(o => o.text === 'Skin barrier strengthening')) {
      opportunities.push({ icon: 'shield-outline', text: 'Skin barrier strengthening' });
    }
    if (!opportunities.find(o => o.text === 'Anti-aging prevention')) {
      opportunities.push({ icon: 'hourglass-outline', text: 'Anti-aging prevention' });
    }
  }
  
  return opportunities.slice(0, 5);
};

// Locked Content Component
const LockedSection = ({ 
  title, 
  description, 
  previewCount, 
  onUnlock, 
  theme 
}: { 
  title: string; 
  description: string; 
  previewCount?: number;
  onUnlock: () => void;
  theme: any;
}) => (
  <View style={[styles.lockedContainer, { backgroundColor: theme.surface }]}>
    <View style={styles.lockedContent}>
      <View style={[styles.lockIconCircle, { backgroundColor: theme.primary + '20' }]}>
        <Ionicons name="lock-closed" size={32} color={theme.primary} />
      </View>
      <Text style={[styles.lockedTitle, { color: theme.text }]}>{title}</Text>
      <Text style={[styles.lockedDescription, { color: theme.textSecondary }]}>
        {description}
      </Text>
      {previewCount !== undefined && (
        <Text style={[styles.previewCount, { color: theme.primary }]}>
          {previewCount} items ready for you
        </Text>
      )}
      <TouchableOpacity 
        style={[styles.unlockButton, { backgroundColor: theme.primary }]}
        onPress={onUnlock}
      >
        <Ionicons name="sparkles" size={18} color="#FFFFFF" />
        <Text style={styles.unlockButtonText}>Unlock Premium</Text>
      </TouchableOpacity>
    </View>
  </View>
);

export default function ScanResultScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { token, user } = useAuth();
  const { scanId } = useLocalSearchParams<{ scanId: string }>();
  const router = useRouter();

  const [scan, setScan] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'analysis' | 'routine' | 'nutrition' | 'products'>('analysis');

  // Check if user has premium
  const isPremium = scan?.user_plan === 'premium' || user?.plan === 'premium';
  const isLocked = !isPremium;

  useEffect(() => {
    fetchScanResult();
  }, [scanId]);

  const fetchScanResult = async () => {
    if (!scanId || !token) return;
    try {
      const result = await skinService.getScanDetail(scanId, token);
      setScan(result);
    } catch (error) {
      console.error('Failed to fetch scan:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSkinTypeColor = (skinType: string) => {
    const colors: { [key: string]: string } = {
      oily: '#F39C12',
      dry: '#3498DB',
      combination: '#9B59B6',
      normal: '#27AE60',
      sensitive: '#E74C3C',
    };
    return colors[skinType?.toLowerCase()] || theme.primary;
  };

  const getSeverityColor = (severity: number) => {
    if (severity <= 3) return theme.success;
    if (severity <= 6) return theme.warning;
    return theme.error;
  };

  const getSeverityLabel = (severity: number) => {
    if (severity <= 3) return t('mild') || 'mild';
    if (severity <= 6) return t('moderate') || 'moderate';
    return t('severe') || 'severe';
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.primary} />
          <Text style={[styles.loadingText, { color: theme.textSecondary }]}>
            {t('loading')}
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!scan) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle-outline" size={48} color={theme.error} />
          <Text style={[styles.errorText, { color: theme.text }]}>Scan not found</Text>
          <Button title="Go Back" onPress={() => router.back()} style={{ marginTop: 16 }} />
        </View>
      </SafeAreaView>
    );
  }

  const { analysis, routine, products, diet_recommendations, created_at, image_base64 } = scan;
  const overallScore = analysis?.overall_score || 75;
  const scoreColor = getScoreColor(overallScore);
  const scoreInfo = getScoreInfo(overallScore, t);
  const scoreFactors = analysis?.score_factors || [];
  
  // Get preview data for free users
  const preview = scan?.preview || {};
  const mainIssues = analysis?.main_issues || [];

  // Navigate to paywall
  const goToPaywall = () => {
    router.push({
      pathname: '/paywall',
      params: { scanId: scanId }
    });
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.title, { color: theme.text }]}>{t('analysis_complete')}</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* Score Section - PROMINENT */}
        <Card style={styles.scoreCard}>
          {/* Skin Type - PROMINENT */}
          <View style={[styles.skinTypeHeader, { borderBottomColor: theme.border }]}>
            <View style={styles.skinTypeRow}>
              <Ionicons name="person-circle-outline" size={24} color={getSkinTypeColor(analysis?.skin_type || 'normal')} />
              <Text style={[styles.skinTypeHeaderLabel, { color: theme.textSecondary }]}>
                {t('skin_type')}:
              </Text>
              <View style={[
                styles.skinTypeBadgeLarge,
                { backgroundColor: getSkinTypeColor(analysis?.skin_type || 'normal') + '20' }
              ]}>
                <Text style={[
                  styles.skinTypeTextLarge,
                  { color: getSkinTypeColor(analysis?.skin_type || 'normal') }
                ]}>
                  {t(analysis?.skin_type || 'normal') || analysis?.skin_type || 'Normal'}
                </Text>
              </View>
            </View>
            {analysis?.skin_type_confidence && (
              <Text style={[styles.skinTypeConfidence, { color: theme.textMuted }]}>
                {Math.round(analysis.skin_type_confidence * 100)}% {t('confidence') || 'confidence'}
              </Text>
            )}
          </View>

          {/* Score */}
          <View style={styles.scoreHeader}>
            <View style={styles.scoreCircleContainer}>
              <View style={[styles.scoreCircle, { borderColor: scoreColor }]}>
                <Text style={[styles.scoreValue, { color: scoreColor }]}>
                  {overallScore}
                </Text>
              </View>
            </View>
            <View style={styles.scoreLabelContainer}>
              <View style={styles.scoreLabelRow}>
                <Ionicons name={scoreInfo.icon} size={24} color={scoreColor} />
                <Text style={[styles.scoreLabel, { color: scoreColor }]}>
                  {scoreInfo.label}
                </Text>
              </View>
              <Text style={[styles.scoreDescription, { color: theme.textSecondary }]}>
                {t('overall_score')}
              </Text>
            </View>
          </View>

          {/* Score Info Tooltip */}
          <View style={[styles.scoreInfoBox, { backgroundColor: theme.surface }]}>
            <Ionicons name="information-circle-outline" size={16} color={theme.info} />
            <Text style={[styles.scoreInfoText, { color: theme.textSecondary }]}>
              {t('score_info') || 'Score represents overall skin health based on detected issues and their severity.'}
            </Text>
          </View>

          {/* Score Factors */}
          {scoreFactors.length > 0 && (
            <View style={styles.factorsSection}>
              <Text style={[styles.factorsTitle, { color: theme.text }]}>
                {t('main_factors') || 'Main factors affecting your score'}:
              </Text>
              {scoreFactors.slice(0, 4).map((factor: any, index: number) => (
                <View key={index} style={styles.factorItem}>
                  <View style={[styles.factorDot, { backgroundColor: getSeverityColor(factor.severity) }]} />
                  <Text style={[styles.factorText, { color: theme.text }]}>
                    {factor.issue}
                  </Text>
                  <Text style={[styles.factorSeverity, { color: getSeverityColor(factor.severity) }]}>
                    ({factor.severity_label || getSeverityLabel(factor.severity)})
                  </Text>
                </View>
              ))}
            </View>
          )}
        </Card>

        {/* Image Preview */}
        {image_base64 && (
          <View style={styles.imageSection}>
            <Image
              source={{ uri: `data:image/jpeg;base64,${image_base64}` }}
              style={styles.scanImage}
            />
          </View>
        )}

        {/* Tabs */}
        <View style={[styles.tabs, { backgroundColor: theme.surface }]}>
          {(['analysis', 'routine', 'nutrition', 'products'] as const).map((tab) => (
            <TouchableOpacity
              key={tab}
              style={[
                styles.tab,
                activeTab === tab && { backgroundColor: theme.primary }
              ]}
              onPress={() => setActiveTab(tab)}
            >
              <Ionicons 
                name={
                  tab === 'analysis' ? 'analytics-outline' :
                  tab === 'routine' ? 'time-outline' :
                  tab === 'nutrition' ? 'nutrition-outline' : 'leaf-outline'
                } 
                size={16} 
                color={activeTab === tab ? '#FFFFFF' : theme.textSecondary} 
                style={{ marginBottom: 2 }}
              />
              <Text style={[
                styles.tabText,
                { color: activeTab === tab ? '#FFFFFF' : theme.textSecondary }
              ]}>
                {tab === 'analysis' ? t('skin_issues') :
                 tab === 'routine' ? t('my_routines') : 
                 tab === 'nutrition' ? 'Nutrition' : t('products')}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Tab Content */}
        {activeTab === 'analysis' && analysis && (
          <View style={styles.tabContent}>
            {/* Skin Type Description */}
            <Card style={styles.descriptionCard}>
              <Text style={[styles.descriptionText, { color: theme.textSecondary }]}>
                {analysis.skin_type_description}
              </Text>
            </Card>

            {/* Issues */}
            <Text style={[styles.sectionTitle, { color: theme.text }]}>
              {t('skin_issues')} ({analysis.issues?.length || 0})
            </Text>
            
            {(!analysis.issues || analysis.issues.length === 0) ? (
              <Card style={styles.noIssuesCard}>
                <Ionicons name="checkmark-circle" size={32} color={theme.success} />
                <Text style={[styles.noIssuesText, { color: theme.text }]}>
                  No significant issues detected
                </Text>
                <Text style={[styles.noIssuesSubtext, { color: theme.textSecondary }]}>
                  Your skin appears healthy!
                </Text>
              </Card>
            ) : (
              analysis.issues?.map((issue: any, index: number) => (
                <Card key={index} style={styles.issueCard}>
                  <View style={styles.issueHeader}>
                    <Text style={[styles.issueName, { color: theme.text }]}>
                      {issue.name}
                    </Text>
                    <View style={[
                      styles.severityBadge,
                      { backgroundColor: getSeverityColor(issue.severity) + '20' }
                    ]}>
                      <Text style={[styles.severityText, { color: getSeverityColor(issue.severity) }]}>
                        {issue.severity}/10 • {getSeverityLabel(issue.severity)}
                      </Text>
                    </View>
                  </View>
                  <Text style={[styles.issueDescription, { color: theme.textSecondary }]}>
                    {issue.description}
                  </Text>
                  {issue.confidence && (
                    <Text style={[styles.issueConfidence, { color: theme.textMuted }]}>
                      {t('confidence')}: {Math.round(issue.confidence * 100)}%
                    </Text>
                  )}
                  <View style={[styles.severityBar, { backgroundColor: theme.border }]}>
                    <View
                      style={[
                        styles.severityFill,
                        {
                          width: `${issue.severity * 10}%`,
                          backgroundColor: getSeverityColor(issue.severity)
                        }
                      ]}
                    />
                  </View>
                </Card>
              ))
            )}

            {/* Recommendations */}
            <Text style={[styles.sectionTitle, { color: theme.text }]}>
              {t('recommendations')}
            </Text>
            <Card>
              {analysis.recommendations?.map((rec: string, index: number) => (
                <View key={index} style={styles.recommendationItem}>
                  <Ionicons name="checkmark-circle" size={20} color={theme.success} />
                  <Text style={[styles.recommendationText, { color: theme.text }]}>
                    {rec}
                  </Text>
                </View>
              ))}
            </Card>
          </View>
        )}

        {activeTab === 'routine' && (
          <View style={styles.tabContent}>
            {isLocked ? (
              <LockedSection
                title="Your personalized routine is ready"
                description="Unlock to see exact steps for morning & night skincare."
                previewCount={preview.routine_steps_count}
                onUnlock={goToPaywall}
                theme={theme}
              />
            ) : routine && (
              <>
                {/* Morning Routine */}
                <Text style={[styles.sectionTitle, { color: theme.text }]}>
                  {t('morning_routine')}
                </Text>
                {routine.morning_routine?.map((step: any, index: number) => (
                  <Card key={index} style={styles.routineCard}>
                    <View style={styles.stepHeader}>
                      <View style={[styles.stepNumber, { backgroundColor: theme.primary }]}>
                        <Text style={styles.stepNumberText}>{step.order}</Text>
                      </View>
                      <View style={styles.stepInfo}>
                        <Text style={[styles.stepName, { color: theme.text }]}>
                          {step.step_name}
                        </Text>
                        <Text style={[styles.productType, { color: theme.primary }]}>
                          {step.product_type}
                        </Text>
                      </View>
                    </View>
                    <Text style={[styles.instructions, { color: theme.textSecondary }]}>
                      {step.instructions}
                    </Text>
                    {step.ingredients_to_look_for?.length > 0 && (
                      <View style={styles.ingredientSection}>
                        <Text style={[styles.ingredientLabel, { color: theme.success }]}>
                          Look for:
                        </Text>
                        <Text style={[styles.ingredientList, { color: theme.textSecondary }]}>
                          {step.ingredients_to_look_for.join(', ')}
                        </Text>
                      </View>
                    )}
                  </Card>
                ))}

                {/* Evening Routine */}
                <Text style={[styles.sectionTitle, { color: theme.text }]}>
                  {t('evening_routine')}
                </Text>
                {routine.evening_routine?.map((step: any, index: number) => (
                  <Card key={index} style={styles.routineCard}>
                    <View style={styles.stepHeader}>
                      <View style={[styles.stepNumber, { backgroundColor: theme.info }]}>
                        <Text style={styles.stepNumberText}>{step.order}</Text>
                      </View>
                      <View style={styles.stepInfo}>
                        <Text style={[styles.stepName, { color: theme.text }]}>
                          {step.step_name}
                        </Text>
                        <Text style={[styles.productType, { color: theme.info }]}>
                          {step.product_type}
                        </Text>
                      </View>
                    </View>
                    <Text style={[styles.instructions, { color: theme.textSecondary }]}>
                      {step.instructions}
                    </Text>
                  </Card>
                ))}

                {/* Weekly Routine */}
                {routine.weekly_routine?.length > 0 && (
                  <>
                    <Text style={[styles.sectionTitle, { color: theme.text }]}>
                      {t('weekly_routine')}
                    </Text>
                    {routine.weekly_routine?.map((step: any, index: number) => (
                      <Card key={index} style={styles.routineCard}>
                        <View style={styles.stepHeader}>
                          <View style={[styles.stepNumber, { backgroundColor: theme.warning }]}>
                            <Text style={styles.stepNumberText}>{step.order}</Text>
                          </View>
                          <View style={styles.stepInfo}>
                            <Text style={[styles.stepName, { color: theme.text }]}>
                              {step.step_name}
                            </Text>
                            <Text style={[styles.productType, { color: theme.warning }]}>
                              {step.product_type}
                        </Text>
                      </View>
                    </View>
                    <Text style={[styles.instructions, { color: theme.textSecondary }]}>
                      {step.instructions}
                    </Text>
                  </Card>
                ))}
              </>
            )}
              </>
            )}
          </View>
        )}

        {activeTab === 'products' && (
          <View style={styles.tabContent}>
            {isLocked ? (
              <LockedSection
                title="Product recommendations ready"
                description="Unlock to see the best products for your skin type."
                previewCount={preview.products_count}
                onUnlock={goToPaywall}
                theme={theme}
              />
            ) : products && (
              <>
                <Text style={[styles.sectionTitle, { color: theme.text }]}>
                  {t('products')} ({products.length})
                </Text>
                {products.map((product: any, index: number) => (
                  <Card key={index} style={styles.productCard}>
                    <View style={styles.productHeader}>
                      <View style={[styles.productIcon, { backgroundColor: theme.primary + '20' }]}>
                        <Ionicons name="leaf-outline" size={24} color={theme.primary} />
                      </View>
                      <View style={styles.productInfo}>
                        <Text style={[styles.productName, { color: theme.text }]}>
                          {product.name}
                        </Text>
                        <Text style={[styles.productTypeText, { color: theme.primary }]}>
                          {product.product_type}
                        </Text>
                      </View>
                      <Text style={[styles.priceRange, { color: theme.success }]}>
                        {product.price_range}
                      </Text>
                    </View>
                    <Text style={[styles.productDescription, { color: theme.textSecondary }]}>
                      {product.description}
                    </Text>
                    <View style={styles.keyIngredients}>
                      <Text style={[styles.keyIngredientsLabel, { color: theme.text }]}>
                        Key Ingredients:
                      </Text>
                      <View style={styles.ingredientTags}>
                        {product.key_ingredients?.slice(0, 4).map((ingredient: string, i: number) => (
                          <View key={i} style={[styles.ingredientTag, { backgroundColor: theme.surface }]}>
                            <Text style={[styles.ingredientTagText, { color: theme.textSecondary }]}>
                              {ingredient}
                            </Text>
                          </View>
                        ))}
                      </View>
                    </View>
                  </Card>
                ))}
              </>
            )}
          </View>
        )}

        {/* Nutrition Tab Content */}
        {activeTab === 'nutrition' && (
          <View style={styles.tabContent}>
            {isLocked ? (
              <LockedSection
                title="Nutrition has a huge impact on your skin"
                description="Unlock to see what to eat and avoid for better skin."
                previewCount={preview.diet_items_count}
                onUnlock={goToPaywall}
                theme={theme}
              />
            ) : diet_recommendations && (
              <>
                {/* Hydration Tip Card */}
                <Card style={[styles.hydrationCard, { backgroundColor: '#E3F2FD' }]}>
                  <View style={styles.hydrationHeader}>
                    <Ionicons name="water-outline" size={28} color="#1976D2" />
                    <Text style={[styles.hydrationTitle, { color: '#1976D2' }]}>
                      Hydration Tip
                    </Text>
                  </View>
                  <Text style={[styles.hydrationText, { color: '#0D47A1' }]}>
                    {diet_recommendations.hydration_tip}
                  </Text>
                </Card>

                {/* Foods to Eat More */}
                <Text style={[styles.sectionTitle, { color: theme.text }]}>
                  <Ionicons name="checkmark-circle" size={20} color={theme.success} /> Foods to Eat More
                </Text>
                {diet_recommendations.eat_more?.map((food, index) => (
                  <Card key={index} style={styles.foodCard}>
                    <View style={styles.foodHeader}>
                      <View style={[styles.foodIconContainer, { backgroundColor: '#E8F5E9' }]}>
                        <Ionicons name="leaf" size={20} color="#4CAF50" />
                      </View>
                      <Text style={[styles.foodName, { color: theme.text }]}>
                        {food.name}
                      </Text>
                    </View>
                    <Text style={[styles.foodReason, { color: theme.textSecondary }]}>
                      {food.reason}
                    </Text>
                  </Card>
                ))}

                {/* Foods to Avoid */}
                <Text style={[styles.sectionTitle, { color: theme.text, marginTop: 20 }]}>
                  <Ionicons name="close-circle" size={20} color={theme.error} /> Foods to Limit/Avoid
                </Text>
                {diet_recommendations.avoid?.map((food, index) => (
                  <Card key={index} style={styles.foodCard}>
                    <View style={styles.foodHeader}>
                      <View style={[styles.foodIconContainer, { backgroundColor: '#FFEBEE' }]}>
                        <Ionicons name="ban" size={20} color="#F44336" />
                      </View>
                      <Text style={[styles.foodName, { color: theme.text }]}>
                        {food.name}
                      </Text>
                    </View>
                    <Text style={[styles.foodReason, { color: theme.textSecondary }]}>
                      {food.reason}
                    </Text>
                  </Card>
                ))}

                {/* Optional Supplements */}
                {diet_recommendations.supplements_optional && diet_recommendations.supplements_optional.length > 0 && (
                  <>
                    <Text style={[styles.sectionTitle, { color: theme.text, marginTop: 20 }]}>
                      <Ionicons name="medical" size={20} color={theme.info} /> Optional Supplements
                    </Text>
                    <Card style={styles.supplementsCard}>
                      {diet_recommendations.supplements_optional.map((supplement, index) => (
                        <View key={index} style={[
                          styles.supplementItem,
                          index < diet_recommendations.supplements_optional!.length - 1 && styles.supplementBorder
                        ]}>
                          <View style={styles.supplementHeader}>
                            <Ionicons name="add-circle-outline" size={18} color={theme.info} />
                            <Text style={[styles.supplementName, { color: theme.text }]}>
                              {supplement.name}
                            </Text>
                          </View>
                          <Text style={[styles.supplementReason, { color: theme.textSecondary }]}>
                            {supplement.reason}
                          </Text>
                        </View>
                      ))}
                    </Card>
                  </>
                )}

                {/* Nutrition Disclaimer */}
                <View style={[styles.nutritionDisclaimer, { backgroundColor: '#FFF3E0' }]}>
                  <Ionicons name="information-circle" size={20} color="#E65100" />
                  <Text style={[styles.nutritionDisclaimerText, { color: '#E65100' }]}>
                    Nutrition suggestions are general wellness advice and not medical treatment. 
                    Consult a healthcare professional before making significant dietary changes.
                  </Text>
                </View>
              </>
            )}
          </View>
        )}

        {/* Upgrade Banner for Free Users */}
        {isLocked && (
          <TouchableOpacity 
            style={[styles.upgradeBanner, { backgroundColor: theme.primary }]}
            onPress={goToPaywall}
          >
            <View style={styles.upgradeBannerContent}>
              <Ionicons name="sparkles" size={24} color="#FFFFFF" />
              <View style={styles.upgradeBannerText}>
                <Text style={styles.upgradeBannerTitle}>
                  Unlock your full skin improvement plan
                </Text>
                <Text style={styles.upgradeBannerSubtitle}>
                  Routine, diet, products & more
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={24} color="#FFFFFF" />
            </View>
          </TouchableOpacity>
        )}

        {/* Disclaimer */}
        <View style={[styles.disclaimer, { backgroundColor: theme.surface }]}>
          <Ionicons name="information-circle-outline" size={16} color={theme.textMuted} />
          <Text style={[styles.disclaimerText, { color: theme.textMuted }]}>
            {t('disclaimer')}
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  errorText: {
    fontSize: 18,
    marginTop: 16,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  // Score Card Styles
  scoreCard: {
    marginBottom: 20,
    padding: 20,
  },
  // Skin Type Header - PROMINENT
  skinTypeHeader: {
    borderBottomWidth: 1,
    paddingBottom: 16,
    marginBottom: 16,
  },
  skinTypeRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  skinTypeHeaderLabel: {
    fontSize: 14,
    marginLeft: 8,
    marginRight: 8,
  },
  skinTypeBadgeLarge: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
  },
  skinTypeTextLarge: {
    fontSize: 16,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  skinTypeConfidence: {
    fontSize: 12,
    marginTop: 8,
    marginLeft: 32,
  },
  scoreHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  scoreCircleContainer: {
    marginRight: 20,
  },
  scoreCircle: {
    width: 90,
    height: 90,
    borderRadius: 45,
    borderWidth: 5,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scoreValue: {
    fontSize: 36,
    fontWeight: 'bold',
  },
  scoreLabelContainer: {
    flex: 1,
  },
  scoreLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  scoreLabel: {
    fontSize: 18,
    fontWeight: '600',
    marginLeft: 8,
  },
  scoreDescription: {
    fontSize: 14,
  },
  scoreInfoBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  scoreInfoText: {
    flex: 1,
    fontSize: 12,
    marginLeft: 8,
    lineHeight: 18,
  },
  factorsSection: {
    borderTopWidth: 1,
    borderTopColor: '#E8E8E8',
    paddingTop: 16,
  },
  factorsTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
  },
  factorItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  factorDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 10,
  },
  factorText: {
    fontSize: 14,
    flex: 1,
  },
  factorSeverity: {
    fontSize: 12,
    fontWeight: '500',
  },
  // Image Section
  imageSection: {
    marginBottom: 16,
    alignItems: 'center',
  },
  scanImage: {
    width: 120,
    height: 120,
    borderRadius: 16,
  },
  tabs: {
    flexDirection: 'row',
    borderRadius: 12,
    padding: 4,
    marginBottom: 20,
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  tabText: {
    fontSize: 13,
    fontWeight: '600',
  },
  tabContent: {
    marginBottom: 20,
  },
  descriptionCard: {
    marginBottom: 20,
  },
  descriptionText: {
    fontSize: 14,
    lineHeight: 22,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 12,
  },
  noIssuesCard: {
    alignItems: 'center',
    paddingVertical: 24,
    marginBottom: 20,
  },
  noIssuesText: {
    fontSize: 16,
    fontWeight: '600',
    marginTop: 12,
  },
  noIssuesSubtext: {
    fontSize: 14,
    marginTop: 4,
  },
  issueCard: {
    marginBottom: 12,
  },
  issueHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  issueName: {
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
  },
  severityBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  severityText: {
    fontSize: 11,
    fontWeight: '600',
  },
  issueDescription: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 8,
  },
  issueConfidence: {
    fontSize: 11,
    marginBottom: 8,
  },
  severityBar: {
    height: 4,
    borderRadius: 2,
  },
  severityFill: {
    height: 4,
    borderRadius: 2,
  },
  recommendationItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  recommendationText: {
    flex: 1,
    marginLeft: 10,
    fontSize: 14,
    lineHeight: 20,
  },
  routineCard: {
    marginBottom: 12,
  },
  stepHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  stepNumber: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  stepNumberText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  stepInfo: {
    flex: 1,
  },
  stepName: {
    fontSize: 16,
    fontWeight: '600',
  },
  productType: {
    fontSize: 12,
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  instructions: {
    fontSize: 14,
    lineHeight: 20,
  },
  ingredientSection: {
    marginTop: 12,
  },
  ingredientLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  ingredientList: {
    fontSize: 13,
  },
  productCard: {
    marginBottom: 12,
  },
  productHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  productIcon: {
    width: 48,
    height: 48,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  productInfo: {
    flex: 1,
  },
  productName: {
    fontSize: 16,
    fontWeight: '600',
  },
  productTypeText: {
    fontSize: 12,
    fontWeight: '500',
    textTransform: 'capitalize',
  },
  priceRange: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  productDescription: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  keyIngredients: {
    marginTop: 8,
  },
  keyIngredientsLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 8,
  },
  ingredientTags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  ingredientTag: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 8,
    marginBottom: 8,
  },
  ingredientTagText: {
    fontSize: 12,
  },
  disclaimer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 16,
    borderRadius: 12,
    marginTop: 20,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 12,
    marginLeft: 8,
    lineHeight: 18,
  },
  // Nutrition Tab Styles
  hydrationCard: {
    marginBottom: 20,
    padding: 16,
    borderRadius: 12,
  },
  hydrationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  hydrationTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginLeft: 10,
  },
  hydrationText: {
    fontSize: 14,
    lineHeight: 22,
  },
  foodCard: {
    marginBottom: 10,
    padding: 14,
  },
  foodHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  foodIconContainer: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  foodName: {
    fontSize: 15,
    fontWeight: '600',
    flex: 1,
  },
  foodReason: {
    fontSize: 13,
    lineHeight: 20,
    marginLeft: 44,
  },
  supplementsCard: {
    padding: 16,
  },
  supplementItem: {
    paddingVertical: 12,
  },
  supplementBorder: {
    borderBottomWidth: 1,
    borderBottomColor: '#E8E8E8',
  },
  supplementHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  supplementName: {
    fontSize: 15,
    fontWeight: '600',
    marginLeft: 8,
  },
  supplementReason: {
    fontSize: 13,
    lineHeight: 20,
    marginLeft: 26,
  },
  nutritionDisclaimer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 16,
    borderRadius: 12,
    marginTop: 20,
    marginBottom: 10,
  },
  nutritionDisclaimerText: {
    flex: 1,
    fontSize: 12,
    marginLeft: 10,
    lineHeight: 18,
    fontWeight: '500',
  },
  // Locked Section Styles
  lockedContainer: {
    borderRadius: 16,
    padding: 32,
    alignItems: 'center',
    marginVertical: 20,
  },
  lockedContent: {
    alignItems: 'center',
  },
  lockIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  lockedTitle: {
    fontSize: 20,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 12,
  },
  lockedDescription: {
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 16,
    paddingHorizontal: 10,
  },
  previewCount: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 20,
  },
  unlockButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 25,
    gap: 8,
  },
  unlockButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  // Upgrade Banner Styles
  upgradeBanner: {
    marginTop: 24,
    marginBottom: 16,
    borderRadius: 16,
    overflow: 'hidden',
  },
  upgradeBannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
  },
  upgradeBannerText: {
    flex: 1,
    marginLeft: 12,
  },
  upgradeBannerTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  upgradeBannerSubtitle: {
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: 13,
  },
});
