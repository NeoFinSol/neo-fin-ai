import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { apiClient } from '../client';

// Mock localStorage
const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
        getItem: vi.fn((key: string) => store[key] || null),
        setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
        removeItem: vi.fn((key: string) => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; }),
    };
})();

Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
});

describe('apiClient', () => {
    beforeEach(() => {
        localStorageMock.clear();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('creates axios instance with correct base configuration', () => {
        expect(apiClient.defaults.baseURL).toBe('/api');
        expect(apiClient.defaults.headers['Content-Type']).toBe('application/json');
        expect(apiClient.defaults.timeout).toBe(120000);
    });

    it('adds X-API-Key header from localStorage when key exists', async () => {
        localStorageMock.getItem.mockReturnValue('test-api-key-123');
        
        const mockAdapter = vi.fn((config) => {
            return Promise.resolve({ data: {}, status: 200, statusText: 'OK', headers: {}, config });
        });
        apiClient.defaults.adapter = mockAdapter;
        
        await apiClient.get('/test');
        
        expect(localStorageMock.getItem).toHaveBeenCalledWith('neofin_api_key');
        const config = mockAdapter.mock.calls[0][0];
        expect(config.headers['X-API-Key']).toBe('test-api-key-123');
    });

    it('does not add X-API-Key header when localStorage is empty', async () => {
        localStorageMock.getItem.mockReturnValue(null);
        
        const mockAdapter = vi.fn((config) => {
            return Promise.resolve({ data: {}, status: 200, statusText: 'OK', headers: {}, config });
        });
        apiClient.defaults.adapter = mockAdapter;
        
        await apiClient.get('/test');
        
        const config = mockAdapter.mock.calls[0][0];
        expect(config.headers['X-API-Key']).toBeUndefined();
    });

    it('removes API key on 401 response', async () => {
        const mockAdapter = vi.fn((config) => {
            return Promise.reject({
                message: 'Unauthorized',
                response: { status: 401, data: { detail: 'Invalid API key' } },
                config
            });
        });
        apiClient.defaults.adapter = mockAdapter;
        
        await expect(apiClient.get('/protected')).rejects.toThrow();
        
        expect(localStorageMock.removeItem).toHaveBeenCalledWith('neofin_api_key');
    });

    it('handles network errors without response object', async () => {
        const mockAdapter = vi.fn((config) => {
            return Promise.reject({
                message: 'Network Error',
                isAxiosError: true,
                config
            });
        });
        apiClient.defaults.adapter = mockAdapter;
        
        await expect(apiClient.get('/test')).rejects.toThrow();
    });

    it('preserves error response data for handling', async () => {
        const errorData = { detail: 'Resource not found' };
        const mockAdapter = vi.fn((config) => {
            return Promise.reject({
                message: 'Not Found',
                response: { status: 404, data: errorData },
                config
            });
        });
        apiClient.defaults.adapter = mockAdapter;
        
        try {
            await apiClient.get('/nonexistent');
        } catch (error: any) {
            expect(error.response.data).toEqual(errorData);
        }
    });
});
