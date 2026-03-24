import { useState, useCallback, useEffect } from 'react';
import { AnalysisData } from '../api/interfaces';

export interface HistoryEntry {
  id: string;
  filename: string;
  date: string;
  score: number;
  riskLevel: string;
  result: AnalysisData;
}

const STORAGE_KEY = 'neofin_analysis_history';

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory(entries: HistoryEntry[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
}

export const useAnalysisHistory = () => {
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);

  useEffect(() => {
    saveHistory(history);
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

  const getEntry = useCallback((id: string): HistoryEntry | undefined => {
    return history.find((e) => e.id === id);
  }, [history]);

  return { history, addEntry, removeEntry, clearHistory, getEntry };
};
