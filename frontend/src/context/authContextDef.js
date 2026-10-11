import { createContext } from 'react';

/**
 * Authoritative AuthContext instance.
 * Separated into a non-component module to maintain Fast Refresh compliance.
 */
export const AuthContext = createContext(null);
