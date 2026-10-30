# ARF Documentation Directory (`docs/`)

This directory houses the authoritative architecture records, product requirements, investment whitepapers, and operational plans for the ARF (AI Relevance Factor) platform.

---

## 1. Architecture Decision Records (ADRs)
* **[ADR-0001: Hybrid-Repo Single-Container Architecture for AI CIO Integration](file:///Users/sheng/Developer/ARF/docs/ADR_0001_HYBRID_REPO_SINGLE_CONTAINER_INTEGRATION.md)**: Architectural design detailing how `ARF` and `ai-hedge-fund` are built into a single Google Cloud Run container image using Git-pinned dependency resolution and an in-memory runtime data adapter.
* **[ADR-001: Lightweight Code-First Ontology & Deterministic Domain Modeling for AI Agents](file:///Users/sheng/Developer/ARF/docs/ADR-001-Next-Gen-Modeling-and-Lightweight-Ontology-for-Agents.md)**: Cross-repo architecture standard establishing the 4-element kinetic ontology, deterministic isolation, and lightweight tech stack across `BidAgent`, `Architect`, and `ARF`.

---

## 2. Product Specifications & Requirements
* **[ARF / AI-CIO Master Development Plan](file:///Users/sheng/Developer/ARF/docs/ARF_AI_CIO_DEVELOPMENT_PLAN.md)**: Master engineering plan and 4-phase execution roadmap covering the value-chain engine, multi-agent governance, and the continuous improvement loop.
* **[AI-CIO Value Chain Financial Modeling & Supply Chain Transmission](file:///Users/sheng/Developer/ARF/docs/AI_CIO_CONNECTING_THE_DOTS_FINANCIAL_MODELING.md)**: Deep dive on connecting the dots across companies, CapEx-to-revenue circuits, reverse-DCF $g^*$ harmonization, and 6 formal modeling paradigms (also available in [Chinese PDF](file:///Users/sheng/Developer/ARF/docs/AI_CIO_CONNECTING_THE_DOTS_FINANCIAL_MODELING_ZH.pdf)).
* **[ARF Digital Investment Analyst Vision](file:///Users/sheng/Developer/ARF/docs/ARF_DIGITAL_INVESTMENT_ANALYST_VISION.md)**: Vision, multi-agent supervisory architecture, and OODA continuous learning loop for the AI-CIO (also available in [Chinese PDF](file:///Users/sheng/Developer/ARF/docs/ARF_DIGITAL_INVESTMENT_ANALYST_VISION_ZH.pdf)).
* **[ARF PRD (Product Requirements Document)](file:///Users/sheng/Developer/ARF/docs/ARF_PRD.md)**: Complete specifications for Jensen Huang's 5-layer AI stack, universe definition (US and China legs), scoring formulas ($E_{score}$, $V_{score}$, and $ARF$), and calibration criteria.
* **[ARF Investor Whitepaper](file:///Users/sheng/Developer/ARF/docs/ARF_Investor_Whitepaper.md)**: Conceptual and mathematical foundation of the AI Relevance Factor for institutional investors.

---

## 3. Infrastructure & Engineering Plans
* **[ARF China Data Plan](file:///Users/sheng/Developer/ARF/docs/ARF_CHINA_DATA_PLAN.md)**: Blueprint for the domestic China financial data proxy (Tencent Cloud Lighthouse) and hybrid cross-cloud syncing architecture with Google Cloud Platform.

---

## 4. Engineering Reviews & Post-Mortems
* **[Architecture Review (2026-09-13)](file:///Users/sheng/Developer/ARF/docs/REVIEW_2026-09-13.md)**: System review and audit report for core pipeline milestones.
* **[Architecture Review (2026-10-21)](file:///Users/sheng/Developer/ARF/docs/REVIEW_2026-10-21.md)**: Progress and calibration review for hybrid cloud data integration and Gemini model screener.
