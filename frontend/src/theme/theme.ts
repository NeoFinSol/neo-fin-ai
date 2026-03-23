import { createTheme, MantineThemeOverride, rem } from '@mantine/core';

export const theme: MantineThemeOverride = createTheme({
  primaryColor: 'neofin',
  colors: {
    neofin: [
      '#eef2ff',
      '#e0e7ff',
      '#c7d2fe',
      '#a5b4fc',
      '#818cf8',
      '#6366f1',
      '#4f46e5',
      '#4338ca',
      '#00288e', // Primary
      '#1e40af', // Primary Container
    ],
  },
  fontFamily: 'Inter, sans-serif',
  fontFamilyMonospace: 'JetBrains Mono, monospace',
  headings: {
    fontFamily: 'Inter, sans-serif',
    fontWeight: '700',
  },
  spacing: {
    xs: rem(8),
    sm: rem(12),
    md: rem(16),
    lg: rem(24),
    xl: rem(32),
  },
  radius: {
    xs: rem(2),
    sm: rem(4),
    md: rem(6), // Design spec: 6px
    lg: rem(8),
    xl: rem(12),
  },
  components: {
    Container: {
      defaultProps: {
        size: 'xl',
      },
    },
    Card: {
      defaultProps: {
        padding: 'xl',
        radius: 'md',
        withBorder: false,
      },
      styles: {
        root: {
          backgroundColor: '#ffffff',
          border: 'none',
        },
      },
    },
    Paper: {
      defaultProps: {
        radius: 'md',
        withBorder: false,
      },
      styles: {
        root: {
          border: 'none',
        },
      },
    },
    Button: {
      defaultProps: {
        radius: 'md',
      },
      styles: (theme) => ({
        root: {
          border: 'none',
          backgroundImage: 'linear-gradient(135deg, #00288e 0%, #1e40af 100%)',
          color: '#ffffff',
          transition: 'transform 0.2s ease',
          '&:hover': {
            transform: 'translateY(-1px)',
          },
        },
      }),
    },
    Badge: {
      defaultProps: {
        radius: 'xl',
      },
      styles: {
        root: {
          border: 'none',
        },
      },
    },
    TextInput: {
      styles: {
        input: {
          backgroundColor: '#f3f4f5',
          border: '1px solid rgba(0, 0, 0, 0.05)',
          '&:focus': {
            borderColor: '#00288e',
          },
        },
      },
    },
  },
  other: {
    surfaces: {
      base: '#f8f9fa',
      containerLow: '#f3f4f5',
      containerLowest: '#ffffff',
    },
  },
});
