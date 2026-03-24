import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { AnalysisData } from '../api/interfaces';

export interface HistoryEntry {
  id: string;
  filename: string;
  date: string;
  score: number;
  riskLevel: string;
  result: AnalysisData;
}

interface HistoryContextType {
  history: HistoryEntry[];
  addEntry: (filename: string, result: AnalysisData) => void;
  removeEntry: (id: string) => void;
  clearHistory: () => void;
  getEntry: (id: string) => HistoryEntry | undefined;
}

const STORAGE_KEY = 'neofin_analysis_history';

const HistoryContext = createContext<HistoryContextType | undefined>(undefined);

function loadFromStorage(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export const HistoryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [history, setHistory] = useState<HistoryEntry[]>(loadFromStorage);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  const addEntry = useCallback((filename: string, result: AnalysisData) => {
    const entry: HistoryEntry = {
      id: crypto.randomUUID(),
      filename,
      date: new Date().toLocaleDateString('ru-RU'),
      score: result.score?.score ?? 0,
      riskLevel: result.score?.risk_level ?? 'medium',
      result,
    };
    setHistory((prev) => [entry, ...prev]);
  }, []);

  const removeEntry = useCallback((id: string) => {
    setHistory((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  const getEntry = useCallback(
    (id: string) => history.find((e) => e.id === id),
    [history],
  );

  return (
    <HistoryContext.Provider value={{ history, addEntry, removeEntry, clearHistory, getEntry }}>
      {children}
    </HistoryContext.Provider>
  );
};

export const useHistory = () => {
  const ctx = useContext(HistoryContext);
  if (!ctx) throw new Error('useHistory must be used inside HistoryProvider');
  return ctx;
};
