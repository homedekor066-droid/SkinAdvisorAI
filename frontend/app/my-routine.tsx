import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTheme } from '../src/context/ThemeContext';
import { useI18n } from '../src/context/I18nContext';
import { useAuth } from '../src/context/AuthContext';
import { skinService } from '../src/services/skinService';
import { Card } from '../src/components';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { format, differenceInDays, startOfDay, isToday, isYesterday } from 'date-fns';

interface RoutineTask {
  id: string;
  name: string;
  type: 'morning' | 'evening' | 'weekly';
  completed: boolean;
  icon: string;
}

interface RoutineProgress {
  streak: number;
  lastCompletedDate: string | null;
  weeklyCompletionRate: number;
  totalTasksCompleted: number;
}

const DEFAULT_ROUTINE: RoutineTask[] = [
  { id: 'cleanser_am', name: 'Cleanser', type: 'morning', completed: false, icon: 'water-outline' },
  { id: 'toner_am', name: 'Toner', type: 'morning', completed: false, icon: 'flask-outline' },
  { id: 'serum_am', name: 'Serum', type: 'morning', completed: false, icon: 'sparkles-outline' },
  { id: 'moisturizer_am', name: 'Moisturizer', type: 'morning', completed: false, icon: 'leaf-outline' },
  { id: 'sunscreen', name: 'Sunscreen (SPF 30+)', type: 'morning', completed: false, icon: 'sunny-outline' },
  { id: 'cleanser_pm', name: 'Cleanser', type: 'evening', completed: false, icon: 'water-outline' },
  { id: 'treatment', name: 'Treatment', type: 'evening', completed: false, icon: 'medical-outline' },
  { id: 'moisturizer_pm', name: 'Night Cream', type: 'evening', completed: false, icon: 'moon-outline' },
  { id: 'exfoliate', name: 'Exfoliate', type: 'weekly', completed: false, icon: 'refresh-outline' },
  { id: 'mask', name: 'Face Mask', type: 'weekly', completed: false, icon: 'happy-outline' },
];

