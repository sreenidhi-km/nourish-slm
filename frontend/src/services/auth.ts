import { apiClient } from './api';
import type { User, DietaryPreference } from '../types';

export const authService = {
  async register(name: string, email: string, password: string) {
    const res = await apiClient.post('/auth/register', { name, email, password });
    if (res.data.access_token) {
      localStorage.setItem('food_slm_token', res.data.access_token);
      localStorage.setItem('food_slm_user', JSON.stringify(res.data.user));
    }
    return res.data;
  },

  async login(email: string, password: string) {
    const res = await apiClient.post('/auth/login', { email, password });
    if (res.data.access_token) {
      localStorage.setItem('food_slm_token', res.data.access_token);
      localStorage.setItem('food_slm_user', JSON.stringify(res.data.user));
    }
    return res.data;
  },

  async logout() {
    try {
      await apiClient.post('/auth/logout');
    } catch (e) {
      // ignore
    }
    localStorage.removeItem('food_slm_token');
    localStorage.removeItem('food_slm_user');
  },

  async getProfile(): Promise<User> {
    const res = await apiClient.get('/user/profile');
    return res.data;
  },

  async updatePreference(preference: DietaryPreference): Promise<{ message: string; dietary_preference: DietaryPreference }> {
    const res = await apiClient.put('/user/preferences', { dietary_preference: preference });
    const storedUser = localStorage.getItem('food_slm_user');
    if (storedUser) {
      const u = JSON.parse(storedUser);
      u.dietary_preference = preference;
      localStorage.setItem('food_slm_user', JSON.stringify(u));
    }
    return res.data;
  },

  async updateAllergies(allergies: string[]): Promise<string[]> {
    const res = await apiClient.put('/user/allergies', { allergies });
    const storedUser = localStorage.getItem('food_slm_user');
    if (storedUser) {
      const u = JSON.parse(storedUser);
      u.allergies = res.data.allergies;
      localStorage.setItem('food_slm_user', JSON.stringify(u));
    }
    return res.data.allergies;
  },

  getStoredUser(): User | null {
    const u = localStorage.getItem('food_slm_user');
    return u ? JSON.parse(u) : null;
  }
};
