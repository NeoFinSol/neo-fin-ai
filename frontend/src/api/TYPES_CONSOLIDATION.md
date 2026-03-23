// MIGRATION GUIDE: Consolidating API Types
// 
// BEFORE: Two conflicting files
//   - frontend/src/api/interfaces.ts (FinancialMetrics with number | null)
//   - frontend/src/api/types.ts (FinancialMetrics with number?)
//
// AFTER: Single source of truth
//   - frontend/src/api/interfaces.ts (use this)
//   - frontend/src/api/types.ts (DELETE this)
//
// ============================================================================
//
// ACTION ITEMS:
//
// 1. Delete: frontend/src/api/types.ts
//    rm frontend/src/api/types.ts
//
// 2. Update all imports in frontend/src/:
//    Find: import.*from.*types
//    Replace: import from ./interfaces
//
//    Files to check:
//    - frontend/src/api/client.ts
//    - frontend/src/pages/Dashboard.tsx
//    - frontend/src/pages/DetailedReport.tsx
//    - All other components using types
//
// 3. Standard pattern in interfaces.ts:
//
//    // Option A: Non-optional with null (RECOMMENDED)
//    interface FinancialMetrics {
//      revenue: number | null;      // Can be 0 or null
//      net_profit: number | null;
//    }
//
//    // Option B: Optional without null (if truly optional)
//    interface OptionalMetrics {
//      revenue?: number;            // Can be 0 or absent
//      net_profit?: number;
//    }
//
// 4. In components, use explicit null checks:
//
//    // ✅ GOOD - handles 0 correctly
//    const value = metrics.revenue !== null ? metrics.revenue : 'N/A';
//    
//    // ❌ BAD - treats 0 as missing
//    const value = metrics.revenue || 'N/A';
//
// 5. Verify with TypeScript:
//    npm run lint
//    npm run build
//
// ============================================================================
