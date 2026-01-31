import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { useI18n } from '../src/context/I18nContext';
import { useAuth } from '../src/context/AuthContext';
import { Card, Button } from '../src/components';
import { Ionicons } from '@expo/vector-icons';
import Constants from 'expo-constants';

const API_URL = Constants.expoConfig?.extra?.apiUrl || process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface Challenge {
  id: string;
  title: string;
  description: string;
  why_this_challenge: string;
  duration_days: number;
  target_metric: string;
  difficulty: string;
  daily_goal: string;
  tips: string[];
  expected_impact: string;
  progress: {
    days_completed: number;
    total_days: number;
    is_active: boolean;
  };
  completed?: boolean;
}

// Difficulty badge colors
const getDifficultyColor = (difficulty: string) => {
  switch (difficulty) {
    case 'easy': return '#4CAF50';
    case 'medium': return '#FF9800';
    case 'hard': return '#F44336';
    default: return '#9E9E9E';
  }
};

// Metric icon mapping
const getMetricIcon = (metric: string) => {
  const icons: { [key: string]: string } = {
    'hydration_appearance': 'water-outline',
    'texture_smoothness': 'hand-left-outline',
    'redness_level': 'heart-outline',
    'pore_visibility': 'scan-outline',
    'tone_uniformity': 'color-palette-outline',
    'overall': 'fitness-outline',
  };
  return icons[metric] || 'star-outline';
};

