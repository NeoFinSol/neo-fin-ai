import { afterEach, describe, expect, it, vi } from 'vitest';
import { generateTransactionId } from '../transactionId';

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('generateTransactionId', () => {
    it('uses crypto.randomUUID when available', () => {
        vi.stubGlobal('crypto', {
            randomUUID: () => '123e4567-e89b-12d3-a456-426614174000',
        });

        expect(generateTransactionId()).toBe('123E4567E89B');
    });

    it('falls back to deterministic seed when crypto is unavailable', () => {
        vi.stubGlobal('crypto', undefined);

        const first = generateTransactionId();
        const second = generateTransactionId();

        expect(first).toMatch(/^[0-9A-Z]{12}$/);
        expect(second).toMatch(/^[0-9A-Z]{12}$/);
        expect(second).not.toBe(first);
    });
});
