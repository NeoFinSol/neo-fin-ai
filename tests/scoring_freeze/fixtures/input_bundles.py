from tests.scoring_freeze.fixtures.models import (
    DocumentInputBundle,
    PrecomputedInputBundle,
)

DOCUMENT_INPUT_BUNDLES: tuple[DocumentInputBundle, ...] = (
    DocumentInputBundle(
        input_bundle_id="bundle-doc-period-marker",
        metrics={
            "revenue": 120000000.0,
            "net_profit": 5000000.0,
            "current_assets": 45000000.0,
            "short_term_liabilities": 42000000.0,
        },
        filename="q1_report_2026.pdf",
        text="Промежуточная отчетность за 1 квартал 2026",
        extraction_metadata=None,
        profile=None,
    ),
)

PRECOMPUTED_INPUT_BUNDLES: tuple[PrecomputedInputBundle, ...] = (
    PrecomputedInputBundle(
        input_bundle_id="bundle-pre-ru-label-coupling",
        metrics={
            "revenue": 120000000.0,
            "net_profit": 5000000.0,
            "current_assets": 45000000.0,
            "short_term_liabilities": 42000000.0,
            "equity": 70000000.0,
            "liabilities": 90000000.0,
        },
        ratios_ru={
            "Коэффициент текущей ликвидности": 1.07,
            "Рентабельность активов (ROA)": 0.12,
        },
        ratios_en={"current_ratio": 1.07, "roa": 0.12},
        methodology={"benchmark_profile": "generic", "period_basis": "reported"},
        extraction_metadata=None,
    ),
    PrecomputedInputBundle(
        input_bundle_id="bundle-pre-anomaly-helper-impact",
        metrics={
            "revenue": 120000000.0,
            "net_profit": 5000000.0,
            "current_assets": 45000000.0,
            "short_term_liabilities": 42000000.0,
            "equity": 70000000.0,
            "liabilities": 90000000.0,
        },
        ratios_ru={
            "Коэффициент текущей ликвидности": 1.07,
            "Рентабельность активов (ROA)": 9999.0,
        },
        ratios_en={"current_ratio": 1.07, "roa": 9999.0},
        methodology={"benchmark_profile": "generic", "period_basis": "reported"},
        extraction_metadata=None,
    ),
    PrecomputedInputBundle(
        input_bundle_id="bundle-pre-empty-factors-quirk",
        metrics={
            "revenue": None,
            "net_profit": None,
            "current_assets": None,
            "short_term_liabilities": None,
            "equity": None,
            "liabilities": None,
        },
        ratios_ru={},
        ratios_en={},
        methodology={"benchmark_profile": "generic", "period_basis": "reported"},
        extraction_metadata=None,
    ),
)

INPUT_BUNDLE_INDEX: dict[str, DocumentInputBundle | PrecomputedInputBundle] = {
    bundle.input_bundle_id: bundle
    for bundle in (*DOCUMENT_INPUT_BUNDLES, *PRECOMPUTED_INPUT_BUNDLES)
}
