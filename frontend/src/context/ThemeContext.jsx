import { useState, useEffect } from 'react';
import { ThemeContext } from './themeContextDef';

const THEME_STORAGE_KEY = 'queueless-theme';

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => {
    // 1. Check saved user preference in localStorage
    try {
      const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
      if (savedTheme === 'light' || savedTheme === 'dark') {
        return savedTheme;
      }
    } catch {
      // localStorage may be disabled
    }

    // 2. Check system OS color scheme preference
    if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }

    return 'light';
  });

  useEffect(() => {
    // Authoritatively synchronize HTML document attribute
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // ignore
    }
  }, [theme]);

  function toggleTheme() {
    setThemeState((prev) => (prev === 'light' ? 'dark' : 'light'));
  }

  function setTheme(newTheme) {
    if (newTheme === 'light' || newTheme === 'dark') {
      setThemeState(newTheme);
    }
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
