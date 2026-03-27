import { useEffect, useRef, useCallback } from 'react';

export interface WSMessage {
  type: 'status_update' | 'progress_update';
  task_id?: string;
  session_id?: string;
  status: string;
  progress?: { completed: number; total: number } | number;
  result?: any;
  error?: string;
}

interface UseAnalysisSocketProps {
  taskId: string | null;
  onMessage: (message: WSMessage) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
  enabled?: boolean;
}

export const useAnalysisSocket = ({
  taskId,
  onMessage,
  onError,
  onClose,
  enabled = true,
}: UseAnalysisSocketProps) => {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 3;

  const connect = useCallback(() => {
    if (!taskId || !enabled) return;

    // Use current protocol (ws or wss)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // In dev, host is localhost:5173 (Vite). We use /api/ws which is proxied to backend.
    // The path in backend is /ws/{task_id}, but we use /api/ws/{task_id} to match Vite proxy.
    const wsUrl = `${protocol}//${host}/api/ws/${taskId}`;

    console.log(`Connecting to WebSocket: ${wsUrl}`);
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('WebSocket connected');
      reconnectAttempts.current = 0;
    };

    socket.onmessage = (event) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        onMessage(data);
      } catch (err) {
        console.error('Failed to parse WS message:', err);
      }
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (onError) onError(error);
    };

    socket.onclose = () => {
      console.log('WebSocket closed');
      if (onClose) onClose();

      // Simple reconnect logic
      if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts.current += 1;
        setTimeout(connect, 2000);
      }
    };

    socketRef.current = socket;
  }, [taskId, enabled, onMessage, onError, onClose]);

  useEffect(() => {
    connect();
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect]);

  return {
    socket: socketRef.current,
    isConnected: socketRef.current?.readyState === WebSocket.OPEN,
  };
};
