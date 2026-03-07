import { create } from "zustand";
import axios from "axios";
import type { TokenResponse } from "../types";

interface AuthUser {
  id: string;
  role: string;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  hydrate: () => void;
}

function parseJwtPayload(token: string): Record<string, unknown> {
  const base64 = token.split(".")[1];
  const json = atob(base64);
  return JSON.parse(json);
}

function userFromToken(token: string): AuthUser {
  const payload = parseJwtPayload(token);
  return {
    id: payload.sub as string,
    role: payload.role as string,
  };
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,

  login: async (username: string, password: string) => {
    const res = await axios.post<TokenResponse>("/api/auth/login", {
      username,
      password,
    });
    const { access_token, refresh_token } = res.data;
    localStorage.setItem("access_token", access_token);
    localStorage.setItem("refresh_token", refresh_token);
    set({
      accessToken: access_token,
      refreshToken: refresh_token,
      user: userFromToken(access_token),
    });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, accessToken: null, refreshToken: null });
  },

  setTokens: (accessToken: string, refreshToken: string) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    set({
      accessToken,
      refreshToken,
      user: userFromToken(accessToken),
    });
  },

  hydrate: () => {
    const accessToken = localStorage.getItem("access_token");
    const refreshToken = localStorage.getItem("refresh_token");
    if (accessToken && refreshToken) {
      try {
        set({
          accessToken,
          refreshToken,
          user: userFromToken(accessToken),
        });
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
    }
  },
}));
