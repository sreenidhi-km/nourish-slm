import { apiClient } from './api';
import type {
  CategoryDetail, DietCategoryGroup, DietChatMessage, DietOptions, DietPlan, DietPlanSummary, DietProfile,
  Paginated, RecipeSummary, UsdaFood, Assessment, PlanTotals, Targets,
} from '../types/diet';

/** Turns an axios error into a readable message for the UI. */
export function apiErrorMessage(err: unknown, fallback = 'Something went wrong. Please try again.'): string {
  const e = err as { response?: { status?: number; data?: { detail?: unknown } }; message?: string };
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string };
    if (first?.msg) return first.msg;
  }
  if (!e?.response) return 'Cannot reach the Nourish server. Check that the backend is running.';
  return fallback;
}

export const dietService = {
  async getCategories(): Promise<{ groups: DietCategoryGroup[]; data_available: boolean }> {
    return (await apiClient.get('/diet/categories')).data;
  },
  async getCategory(key: string): Promise<CategoryDetail> {
    return (await apiClient.get(`/diet/categories/${key}`)).data;
  },
  async getOptions(): Promise<DietOptions> {
    return (await apiClient.get('/diet/options')).data;
  },
  async createPlan(categoryKey: string, profile: Partial<DietProfile>): Promise<DietPlan> {
    return (await apiClient.post('/diet/plans', { category_key: categoryKey, profile })).data;
  },
  async listPlans(savedOnly = false): Promise<DietPlanSummary[]> {
    return (await apiClient.get('/diet/plans', { params: { saved_only: savedOnly } })).data;
  },
  async getPlan(id: string): Promise<DietPlan> {
    return (await apiClient.get(`/diet/plans/${id}`)).data;
  },
  async savePlan(id: string, name: string, isSaved = true): Promise<DietPlan> {
    return (await apiClient.put(`/diet/plans/${id}`, { name, is_saved: isSaved })).data;
  },
  async deletePlan(id: string) {
    return (await apiClient.delete(`/diet/plans/${id}`)).data;
  },
  async editPlan(id: string, op: Record<string, unknown>, version?: number): Promise<DietPlan> {
    return (await apiClient.post(`/diet/plans/${id}/edit`, { ...op, version })).data;
  },
  async assess(id: string): Promise<{ assessment: Assessment; totals: PlanTotals; targets: Targets; version: number }> {
    return (await apiClient.post(`/diet/plans/${id}/assess`)).data;
  },
  async alternatives(id: string, params: { meal_id?: string; slot?: string; q?: string; focus?: string; cuisine?: string; page?: number }):
    Promise<Paginated<RecipeSummary>> {
    return (await apiClient.get(`/diet/plans/${id}/alternatives`, { params })).data;
  },
  async searchIngredients(q: string): Promise<UsdaFood[]> {
    return (await apiClient.get('/diet/ingredients/search', { params: { q } })).data.items;
  },
  async getChat(id: string): Promise<{ assistant_name: string; messages: DietChatMessage[] }> {
    return (await apiClient.get(`/diet/plans/${id}/chat`)).data;
  },
  async sendChat(id: string, message: string): Promise<{ user_message: DietChatMessage; reply: DietChatMessage }> {
    return (await apiClient.post(`/diet/plans/${id}/chat`, { message })).data;
  },
  async applyProposal(id: string, messageId: number, proposalId: string):
    Promise<{ plan: DietPlan; message: DietChatMessage; confirmation: DietChatMessage }> {
    return (await apiClient.post(`/diet/plans/${id}/chat/${messageId}/apply`, { proposal_id: proposalId })).data;
  },
};
