import { useState, useEffect, useCallback } from 'react';
import { getToken, setToken, getUser, setUser, clearAuth } from '../utils/tokenStorage';
import { loginApi, fetchCurrentUserApi } from '../api/auth';
import { AuthContext } from './authContextDef';

export function AuthProvider({ children }) {
  const [tokenState, setTokenState] = useState(() => getToken());
  const [userState, setUserState] = useState(() => getUser());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState(null);

  // Authoritative session verification on application startup
  useEffect(() => {
    let isMounted = true;

    async function hydrateSession() {
      const storedToken = getToken();
      if (!storedToken) {
        if (isMounted) {
          setUserState(null);
          setTokenState(null);
          setIsLoading(false);
        }
        return;
      }

      try {
        // Verify token validity against the authoritative backend /api/auth/me
        const profile = await fetchCurrentUserApi();
        if (isMounted) {
          setUserState(profile);
          setUser(profile);
          setTokenState(storedToken);
        }
      } catch {
        // Token was invalid, expired, or rejected
        clearAuth();
        if (isMounted) {
          setUserState(null);
          setTokenState(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    hydrateSession();

    // Subscribe to mid-session token expiration events dispatched by apiClient
    function handleSessionExpired(event) {
      if (!isMounted) return;
      clearAuth();
      setUserState(null);
      setTokenState(null);
      setSessionExpiredNotice(event?.detail?.reason || 'Your session has expired. Please sign in again.');
    }

    window.addEventListener('queueless:session-expired', handleSessionExpired);

    return () => {
      isMounted = false;
      window.removeEventListener('queueless:session-expired', handleSessionExpired);
    };
  }, []);

  const login = useCallback(async (email, password) => {
    setError(null);
    setSessionExpiredNotice(null);
    try {
      const response = await loginApi({ email, password });
      setToken(response.access_token);
      setUser(response.user);
      setTokenState(response.access_token);
      setUserState(response.user);
      return response.user;
    } catch (err) {
      const msg = err.message || 'Login failed. Please check your credentials.';
      setError(msg);
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setTokenState(null);
    setUserState(null);
    setError(null);
    setSessionExpiredNotice(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
    setSessionExpiredNotice(null);
  }, []);

  const value = {
    user: userState,
    token: tokenState,
    isAuthenticated: Boolean(tokenState && userState),
    isLoading,
    error,
    sessionExpiredNotice,
    login,
    logout,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