export default function MyRoutineScreen() {
  const { theme } = useTheme();
  const { t } = useI18n();
  const { token, user } = useAuth();
  const router = useRouter();
  
  const [tasks, setTasks] = useState<RoutineTask[]>(DEFAULT_ROUTINE);
  const [progress, setProgress] = useState<RoutineProgress>({
    streak: 0,
    lastCompletedDate: null,
    weeklyCompletionRate: 0,
    totalTasksCompleted: 0,
  });
  const [refreshing, setRefreshing] = useState(false);
  const [lastScanDate, setLastScanDate] = useState<Date | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [serverProgress, setServerProgress] = useState<{
    streak: number;
    bonus_points: number;
    total_days_completed: number;
  }>({ streak: 0, bonus_points: 0, total_days_completed: 0 });

  const isPremium = user?.plan === 'premium';
  
  // CRITICAL: Only use user-specific storage keys when user.id is available
  // This prevents data from being saved/loaded under 'guest' key
  const userId = user?.id;
  const getStorageKey = (prefix: string) => userId ? `${prefix}_${userId}` : null;

  // Load saved routine state - only when user is authenticated
  useEffect(() => {
    if (userId && token) {
      console.log('[MyRoutine] Loading state for user:', userId);
      loadRoutineState();
      checkLastScanDate();
      fetchServerProgress();
      setIsReady(true);
    }
  }, [userId, token]);

  const fetchServerProgress = async () => {
    if (!token) return;
    try {
      const progress = await skinService.getRoutineProgress(token);
      setServerProgress({
        streak: progress.streak,
        bonus_points: progress.bonus_points,
        total_days_completed: progress.total_days_completed
      });
    } catch (error) {
      console.error('Failed to fetch server progress:', error);
    }
  };

  const loadRoutineState = async () => {
    const tasksKey = getStorageKey('routine_tasks');
    const progressKey = getStorageKey('routine_progress');
    const dateKey = getStorageKey('routine_date');
    
    // Don't proceed if user is not loaded yet
    if (!tasksKey || !progressKey || !dateKey) {
      console.log('[MyRoutine] Skipping load - user not ready');
      return;
    }
    
    try {
      console.log('[MyRoutine] Loading from keys:', { tasksKey, progressKey, dateKey });
      
      const savedTasks = await AsyncStorage.getItem(tasksKey);
      const savedProgress = await AsyncStorage.getItem(progressKey);
      const savedDate = await AsyncStorage.getItem(dateKey);
      
      const today = format(new Date(), 'yyyy-MM-dd');
      
      // If saved date is not today, reset daily tasks but keep streak
      if (savedDate !== today) {
        // Check if streak should continue
        if (savedProgress) {
          const parsedProgress = JSON.parse(savedProgress);
          const lastDate = parsedProgress.lastCompletedDate;
          
          if (lastDate) {
            const daysDiff = differenceInDays(new Date(), new Date(lastDate));
            if (daysDiff > 1) {
              // Streak broken
              setProgress(prev => ({ ...prev, streak: 0 }));
            }
          }
        }
        
        // Reset tasks for new day
        setTasks(DEFAULT_ROUTINE);
        await AsyncStorage.setItem(dateKey, today);
      } else if (savedTasks) {
        setTasks(JSON.parse(savedTasks));
      }
      
      if (savedProgress) {
        setProgress(JSON.parse(savedProgress));
      }
    } catch (error) {
      console.error('Failed to load routine state:', error);
    }
  };

  const checkLastScanDate = async () => {
    if (!token) return;
    try {
      const scans = await skinService.getScanHistory(token);
      if (scans.length > 0) {
        setLastScanDate(new Date(scans[0].created_at));
      }
    } catch (error) {
      console.error('Failed to check scan history:', error);
    }
  };

  const saveRoutineState = async (newTasks: RoutineTask[], newProgress: RoutineProgress) => {
    const tasksKey = getStorageKey('routine_tasks');
    const progressKey = getStorageKey('routine_progress');
    const dateKey = getStorageKey('routine_date');
    
    // Don't save if user is not loaded
    if (!tasksKey || !progressKey || !dateKey) {
      console.log('[MyRoutine] Skipping save - user not ready');
      return;
    }
    
    try {
      console.log('[MyRoutine] Saving to keys:', { tasksKey, progressKey, dateKey });
      await AsyncStorage.setItem(tasksKey, JSON.stringify(newTasks));
      await AsyncStorage.setItem(progressKey, JSON.stringify(newProgress));
      await AsyncStorage.setItem(dateKey, format(new Date(), 'yyyy-MM-dd'));
    } catch (error) {
      console.error('Failed to save routine state:', error);
    }
  };

  const toggleTask = async (taskId: string) => {
    if (!isPremium) {
      Alert.alert(
        'Premium Feature',
        'Track your daily routine progress with Premium.',
        [
          { text: 'Later', style: 'cancel' },
          { text: 'Upgrade', onPress: () => router.push('/paywall') }
        ]
      );
      return;
    }

    const newTasks = tasks.map(task =>
      task.id === taskId ? { ...task, completed: !task.completed } : task
    );
    setTasks(newTasks);

    // Calculate completion and update progress
    const completedCount = newTasks.filter(t => t.completed).length;
    const completionRate = Math.round((completedCount / newTasks.length) * 100);
    
    let newStreak = progress.streak;
    const allDailyComplete = newTasks
      .filter(t => t.type !== 'weekly')
      .every(t => t.completed);
    
    // If all daily tasks completed, sync with server
    if (allDailyComplete && !isToday(new Date(progress.lastCompletedDate || 0))) {
      try {
        const result = await skinService.completeRoutineDay(token!);
        newStreak = result.streak;
        setServerProgress(prev => ({
          ...prev,
          streak: result.streak,
          bonus_points: result.total_bonus,
          total_days_completed: result.total_days_completed
        }));
        
        // Show bonus notification if earned
        if (result.bonus_earned > 0) {
          Alert.alert(
            '🎉 Bonus Points Earned!',
            result.message,
            [{ text: 'Awesome!', style: 'default' }]
          );
        }
      } catch (error) {
        console.error('Failed to sync with server:', error);
        newStreak = progress.streak + 1;
      }
    }

    const newProgress: RoutineProgress = {
      streak: newStreak,
      lastCompletedDate: allDailyComplete ? new Date().toISOString() : progress.lastCompletedDate,
      weeklyCompletionRate: completionRate,
      totalTasksCompleted: progress.totalTasksCompleted + (newTasks.find(t => t.id === taskId)?.completed ? 1 : -1),
    };
    
    setProgress(newProgress);
    await saveRoutineState(newTasks, newProgress);
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadRoutineState();
    await checkLastScanDate();
    setRefreshing(false);
  }, [token]);

  // Calculate today's progress
  const morningTasks = tasks.filter(t => t.type === 'morning');
  const eveningTasks = tasks.filter(t => t.type === 'evening');
  const weeklyTasks = tasks.filter(t => t.type === 'weekly');
  
  const morningCompleted = morningTasks.filter(t => t.completed).length;
  const eveningCompleted = eveningTasks.filter(t => t.completed).length;
  const dailyProgress = Math.round(((morningCompleted + eveningCompleted) / (morningTasks.length + eveningTasks.length)) * 100);

  // Check if weekly scan is due
  const showWeeklyScanReminder = lastScanDate && differenceInDays(new Date(), lastScanDate) >= 7;

  const renderTaskItem = (task: RoutineTask) => (
    <TouchableOpacity
      key={task.id}
      style={[
        styles.taskItem,
        { backgroundColor: task.completed ? theme.success + '15' : theme.surface },
        !isPremium && styles.taskItemLocked
      ]}
      onPress={() => toggleTask(task.id)}
    >
      <View style={[styles.taskIcon, { backgroundColor: task.completed ? theme.success + '20' : theme.primary + '15' }]}>
        <Ionicons 
          name={task.icon as any} 
          size={20} 
          color={task.completed ? theme.success : theme.primary} 
        />
      </View>
      <Text style={[styles.taskName, { color: theme.text }]}>{task.name}</Text>
      <View style={[
        styles.checkbox,
        { borderColor: task.completed ? theme.success : theme.border },
        task.completed && { backgroundColor: theme.success }
      ]}>
        {task.completed && <Ionicons name="checkmark" size={16} color="#FFFFFF" />}
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={theme.text} />
        </TouchableOpacity>
        <Text style={[styles.title, { color: theme.text }]}>My Routine</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Weekly Scan Reminder */}
        {showWeeklyScanReminder && (
          <TouchableOpacity 
            style={[styles.reminderBanner, { backgroundColor: '#E3F2FD' }]}
            onPress={() => router.push('/(tabs)/scan')}
          >
            <Ionicons name="scan-outline" size={24} color="#1976D2" />
            <View style={styles.reminderText}>
              <Text style={[styles.reminderTitle, { color: '#1976D2' }]}>
                Weekly Skin Scan Ready
              </Text>
              <Text style={[styles.reminderSubtitle, { color: '#0D47A1' }]}>
                Track your progress with a new scan
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#1976D2" />
          </TouchableOpacity>
        )}

        {/* Progress Stats */}
        <View style={styles.statsRow}>
          <Card style={[styles.statCard, { flex: 1, marginRight: 8 }]}>
            <Text style={[styles.statValue, { color: theme.primary }]}>
              {serverProgress.streak > 0 ? serverProgress.streak : progress.streak}
            </Text>
            <Text style={[styles.statLabel, { color: theme.textSecondary }]}>Day Streak 🔥</Text>
          </Card>
          <Card style={[styles.statCard, { flex: 1, marginLeft: 8 }]}>
            <Text style={[styles.statValue, { color: theme.success }]}>{dailyProgress}%</Text>
            <Text style={[styles.statLabel, { color: theme.textSecondary }]}>Today</Text>
          </Card>
        </View>

        {/* Bonus Points Card (only show if bonus points > 0) */}
        {serverProgress.bonus_points > 0 && (
          <Card style={[styles.bonusCard, { backgroundColor: '#FFF8E1' }]}>
            <View style={styles.bonusContent}>
              <Ionicons name="star" size={24} color="#FFB300" />
              <View style={styles.bonusTextContainer}>
                <Text style={[styles.bonusTitle, { color: '#FF8F00' }]}>
                  +{serverProgress.bonus_points} Bonus Points Earned!
                </Text>
                <Text style={[styles.bonusSubtitle, { color: '#5D4037' }]}>
                  Keep your streak for more bonuses (every 7 days)
                </Text>
              </View>
            </View>
          </Card>
        )}

        {/* Next Bonus Progress */}
        {isPremium && serverProgress.streak > 0 && (
          <Card style={[styles.nextBonusCard, { backgroundColor: theme.surface }]}>
            <View style={styles.nextBonusHeader}>
              <Text style={[styles.nextBonusTitle, { color: theme.text }]}>
                Next Bonus: {7 - (serverProgress.streak % 7)} days
              </Text>
              <Text style={[styles.nextBonusPoints, { color: theme.primary }]}>+3 pts</Text>
            </View>
            <View style={[styles.progressBar, { backgroundColor: theme.border }]}>
              <View 
                style={[
                  styles.progressFill, 
                  { 
                    backgroundColor: theme.primary,
                    width: `${((serverProgress.streak % 7) / 7) * 100}%` 
                  }
                ]} 
              />
            </View>
          </Card>
        )}

        {/* Morning Routine */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="sunny" size={20} color="#FFC107" />
            <Text style={[styles.sectionTitle, { color: theme.text }]}>Morning Routine</Text>
            <Text style={[styles.sectionProgress, { color: theme.textSecondary }]}>
              {morningCompleted}/{morningTasks.length}
            </Text>
          </View>
          {morningTasks.map(renderTaskItem)}
        </View>

        {/* Evening Routine */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="moon" size={20} color="#7C4DFF" />
            <Text style={[styles.sectionTitle, { color: theme.text }]}>Evening Routine</Text>
            <Text style={[styles.sectionProgress, { color: theme.textSecondary }]}>
              {eveningCompleted}/{eveningTasks.length}
            </Text>
          </View>
          {eveningTasks.map(renderTaskItem)}
        </View>

        {/* Weekly Tasks */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="calendar" size={20} color="#00BCD4" />
            <Text style={[styles.sectionTitle, { color: theme.text }]}>Weekly</Text>
          </View>
          {weeklyTasks.map(renderTaskItem)}
        </View>

        {/* Premium Lock */}
        {!isPremium && (
          <TouchableOpacity 
            style={[styles.premiumBanner, { backgroundColor: theme.primary }]}
            onPress={() => router.push('/paywall')}
          >
            <Ionicons name="lock-closed" size={24} color="#FFFFFF" />
            <View style={styles.premiumBannerText}>
              <Text style={styles.premiumBannerTitle}>
                Unlock Routine Tracking
              </Text>
              <Text style={styles.premiumBannerSubtitle}>
                Track habits, build streaks, improve your skin
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={24} color="#FFFFFF" />
          </TouchableOpacity>
        )}

        <View style={{ height: 40 }} />
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
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  reminderBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 12,
    marginBottom: 20,
  },
  reminderText: {
    flex: 1,
    marginLeft: 12,
  },
  reminderTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  reminderSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  statsRow: {
    flexDirection: 'row',
    marginBottom: 20,
  },
  statCard: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  statValue: {
    fontSize: 32,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 13,
    marginTop: 4,
  },
  // Bonus Cards
  bonusCard: {
    marginBottom: 16,
    borderRadius: 12,
    padding: 16,
  },
  bonusContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  bonusTextContainer: {
    flex: 1,
    marginLeft: 12,
  },
  bonusTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  bonusSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  nextBonusCard: {
    marginBottom: 20,
    padding: 16,
    borderRadius: 12,
  },
  nextBonusHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  nextBonusTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  nextBonusPoints: {
    fontSize: 14,
    fontWeight: '700',
  },
  progressBar: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 4,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 17,
    fontWeight: '600',
    marginLeft: 8,
    flex: 1,
  },
  sectionProgress: {
    fontSize: 14,
    fontWeight: '500',
  },
  taskItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    marginBottom: 8,
  },
  taskItemLocked: {
    opacity: 0.6,
  },
  taskIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  taskName: {
    flex: 1,
    fontSize: 15,
    fontWeight: '500',
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
  premiumBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 16,
    marginTop: 10,
  },
  premiumBannerText: {
    flex: 1,
    marginLeft: 12,
  },
  premiumBannerTitle: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  premiumBannerSubtitle: {
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: 13,
    marginTop: 2,
  },
});
