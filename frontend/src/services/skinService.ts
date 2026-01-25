import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export interface SkinIssue {
  name: string;
  severity: number;
  confidence?: number;
  description: string;
}

export interface ScoreFactor {
  issue: string;
  severity: number;
  severity_label: string;
  deduction: number;
}

export interface SkinAnalysisResult {
  skin_type: string;
  skin_type_confidence?: number;
  skin_type_description: string;
  issues: SkinIssue[];
  overall_score: number;
  score_label?: string;
  score_description?: string;
  score_factors?: ScoreFactor[];
  recommendations: string[];
}

export interface RoutineStep {
  order: number;
  step_name: string;
  product_type: string;
  instructions: string;
  ingredients_to_look_for: string[];
  ingredients_to_avoid: string[];
}

export interface SkincareRoutine {
  morning_routine: RoutineStep[];
  evening_routine: RoutineStep[];
  weekly_routine: RoutineStep[];
}

export interface ProductRecommendation {
  product_type: string;
  name: string;
  description: string;
  key_ingredients: string[];
  suitable_for: string[];
  price_range: string;
}

export interface ScoreData {
  score: number;
  label: string;
  description: string;
  factors: ScoreFactor[];
  base_score: number;
  total_deduction: number;
}

export interface FoodItem {
  name: string;
  reason: string;
}

export interface SupplementItem {
  name: string;
  reason: string;
}

export interface DietRecommendations {
  eat_more: FoodItem[];
  avoid: FoodItem[];
  hydration_tip: string;
  supplements_optional: SupplementItem[];
}

export interface ScanResult {
  id: string;
  analysis: SkinAnalysisResult;
  routine: SkincareRoutine;
  products: ProductRecommendation[];
  diet_recommendations?: DietRecommendations;
  created_at: string;
  image_base64?: string;
  image_hash?: string;
  score_data?: ScoreData;
}

export interface ScanHistoryItem {
  id: string;
  analysis: SkinAnalysisResult;
  score_data?: ScoreData;
  created_at: string;
  has_image: boolean;
  image_hash?: string;
}

export interface ScanComparison {
  scan1: {
    id: string;
    date: string;
    score: number;
  };
  scan2: {
    id: string;
    date: string;
    score: number;
  };
  score_change: number;
  score_improved: boolean;
  issue_changes: Array<{
    issue: string;
    old_severity: number;
    new_severity: number;
    change: number;
    improved: boolean;
  }>;
}

class SkinService {
  private getAuthHeader(token: string) {
    return { Authorization: `Bearer ${token}` };
  }

  async analyzeSkin(imageBase64: string, language: string, token: string): Promise<ScanResult> {
    const response = await axios.post(
      `${API_URL}/api/scan/analyze`,
      { image_base64: imageBase64, language },
      { headers: this.getAuthHeader(token), timeout: 120000 } // 2 minute timeout for AI analysis
    );
    return response.data;
  }

  async getScanHistory(token: string): Promise<ScanHistoryItem[]> {
    const response = await axios.get(`${API_URL}/api/scan/history`, {
      headers: this.getAuthHeader(token)
    });
    return response.data;
  }

  async getScanDetail(scanId: string, token: string): Promise<ScanResult> {
    const response = await axios.get(`${API_URL}/api/scan/${scanId}`, {
      headers: this.getAuthHeader(token)
    });
    return response.data;
  }

  async deleteScan(scanId: string, token: string): Promise<void> {
    await axios.delete(`${API_URL}/api/scan/${scanId}`, {
      headers: this.getAuthHeader(token)
    });
  }

  async compareScans(scanId1: string, scanId2: string, token: string): Promise<ScanComparison> {
    const response = await axios.get(`${API_URL}/api/scan/compare/${scanId1}/${scanId2}`, {
      headers: this.getAuthHeader(token)
    });
    return response.data;
  }
}

export const skinService = new SkinService();
