import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export interface SkinIssue {
  name: string;
  severity: number;
  description: string;
}

export interface SkinAnalysisResult {
  skin_type: string;
  skin_type_description: string;
  issues: SkinIssue[];
  overall_score: number;
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

export interface ScanResult {
  id: string;
  analysis: SkinAnalysisResult;
  routine: SkincareRoutine;
  products: ProductRecommendation[];
  created_at: string;
  image_base64?: string;
}

export interface ScanHistoryItem {
  id: string;
  analysis: SkinAnalysisResult;
  created_at: string;
  has_image: boolean;
}

class SkinService {
  private getAuthHeader(token: string) {
    return { Authorization: `Bearer ${token}` };
  }

  async analyzeSkin(imageBase64: string, language: string, token: string): Promise<ScanResult> {
    const response = await axios.post(
      `${API_URL}/api/scan/analyze`,
      { image_base64: imageBase64, language },
      { headers: this.getAuthHeader(token) }
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
}

export const skinService = new SkinService();
