import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';

import { SettingsPage } from '../SettingsPage';

describe('SettingsPage', () => {
    it('renders localized settings sections and primary actions', () => {
        render(
            <MantineProvider>
                <SettingsPage />
            </MantineProvider>,
        );

        expect(screen.getByRole('heading', { name: 'Настройки' })).toBeInTheDocument();
        expect(screen.getAllByText(/НеоФин\.Документы/).length).toBeGreaterThan(0);
        expect(screen.getByRole('tab', { name: 'Профиль' })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: 'Безопасность' })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: 'API-ключи' })).toBeInTheDocument();
        expect(screen.getByRole('tab', { name: 'Тариф' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Сохранить изменения' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Отменить' })).toBeInTheDocument();
    });
});
