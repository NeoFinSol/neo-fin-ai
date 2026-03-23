import React, { createContext, useContext, useState, useEffect } from 'react';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  apiKey: string | null;
  login: (key: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [apiKey, setApiKey] = useState<string | null>(localStorage.getItem('neofin_api_key'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    // Simulate initial auth check (can be async API call later)
    setIsLoading(false);
  }, []);

  const login = (key: string) => {
    localStorage.setItem('neofin_api_key', key);
    setApiKey(key);
  };

  const logout = () => {
    localStorage.removeItem('neofin_api_key');
    setApiKey(null);
  };

  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'neofin_api_key') {
        setApiKey(e.newValue);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!apiKey, isLoading, apiKey, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
