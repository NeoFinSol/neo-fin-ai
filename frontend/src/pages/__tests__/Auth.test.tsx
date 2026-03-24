/**
 * Tests for Auth.tsx — API key validation
 * Requirements: pre-flight GET /analyses, error handling, success flow
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import { Auth } from '../Auth';

// Mock axios directly (Auth uses one-shot axios, not apiClient)
vi.mock('axios');
const mockedAxios = vi.mocked(axios);

// Mock AuthContext
const mockLogin = vi.fn();
vi.mock('../../context/AuthContext', () => ({
    useAuth: () => ({ login: mockLogin, isAuthenticated: false }),
}));

// Mock react-router-dom navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
        useLocation: () => ({ state: null, pathname: '/login' }),
    };
});

function renderAuth() {
    return render(
        <MantineProvider>
            <MemoryRouter>
                <Auth />
            </MemoryRouter>
        </MantineProvider>,
    );
}

beforeEach(() => {
    vi.clearAllMocks();
});

describe('Auth — API key validation', () => {
    it('shows error when key field is empty and form is submitted', async () => {
        renderAuth();
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));
        await waitFor(() => {
            expect(screen.getByText('Введите API ключ')).toBeInTheDocument();
        });
        expect(mockedAxios.get).not.toHaveBeenCalled();
    });

    it('calls GET /analyses with entered key as X-API-Key header', async () => {
        mockedAxios.get = vi.fn().mockResolvedValueOnce({ status: 200, data: {} });

        renderAuth();
        fireEvent.change(screen.getByPlaceholderText(/neofin/i), {
            target: { value: 'valid-key-abc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));

        await waitFor(() => {
            expect(mockedAxios.get).toHaveBeenCalledWith(
                expect.stringContaining('/analyses?page=1&page_size=1'),
                expect.objectContaining({
                    headers: { 'X-API-Key': 'valid-key-abc' },
                }),
            );
        });
    });

    it('calls login() and navigates on 200 response', async () => {
        mockedAxios.get = vi.fn().mockResolvedValueOnce({ status: 200, data: {} });

        renderAuth();
        fireEvent.change(screen.getByPlaceholderText(/neofin/i), {
            target: { value: 'valid-key-abc' },
        });
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));

        await waitFor(() => {
            expect(mockLogin).toHaveBeenCalledWith('valid-key-abc');
            expect(mockNavigate).toHaveBeenCalled();
        });
    });

    it('shows "Невалидный ключ" error on 401', async () => {
        mockedAxios.get = vi.fn().mockRejectedValueOnce({ response: { status: 401 } });

        renderAuth();
        fireEvent.change(screen.getByPlaceholderText(/neofin/i), {
            target: { value: 'wrong-key' },
        });
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));

        await waitFor(() => {
            expect(screen.getByText(/невалидный ключ/i)).toBeInTheDocument();
        });
        expect(mockLogin).not.toHaveBeenCalled();
    });

    it('shows "Невалидный ключ" error on 403', async () => {
        mockedAxios.get = vi.fn().mockRejectedValueOnce({ response: { status: 403 } });

        renderAuth();
        fireEvent.change(screen.getByPlaceholderText(/neofin/i), {
            target: { value: 'wrong-key' },
        });
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));

        await waitFor(() => {
            expect(screen.getByText(/невалидный ключ/i)).toBeInTheDocument();
        });
    });

    it('shows connection error when server is unreachable', async () => {
        mockedAxios.get = vi.fn().mockRejectedValueOnce({ response: undefined, message: 'Network Error' });

        renderAuth();
        fireEvent.change(screen.getByPlaceholderText(/neofin/i), {
            target: { value: 'some-key' },
        });
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));

        await waitFor(() => {
            expect(screen.getByText(/не удалось подключиться/i)).toBeInTheDocument();
        });
    });

    it('shows loading state while validating', async () => {
        // Never resolves — stays in loading
        mockedAxios.get = vi.fn().mockReturnValueOnce(new Promise(() => { }));

        renderAuth();
        fireEvent.change(screen.getByPlaceholderText(/neofin/i), {
            target: { value: 'some-key' },
        });
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));

        await waitFor(() => {
            expect(screen.getByText(/проверка ключа/i)).toBeInTheDocument();
        });
    });

    it('trims whitespace from key before sending', async () => {
        mockedAxios.get = vi.fn().mockResolvedValueOnce({ status: 200, data: {} });

        renderAuth();
        fireEvent.change(screen.getByPlaceholderText(/neofin/i), {
            target: { value: '  valid-key  ' },
        });
        fireEvent.click(screen.getByRole('button', { name: /войти/i }));

        await waitFor(() => {
            expect(mockedAxios.get).toHaveBeenCalledWith(
                expect.any(String),
                expect.objectContaining({
                    headers: { 'X-API-Key': 'valid-key' },
                }),
            );
        });
    });
});
