# IDC Positions Strategic Assessment & 3-Tier Application Playbook

**Target Organization:** International Data Corporation (IDC / IDC咨询(北京)有限公司)  
**Location:** Beijing, China  
**Date:** November 2026  
**Candidate:** Sheng Jiang  
**Live Platform Showcase:** [https://stock.thekingfilter.com/IDC_MarketScape](https://stock.thekingfilter.com/IDC_MarketScape)  

---

## 1. Executive Context: Navigating IDC Beijing & Market "内卷"

Three distinct openings are currently active for IDC Beijing:
1. **Role 1:** `Vice President - AI, Software & Data Management` (Global / APAC Research & Advisory Track) — *Open for months, 55+ applicants*
2. **Role 2:** `Vice President, Technology & AI Enablement` (China In-House Platform & Tech Leadership) — *Open for months, 74+ applicants*
3. **Role 3:** `Program Manager, Enterprise AI Platform - China (Contract)` (Quanta Platform Delivery Lead) — *Posted 2 weeks ago, **only 2 applicants***

### The Chinese Job Market Reality ("内卷" vs. Operational Urgency)
* **The VP Committee Bottleneck:**  
  For senior VP positions in Beijing, MNCs frequently face committee paralysis, headhunter screening delays, and lengthy global sign-offs. Positions often sit unfilled for 3–6 months while internal stakeholders debate budgets or organizational design.
* **The Tactical Goldmine (Role 3):**  
  In contrast, the 1-year Contract Program Manager role has **only 2 applicants in two weeks**. In China's job market, many senior professionals avoid the "Contract" label due to face or stability concerns, while mid-level PMs lack the rare cross-border skillset required (China data compliance, US-approved evaluation thresholds, hybrid cloud architectures, and bilingual fluency).
* **The "Trojan Horse" Strategy:**  
  Role 3 is not an isolated project; it is the **hands-on delivery of the Quanta China Enterprise AI Platform** that Role 2 oversees. The JD explicitly notes: *"there could be an opportunity to hire at the end"*. Delivering this program from Day 1 establishes immediate credibility, puts you in daily contact with IDC China executive sponsors and the US technical product owner, and creates a direct internal track to a permanent Director or VP role.

---

## 2. Comparative Matrix: 3 Roles Side-by-Side

| Dimension | **Role 1: VP - AI, Software & Data** | **Role 2: VP, Technology & AI** | **Role 3: Program Manager, AI Platform (Contract)** |
| :--- | :--- | :--- | :--- |
| **Mandate** | External Thought Leadership, TAM sizing, MarketScape evaluations, C-suite advisory. | APAC/China technology stack, overall Quanta China ownership, vendor/cloud governance. | **Hands-on phased execution**: cloud provisioning, model evaluation, regulatory filings, go-live. |
| **Compensation** | Senior Executive Band (Advisory / Research). | **100K – 130K CNY/month** (~1.2M – 1.56M/yr). | **40K – 45K CNY/month** (~480K – 540K/yr contract). |
| **Competition** | High competition (55+ applicants), slow cycle. | High competition (74+ applicants), slow cycle. | **Near zero (2 applicants)**, immediate hiring need. |
| **Primary Stakeholder**| Global C-suites, tech vendor CEOs, investors. | IDC APAC MD, global engineering, cloud partners. | US Technical Product Owner, China Country Lead. |
| **ARF Alignment** | **100% Research & Market Sizing Match**: 5-layer stack, Leontief shock model, MarketScape matrix. | **100% Platform Architecture Match**: Hybrid cloud (GCP + Tencent), multi-model integration. | **100% Execution Checklist Match**: Network isolation, zero data leakage, pass/fail evaluation harnesses. |

---

## 3. The 3-Tier Multi-Track Application Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           3-Tier Campaign Funnel                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 1 (External Authority) : VP - AI, Software & Data Management          │
│  • Position as the premier authority on AI market sizing & bubble dynamics  │
│  • Leverages the live IDC MarketScape engine & Worldwide Spending Guide     │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 2 (Tactical Trojan Horse): Program Manager, Enterprise AI Platform    │
│  • Immediate application to bypass "内卷" and win the unfilled slot         │
│  • Solves their urgent Quanta China delivery & model evaluation problem     │
│  • 1-year runway with explicit hire-to-perm conversion opportunity          │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIER 3 (Strategic Technology): VP, Technology & AI Enablement              │
│  • Long-term executive track; raised naturally during interviews for Role 3 │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Submit for Role 3 Immediately**:  
   Target the recruiter / hiring manager with the hands-on delivery narrative. An overqualified candidate with ready-to-deploy hybrid cloud experience will instantly jump to the top of the 2-person applicant queue.
2. **Submit for Role 1 Simultaneously**:  
   Submit the executive thought-leadership cover letter highlighting the live [stock.thekingfilter.com/IDC_MarketScape](https://stock.thekingfilter.com/IDC_MarketScape) platform to the research practice lead.
3. **Cross-Leverage in the Recruiter Screening**:  
   When the recruiter calls, state: *"I noticed both the Enterprise AI Program Manager delivery role and the Technology VP role. Because I have hands-on experience deploying cross-border hybrid cloud and evaluating China-approved LLMs, I can step in immediately to deliver the platform while bringing senior architectural vision."*

---

## 4. Technical Mapping for Role 3 (Program Manager)

The JD’s exact requirements map directly to what we engineered in ARF:

| JD Core Requirement | Production Evidence in ARF |
| :--- | :--- |
| **"Provision & configure China cloud infrastructure, encryption keys held outside China"** | **Hybrid Cloud Architecture**: Deployed Google Cloud Platform (`asia-east1`, Secret Manager in global tier) + Tencent Cloud Lighthouse (domestic Beijing node for mainland proxy and scraping). |
| **"Run parallel evaluation of China-approved models against pass/fail quality thresholds"** | **Deterministic Evaluation Harness**: Built outside-LLM risk gates (G1–G4) and test suites (`tests/test_cio_loop.py`, `tests/test_idc.py`) benchmarking DeepSeek, Qwen, and Gemini against financial ground truth. |
| **"Familiarity with architectures designed to prevent raw data transmission to model providers"** | **Zero Data Leakage Pipeline**: Local DuckDB and Python compute all sensitive multiples and valuations; only structured, sanitized prompts are passed to LLMs. |
| **"Dual-toolchain workflow bridging China tools with US-facing platforms"** | **Cross-Border Dual Operations**: Fluency across GitHub, GCP, and SEC filings alongside domestic Chinese AkShare, Baostock, and A-share 扣非 net profit workflows. |

---

## 5. Cover Letter: Program Manager, Enterprise AI Platform (Role 3)

**Target Role:** Program Manager, Enterprise AI Platform - China (Contract)  
**Recipient:** IDC China Talent Acquisition & Program Leadership (Beijing)  

```markdown
Subject: Application: Program Manager, Enterprise AI Platform – China (Contract) — Sheng Jiang

Dear IDC China Hiring Team and Program Leadership,

I am writing to express my strong interest in the Program Manager, Enterprise AI Platform – China (Contract) position. Having architected and deployed cross-border AI and data systems bridging Western cloud infrastructure with domestic Chinese compliance realities, I can take full ownership of the phased deployment plan from Day 1 and ensure seamless go-live against your milestones.

My recent work architecting the ARF & AI-CIO Enterprise Intelligence Platform directly addresses the core technical, regulatory, and coordination challenges of this program:

1. China Cloud Provisioning & Network Isolation:
   Engineered a hybrid cloud production environment bridging Google Cloud Platform with Tencent Cloud domestic infrastructure in Beijing. Experienced in establishing network segmentation, proxy routing for mainland data ingestion, and managing encryption architectures where sensitive keys reside securely in Western infrastructure.

2. Parallel Model Evaluation & Quality Benchmarking:
   Designed deterministic evaluation harnesses that benchmark model outputs against rigid pass/fail quality thresholds. Familiar with integrating and evaluating China-approved foundation models (DeepSeek, Alibaba Qwen, Baidu Ernie) alongside global APIs, while ensuring architectures strictly prevent unauthorized raw data transmission to third-party model providers.

3. Cross-Border Delivery & Dual-Toolchain Coordination:
   Bilingual in English and Mandarin with extensive experience bridging US product/engineering teams with China local operations. Comfortable operating across dual toolchains (Jira/Monday/M365 alongside Feishu/WeCom) to maintain transparent deliverables logs, risk registers, and steering committee touchpoints.

4. Pragmatic, Delivery-First Execution:
   While I bring senior architecture and program management experience, I am excited by this 1-year contract engagement because it focuses on tangible delivery: standing up the environment, clearing regulatory filings, and delivering a production-ready AI platform.

A working live demonstration of my dual-ecosystem AI platform is deployed here:
👉 https://stock.thekingfilter.com/IDC_MarketScape

I am based in Beijing, available immediately, and would welcome the opportunity to discuss how I can ensure the on-time, compliant delivery of IDC's Enterprise AI Platform in China.

Sincerely,
Sheng Jiang
Beijing, China
```

---

## 6. Cover Letter: Vice President – AI, Software & Data (Role 1)

**Target Role:** Vice President – AI, Software & Data Management  
**Recipient:** IDC Hiring Committee & Executive Leadership (Beijing)  

```markdown
Subject: Application for Vice President – AI, Software & Data Management (IDC Beijing) — Sheng Jiang

Dear IDC Leadership and Hiring Committee,

I am writing to express my strong interest in the Vice President of AI, Software & Data Management position at IDC Beijing.

As global enterprise and cloud investments in Artificial Intelligence accelerate, technology buyers, enterprise C-suites, and institutional investors confront an unprecedented dilemma: separating genuine commercial AI revenue realization from speculative valuation narrative. Traditional survey-driven market research no longer suffices; what the market urgently requires is a rigorous, data-backed methodology that quantifies AI spending elasticity across the entire technology stack.

To operationalize this exact challenge, I designed, architected, and deployed ARF (AI Relevance Factor) & The Autonomous AI-CIO Platform, an end-to-end quantitative market intelligence engine tracking 73 leading enterprises across Jensen Huang’s 5-layer AI architecture (Silicon, Physical Hardware & Optical Interconnect, Cloud Infrastructure, Foundation Models, and Enterprise Applications) in both the US and Greater China markets.

This initiative directly aligns with the core mandates of IDC's AI Research Practice:

1. Rigorous Market Sizing & Supply-Chain Transmission:
   Rather than relying on static questionnaires, I developed a multi-hop Leontief causal shock model that traces Hyperscaler CapEx revisions (Microsoft, Google, Meta) through tier-1 compute designers (Nvidia) down to optical transceiver suppliers (Innolight, Eoptolink) and foundries (TSMC, SMIC), identifying physical bottleneck clamps before consensus realizes them.

2. Quantitative IDC MarketScape™ Innovation:
   I operationalized IDC's two-dimensional MarketScape model into an algorithmic engine: mapping vendors along Capabilities (ROE quality, operating margins, delivery purity) and Strategies (AI exposure E_score, forward revenue momentum, consensus revision velocity) to deliver objective, real-time vendor positioning.

3. Evaluating AI Business Models & Bubble Risk:
   By calculating reverse-DCF implied growth (g*) and tracking the "Narrative Bubble Multiplier" (Enterprise Value / Real Economic AI Revenue), the platform provides C-level executives with clarity on where AI ROI is genuine versus where multiples have decoupled from underlying cash flow.

4. Bilingual, Dual-Ecosystem Authority (US & China):
   My architecture accounts for the complex operational realities of both ecosystems—from SEC segment filings and A-share non-recurring profit adjustments (扣非) to domestic Chinese AI foundational models (DeepSeek, Alibaba Qwen, Baidu Ernie) and cross-border data security dynamics.

IDC has set the global gold standard for technology intelligence for more than six decades. I would welcome the opportunity to bring this forward-looking, quantitative research architecture to IDC, equipping our clients across Greater China and APAC to navigate the AI frontier with defensible, data-driven conviction.

A live deployment of the platform and the interactive IDC MarketScape matrix can be viewed here:
👉 https://stock.thekingfilter.com/IDC_MarketScape

I look forward to discussing how my experience can contribute to IDC’s continued market leadership.

Sincerely,
Sheng Jiang
Beijing, China
```

---

## 7. Artifact Summary

* **Master Strategy Document:** `Jobs/IDC_VP_APPLICATION_STRATEGY_AND_DECISION.md`
* **Underlying Engine:** [`arf/idc.py`](file:///Users/sheng/Developer/ARF/arf/idc.py)
* **Interactive UI:** [`webapp/views/11_idc_marketscape.py`](file:///Users/sheng/Developer/ARF/webapp/views/11_idc_marketscape.py)
* **Live English URL:** `https://stock.thekingfilter.com/IDC_MarketScape`
* **Unit Tests:** [`tests/test_idc.py`](file:///Users/sheng/Developer/ARF/tests/test_idc.py) (`10 passed`, full suite `317 passed`)
