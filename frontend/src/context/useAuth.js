import { useContext } from 'react';
import { AuthContext } from './authContextDef';

/**
 * Custom hook to consume the AuthContext.
 * @returns {object} AuthContext values and actions
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
