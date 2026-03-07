import axios from "axios";
import { useAuthStore } from "../stores/authStore";
import type {
  TokenResponse,
  UserListResponse,
  UserCreate,
  UserResponse,
  UserUpdate,
  TableListResponse,
  TableDetailResponse,
  TableCreate,
  TableResponse,
  BuyInRequest,
  BuyInResponse,
  CashOutRequest,
  CashOutResponse,
  TablePlayersResponse,
  TransactionListResponse,
  JackpotPoolListResponse,
  JackpotPoolCreate,
  JackpotPoolResponse,
  JackpotTriggerRequest,
  JackpotTriggerResponse,
  RecordHandResponse,
} from "../types";

const api = axios.create({ baseURL: "/api" });

// Request interceptor: attach JWT
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: auto-refresh on 401
let isRefreshing = false;
let pendingRequests: Array<(token: string) => void> = [];

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    const refreshToken = useAuthStore.getState().refreshToken;
    if (!refreshToken) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve) => {
        pendingRequests.push((token: string) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          resolve(api(originalRequest));
        });
      });
    }

    isRefreshing = true;
    originalRequest._retry = true;

    try {
      const res = await axios.post<TokenResponse>("/api/auth/refresh", {
        refresh_token: refreshToken,
      });
      const { access_token, refresh_token } = res.data;
      useAuthStore.getState().setTokens(access_token, refresh_token);

      pendingRequests.forEach((cb) => cb(access_token));
      pendingRequests = [];

      originalRequest.headers.Authorization = `Bearer ${access_token}`;
      return api(originalRequest);
    } catch {
      useAuthStore.getState().logout();
      window.location.href = "/login";
      return Promise.reject(error);
    } finally {
      isRefreshing = false;
    }
  },
);

// ---- Auth API ----
export const authApi = {
  login: (data: { username: string; password: string }) =>
    api.post<TokenResponse>("/auth/login", data),
};

// ---- Users API ----
export const usersApi = {
  list: () => api.get<UserListResponse>("/users"),
  create: (data: UserCreate) => api.post<UserResponse>("/users", data),
  update: (id: string, data: UserUpdate) =>
    api.patch<UserResponse>(`/users/${id}`, data),
};

// ---- Tables API ----
export const tablesApi = {
  list: (status?: string) =>
    api.get<TableListResponse>("/tables", {
      params: status ? { status } : undefined,
    }),
  get: (id: string) => api.get<TableDetailResponse>(`/tables/${id}`),
  create: (data: TableCreate) => api.post<TableResponse>("/tables", data),
  updateStatus: (id: string, status: string) =>
    api.patch<TableResponse>(`/tables/${id}/status`, { status }),
  unlock: (id: string, reason: string) =>
    api.patch<TableResponse>(`/tables/${id}/unlock`, { reason }),
  buyIn: (tableId: string, data: BuyInRequest) =>
    api.post<BuyInResponse>(`/tables/${tableId}/buy-in`, data),
  cashOut: (tableId: string, data: CashOutRequest) =>
    api.post<CashOutResponse>(`/tables/${tableId}/cash-out`, data),
  getPlayers: (tableId: string) =>
    api.get<TablePlayersResponse>(`/tables/${tableId}/players`),
  getTransactions: (tableId: string, playerId?: string) =>
    api.get<TransactionListResponse>(`/tables/${tableId}/transactions`, {
      params: playerId ? { player_id: playerId } : undefined,
    }),
};

// ---- Jackpot API ----
export const jackpotApi = {
  listPools: () => api.get<JackpotPoolListResponse>("/jackpot-pools"),
  createPool: (data: JackpotPoolCreate) =>
    api.post<JackpotPoolResponse>("/jackpot-pools", data),
  getPool: (id: string) =>
    api.get<JackpotPoolResponse>(`/jackpot-pools/${id}`),
  getPoolTriggers: (id: string) =>
    api.get<JackpotTriggerResponse[]>(`/jackpot-pools/${id}/triggers`),
  recordHand: (tableId: string) =>
    api.post<RecordHandResponse>(`/tables/${tableId}/jackpot/hand`),
  triggerPayout: (tableId: string, data: JackpotTriggerRequest) =>
    api.post<JackpotTriggerResponse>(
      `/tables/${tableId}/jackpot/trigger`,
      data,
    ),
};

export default api;
