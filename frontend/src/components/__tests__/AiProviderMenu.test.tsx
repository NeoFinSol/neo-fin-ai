import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { MantineProvider } from '@mantine/core';

import { AiProviderMenu } from '../upload/AiProviderMenu';
import type { AIProvider } from '../../api/interfaces';

const wrapper = ({ children }: { children: React.ReactNode }) => (
    <MantineProvider>{children}</MantineProvider>
);

describe('AiProviderMenu', () => {
    it('renders current provider label', () => {
        render(
            <AiProviderMenu
                value="auto"
                options={['auto', 'gigachat', 'ollama']}
                onChange={() => {}}
            />,
            { wrapper },
        );

        expect(screen.getByText(/провайдер: авто/i)).toBeInTheDocument();
    });

    it('calls onChange when user selects another provider', async () => {
        const user = userEvent.setup();
        const onChange = vi.fn<(provider: AIProvider) => void>();

        render(
            <AiProviderMenu
                value="auto"
                options={['auto', 'gigachat', 'ollama']}
                onChange={onChange}
            />,
            { wrapper },
        );

        await user.click(screen.getByLabelText('Ollama'));

        expect(onChange).toHaveBeenCalledWith('ollama');
    });
});
