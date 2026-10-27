import { apiClient } from './api';
import type { ChatSession, Message, DietaryPreference } from '../types';

export const chatService = {
  async sendMessage(message: string, preference?: DietaryPreference, cuisine?: string, chatId?: string, allergies?: string[]) {
    const res = await apiClient.post('/chat', {
      message,
      preference,
      cuisine,
      chat_id: chatId,
      allergies,
    });
    return res.data;
  },

  async getHistory(): Promise<ChatSession[]> {
    const res = await apiClient.get('/chat/history');
    return res.data;
  },

  async getChatSession(chatId: string): Promise<{ id: string; title: string; messages: Message[] }> {
    const res = await apiClient.get(`/chat/${chatId}`);
    return res.data;
  },

  async deleteChatSession(chatId: string) {
    const res = await apiClient.delete(`/chat/${chatId}`);
    return res.data;
  }
};
