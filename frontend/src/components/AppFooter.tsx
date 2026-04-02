import { Box, Text } from '@mantine/core';

import { LEGAL_COPY } from '../constants/branding';

interface AppFooterProps {
    bordered?: boolean;
}

export function AppFooter({ bordered = false }: AppFooterProps) {
    return (
        <Box
            pt="xl"
            mt="xl"
            style={{
                borderTop: bordered ? '1px solid rgba(0, 0, 0, 0.06)' : 'none',
            }}
        >
            <Text ta="center" size="xs" c="dimmed">
                {LEGAL_COPY}
            </Text>
        </Box>
    );
}
