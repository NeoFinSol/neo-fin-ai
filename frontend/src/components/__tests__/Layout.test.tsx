import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router-dom';

import { Layout } from '../Layout';

vi.mock('../../context/AuthContext', () => ({
    useAuth: () => ({
        logout: vi.fn(),
    }),
}));

describe('Layout', () => {
    it('renders localized navigation and updated footer branding', () => {
        render(
            <MantineProvider>
                <MemoryRouter>
                    <Layout />
                </MemoryRouter>
            </MantineProvider>,
        );

        expect(screen.getByText('НеоФин.Документы')).toBeInTheDocument();
        expect(screen.getByText('Меню')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Главная' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'История' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Настройки' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Выход' })).toBeInTheDocument();
        expect(screen.getByText(/НеоФин\. Все права защищены, 2026\./i)).toBeInTheDocument();
    });
});
