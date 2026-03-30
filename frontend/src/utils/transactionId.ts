let fallbackCounter = 0;

function nextFallbackSeed(): string {
    fallbackCounter = (fallbackCounter + 1) % 46656;
    const timestamp = Date.now().toString(36).toUpperCase();
    const perf = typeof performance !== 'undefined'
        ? Math.floor(performance.now()).toString(36).toUpperCase()
        : '0';
    const counter = fallbackCounter.toString(36).toUpperCase().padStart(3, '0');
    return `${timestamp}${perf}${counter}`;
}

export function generateTransactionId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID().replace(/-/g, '').slice(0, 12).toUpperCase();
    }

    return nextFallbackSeed().slice(-12).padStart(12, '0');
}