export default function ChallengesScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { token, user } = useAuth();
  const router = useRouter();

  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isLocked, setIsLocked] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchChallenges = async () => {
    try {
      const response = await fetch(`${API_URL}/api/challenges/current`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (data.locked) {
        setIsLocked(true);
        setChallenges([]);
      } else {
        setIsLocked(false);
        setChallenges(data.challenges || []);
      }
    } catch (err) {
      console.error('Error fetching challenges:', err);
      setError('Failed to load challenges');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchChallenges();
    }
  }, [token]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchChallenges();
  };

  const handleCompleteDay = async (challengeId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/challenges/progress`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          challenge_id: challengeId,
          day_completed: true,
        }),
      });

      const data = await response.json();
      if (data.success) {
        setChallenges(data.challenges);
      }
    } catch (err) {
      console.error('Error updating challenge:', err);
    }
  };

  const handleRefreshChallenges = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/challenges/refresh`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();
      if (data.success) {
        setChallenges(data.challenges || []);
      }
    } catch (err) {
      console.error('Error refreshing challenges:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.primary} />
          <Text style={[styles.loadingText, { color: theme.textSecondary }]}>
            Loading challenges...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.title, { color: theme.text }]}>Weekly Challenges</Text>
        <TouchableOpacity onPress={handleRefreshChallenges} style={styles.refreshButton}>
          <Ionicons name="refresh" size={24} color={theme.primary} />
        </TouchableOpacity>
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
      >
        {/* Locked State */}
        {isLocked ? (
          <Card style={styles.lockedCard}>
            <View style={[styles.lockIconCircle, { backgroundColor: theme.primary + '20' }]}>
              <Ionicons name="lock-closed" size={48} color={theme.primary} />
            </View>
            <Text style={[styles.lockedTitle, { color: theme.text }]}>
              Weekly Challenges
            </Text>
            <Text style={[styles.lockedDescription, { color: theme.textSecondary }]}>
              Unlock personalized weekly challenges to improve your skin based on your analysis results.
            </Text>
            <View style={styles.previewChallenges}>
              <Text style={[styles.previewLabel, { color: theme.textMuted }]}>
                Sample challenges:
              </Text>
              {['Hydration Hero', 'Smooth Skin Week', '7-Day Streak'].map((title, i) => (
                <View key={i} style={[styles.previewItem, { backgroundColor: theme.surface }]}>
                  <Ionicons name="star-outline" size={16} color={theme.primary} />
                  <Text style={[styles.previewItemText, { color: theme.textSecondary }]}>
                    {title}
                  </Text>
                </View>
              ))}
            </View>
            <TouchableOpacity
              style={[styles.unlockButton, { backgroundColor: theme.primary }]}
              onPress={() => router.push('/paywall')}
            >
              <Ionicons name="sparkles" size={20} color="#FFFFFF" />
              <Text style={styles.unlockButtonText}>Unlock Premium</Text>
            </TouchableOpacity>
          </Card>
        ) : challenges.length === 0 ? (
          /* Empty State */
          <Card style={styles.emptyCard}>
            <Ionicons name="fitness-outline" size={64} color={theme.textMuted} />
            <Text style={[styles.emptyTitle, { color: theme.text }]}>
              No Active Challenges
            </Text>
            <Text style={[styles.emptyDescription, { color: theme.textSecondary }]}>
              Complete a skin scan to receive personalized weekly challenges tailored to your skin needs.
            </Text>
            <TouchableOpacity
              style={[styles.scanButton, { backgroundColor: theme.primary }]}
              onPress={() => router.push('/(tabs)/scan')}
            >
              <Ionicons name="scan-outline" size={20} color="#FFFFFF" />
              <Text style={styles.scanButtonText}>Scan Your Skin</Text>
            </TouchableOpacity>
          </Card>
        ) : (
          /* Challenges List */
          <>
            <Text style={[styles.sectionIntro, { color: theme.textSecondary }]}>
              Complete these challenges to improve your skin health. Each is personalized based on your scan results.
            </Text>

            {challenges.map((challenge, index) => (
              <Card key={challenge.id || index} style={styles.challengeCard}>
                {/* Challenge Header */}
                <View style={styles.challengeHeader}>
                  <View style={[styles.metricIcon, { backgroundColor: theme.primary + '20' }]}>
                    <Ionicons
                      name={getMetricIcon(challenge.target_metric) as any}
                      size={24}
                      color={theme.primary}
                    />
                  </View>
                  <View style={styles.challengeInfo}>
                    <Text style={[styles.challengeTitle, { color: theme.text }]}>
                      {challenge.title}
                    </Text>
                    <View style={styles.challengeMeta}>
                      <View style={[
                        styles.difficultyBadge,
                        { backgroundColor: getDifficultyColor(challenge.difficulty) + '20' }
                      ]}>
                        <Text style={[
                          styles.difficultyText,
                          { color: getDifficultyColor(challenge.difficulty) }
                        ]}>
                          {challenge.difficulty}
                        </Text>
                      </View>
                      <Text style={[styles.durationText, { color: theme.textMuted }]}>
                        {challenge.duration_days} days
                      </Text>
                    </View>
                  </View>
                  {challenge.completed && (
                    <View style={[styles.completedBadge, { backgroundColor: '#E8F5E9' }]}>
                      <Ionicons name="checkmark-circle" size={20} color="#4CAF50" />
                    </View>
                  )}
                </View>

                {/* Description */}
                <Text style={[styles.challengeDescription, { color: theme.textSecondary }]}>
                  {challenge.description}
                </Text>

                {/* Why This Challenge */}
                <View style={[styles.whyContainer, { backgroundColor: theme.surface }]}>
                  <Ionicons name="bulb-outline" size={16} color={theme.primary} />
                  <Text style={[styles.whyText, { color: theme.textSecondary }]}>
                    {challenge.why_this_challenge}
                  </Text>
                </View>

                {/* Daily Goal */}
                <View style={styles.dailyGoalContainer}>
                  <Text style={[styles.dailyGoalLabel, { color: theme.text }]}>
                    Daily Goal:
                  </Text>
                  <Text style={[styles.dailyGoalText, { color: theme.primary }]}>
                    {challenge.daily_goal}
                  </Text>
                </View>

                {/* Progress Bar */}
                <View style={styles.progressSection}>
                  <View style={styles.progressHeader}>
                    <Text style={[styles.progressLabel, { color: theme.textSecondary }]}>
                      Progress
                    </Text>
                    <Text style={[styles.progressText, { color: theme.primary }]}>
                      {challenge.progress.days_completed}/{challenge.progress.total_days} days
                    </Text>
                  </View>
                  <View style={[styles.progressBarContainer, { backgroundColor: theme.border }]}>
                    <View
                      style={[
                        styles.progressBarFill,
                        {
                          width: `${(challenge.progress.days_completed / challenge.progress.total_days) * 100}%`,
                          backgroundColor: challenge.completed ? '#4CAF50' : theme.primary
                        }
                      ]}
                    />
                  </View>
                </View>

                {/* Tips */}
                {challenge.tips && challenge.tips.length > 0 && (
                  <View style={styles.tipsSection}>
                    <Text style={[styles.tipsLabel, { color: theme.text }]}>
                      Tips:
                    </Text>
                    {challenge.tips.map((tip, i) => (
                      <View key={i} style={styles.tipItem}>
                        <Ionicons name="checkmark-circle-outline" size={14} color={theme.success} />
                        <Text style={[styles.tipText, { color: theme.textSecondary }]}>
                          {tip}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Expected Impact */}
                <View style={[styles.impactContainer, { backgroundColor: '#E3F2FD' }]}>
                  <Ionicons name="trending-up" size={16} color="#1976D2" />
                  <Text style={[styles.impactText, { color: '#1976D2' }]}>
                    Expected: {challenge.expected_impact}
                  </Text>
                </View>

                {/* Complete Day Button */}
                {!challenge.completed && challenge.progress.is_active && (
                  <TouchableOpacity
                    style={[styles.completeDayButton, { backgroundColor: theme.primary }]}
                    onPress={() => handleCompleteDay(challenge.id)}
                  >
                    <Ionicons name="checkmark" size={20} color="#FFFFFF" />
                    <Text style={styles.completeDayText}>
                      Mark Today Complete
                    </Text>
                  </TouchableOpacity>
                )}

                {challenge.completed && (
                  <View style={[styles.completedMessage, { backgroundColor: '#E8F5E9' }]}>
                    <Ionicons name="trophy" size={20} color="#4CAF50" />
                    <Text style={[styles.completedMessageText, { color: '#2E7D32' }]}>
                      Challenge Completed! Great job!
                    </Text>
                  </View>
                )}
              </Card>
            ))}
          </>
        )}
      </ScrollView>
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
    padding: 8,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
  },
  refreshButton: {
    padding: 8,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  // Locked State
  lockedCard: {
    padding: 24,
    alignItems: 'center',
  },
  lockIconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  lockedTitle: {
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 8,
  },
  lockedDescription: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  previewChallenges: {
    width: '100%',
    marginBottom: 20,
  },
  previewLabel: {
    fontSize: 12,
    marginBottom: 8,
  },
  previewItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 10,
    borderRadius: 8,
    marginBottom: 6,
  },
  previewItemText: {
    fontSize: 14,
  },
  unlockButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    gap: 8,
    width: '100%',
  },
  unlockButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  // Empty State
  emptyCard: {
    padding: 32,
    alignItems: 'center',
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginTop: 16,
    marginBottom: 8,
  },
  emptyDescription: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
  },
  scanButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    gap: 8,
  },
  scanButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  // Section Intro
  sectionIntro: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },
  // Challenge Card
  challengeCard: {
    padding: 16,
    marginBottom: 16,
  },
  challengeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  metricIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  challengeInfo: {
    flex: 1,
    marginLeft: 12,
  },
  challengeTitle: {
    fontSize: 17,
    fontWeight: '700',
    marginBottom: 4,
  },
  challengeMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  difficultyBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  difficultyText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  durationText: {
    fontSize: 12,
  },
  completedBadge: {
    padding: 4,
    borderRadius: 12,
  },
  challengeDescription: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  whyContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
  },
  whyText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
  },
  dailyGoalContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  dailyGoalLabel: {
    fontSize: 14,
    fontWeight: '600',
  },
  dailyGoalText: {
    fontSize: 14,
    fontWeight: '500',
  },
  progressSection: {
    marginBottom: 12,
  },
  progressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  progressLabel: {
    fontSize: 13,
  },
  progressText: {
    fontSize: 13,
    fontWeight: '600',
  },
  progressBarContainer: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  tipsSection: {
    marginBottom: 12,
  },
  tipsLabel: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 6,
  },
  tipItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  tipText: {
    fontSize: 13,
  },
  impactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
  },
  impactText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
  },
  completeDayButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 10,
    gap: 8,
  },
  completeDayText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  completedMessage: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 12,
    borderRadius: 8,
  },
  completedMessageText: {
    fontSize: 14,
    fontWeight: '600',
  },
});
