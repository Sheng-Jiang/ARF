# IDC Quanta — Research Dossier & ARF Comparison

**Prepared:** November 18, 2026
**Purpose:** Enable confident, specific answers about IDC Quanta in the Program Manager, Enterprise AI Platform – China interview — including technical stack and toolchain — and map it honestly against what we have actually built in ARF.
**Evidence standard:** Every claim below is tagged:
- **[VERIFIED]** — stated on idc.com, in an IDC PDF, or in IDC's developer documentation.
- **[REPORTED]** — from a credible third party (Anthropic case study, press coverage, job postings).
- **[INFERRED]** — my reasoned deduction; say it as a question or a hypothesis, never as fact.
- **[GAP]** — not public. Do not bluff.

---

## 0. The one-paragraph answer (memorize this shape)

> "Quanta is IDC's attempt to stop being a destination and become an embedded layer — the research corpus and 15 billion data points delivered into the tools people already work in, with every sentence traceable to a named IDC deliverable. Architecturally it's a two-layer system: an MCP server that exposes IDC's trackers and research as tools, and a plugin/skill layer that encodes IDC's methodology and forces a citation before any answer is returned. The China program is the hard part of that: Claude and Copilot aren't available in mainland China, so the delivery surface, the model, the identity provider, and the hosting all have to be substituted without forking the core platform — which is exactly the constraint your JD describes."

That paragraph is the whole interview. Everything below is ammunition.

---

## 1. What Quanta is — the factual record

### 1.1 Timeline
| Date | Event | Source |
|---|---|---|
| Apr 8, 2026 | Announced at IDC Directions 2026, Boston (flagship client event), by CEO Lorenzo Larini | [VERIFIED] press release |
| Summer 2026 | General availability targeted | [VERIFIED] press release |
| Jul 2026 | Quanta reportedly connected into Claude for customers (per Chinese trade coverage) | [REPORTED] |
| Jul 23, 2026 | CTO Joe Bradley publishes "No Black Box: How IDC Quanta Actually Works" — the closest thing to an architecture disclosure | [VERIFIED] IDC blog |
| Aug 6, 2026 | IDC publishes its own security self-review ("Five Questions to Ask Before You Trust an AI Vendor's Security Claim") | [VERIFIED] IDC blog |
| Oct 28, 2026 | Anthropic publishes the joint case study: Quanta available in Claude; IDC rolls Claude out company-wide | [VERIFIED] claude.com |

### 1.2 Positioning — the exact language they use
- "The **technology intelligence layer** for the AI economy" / "the **intelligence fabric** of the AI-enabled enterprise." [VERIFIED]
- CEO Larini: *"AI is compressing time across the entire technology market, and that breaks the traditional research model. Leaders don't need more noise. They need intelligence that shows up in the moment."* [VERIFIED]
- The strategic shift they are selling: **from static research consumption through gated portals → continuous, embedded intelligence**. [VERIFIED]

Use "intelligence layer / intelligence fabric," not "chatbot" or "research portal." They are explicit that Quanta is *not* a chatbot — Bradley frames it as a system with an opinionated point of view rooted in 60 years of research.

### 1.3 The five design pillars (their own words — quote these)
| Pillar | What IDC means |
|---|---|
| **Embedded** | Intelligence inside workflows — starts with email, expands to collaboration and AI platforms; no search, no context-switching |
| **Contextual** | Customer brings its own data/documents into a secure workspace; Quanta retains context across interactions |
| **Secure** | Data isolation and governance at the core; customer data never trains models; 90-day auto-deletion |
| **Aware** | Scheduled intelligence, trend signals, anonymized peer patterns, suggested next questions — insight before you ask |
| **Rigorous** | Sourced, citable answers with full transparency into methodology and inputs; every output traceable to IDC intelligence |

### 1.4 The numbers they lead with (memorize three or four)
- 60+ years of IDC research; **1,000+ analysts**; **100+ countries**. [VERIFIED]
- **15B+ data points tracked annually**; **1M+ companies tracked**; **404,000+ tech leaders surveyed annually**; **120+ tech markets**; **$500B in tracked spend**. [VERIFIED]
- Built with **175+ beta customers**, **120+ use cases**, **300+ AI validation dimensions**, **4.8/5** customer satisfaction, **zero training on customer data**. [VERIFIED]
- Kyndryl quote (Mark Terranova): *"Where it used to take weeks to draw conclusions, reading hundreds of reports… I can now do that in minutes."* [VERIFIED]

### 1.5 Commercial model
- **Seven packages**, annual fee, **not** priced as a percentage of procurement savings. [REPORTED]
- Packaging is around *what you're trying to do*, not seat count; every tier draws on the same data foundation and analyst bench. [VERIFIED]
- Analyst inquiries: **60 minutes, open to anyone on the account** — explicitly not one named seat holder. [VERIFIED]
- Purchasable through **AWS Marketplace** against committed AWS spend. [VERIFIED]
- Two product lines: **Quanta for Tech Suppliers** (AR, product marketing, sales/revops) and **Quanta for Tech Leaders** (CIO, security/ops, finance/procurement), plus academic access. [VERIFIED]

---

## 2. Surface map — how a customer actually touches Quanta

This is the part most candidates miss, and it is the part a Program Manager must know cold, because "surface" is what has to be rebuilt for China.

| Surface | What it is | Status |
|---|---|---|
| **Web portal** | Full research workspace at idc.com; enterprise credentials (SAML SSO) unlock it, no new account | [VERIFIED] |
| **Email** | Compose a plain-language question to `brief@quanta.idc.com`; structured, sourced answer back in ~1 minute; "View in IDC Quanta" opens the portal thread with context intact | [VERIFIED] |
| **Claude plugin** | Distributed via Claude's plugin directory; bundles an **IDC Connector (live MCP server)** + an **IDC Quanta Skill** invoked as `/idc-quanta` | [VERIFIED] |
| **Claude surface coverage** | Claude desktop & web, Claude Code, Claude in Chrome, Claude for Microsoft 365 (Excel / Word / PowerPoint add-ins) | [VERIFIED] |
| **Microsoft Copilot** | **IDC federated connector** listed in the M365 Copilot connectors gallery + **IDC Cowork plugin** deployed via M365 admin center; content pulled dynamically through MCP and **never indexed into M365** | [VERIFIED] |
| **REST APIs** | Research Documents API, Query Tool API – Classic, Services Contract Database API | [VERIFIED] |
| **SFTP** | Bulk feeds for Trackers, Spending Guides, Black Book | [VERIFIED] |
| **MCP** | The forward-looking integration path; more connectors + a developer-facing interface announced as next | [VERIFIED] |

**The sentence that matters for the interview:** the plugin is one install for the whole org, distribution is admin-controlled (four settings: available / installed by default / not available / required), and **entitlement travels with every call** via OAuth SSO — a user without a subscription to a report does not get its content.

---

## 3. Technical stack & toolchain

### 3.1 Application platform — the honest state of public knowledge

| Layer | What we know | Confidence |
|---|---|---|
| Backend | **Java**, **Spring Framework**, **microservices**, REST API design | [REPORTED] IDC engineering job postings (Prague) |
| Frontend | **Angular** ("strongly preferred") | [REPORTED] job postings |
| Database | **PostgreSQL** (listed as a plus on the identity/fulfillment role) | [REPORTED] job postings |
| Cloud | AWS / Azure / GCP experience required; IaC a plus | [REPORTED] job postings |
| CI/CD | Standard pipeline + Git; automated testing expected | [REPORTED] job postings |
| Identity | **Frontegg** — IDC's developer docs ship a "FrontEgg: Customer Configuration Guide" alongside SAML setup | [VERIFIED] idc.com/developer |
| Engineering AI | **Claude Code used across all SDLC phases**, treated as default tooling, not optional | [REPORTED] job postings + Anthropic case study |
| Data products | Trackers / Spending Guides / Black Book delivered as **flat CSV inside `.csv.gz`**, dimensions + measures, split into multiple files, schema versioned with advance-change notification | [VERIFIED] developer docs |
| Data API | Base URL `https://www.idctracker.com/api/v3`, header `x-api-key`, `GET /api/v3/exports` returns JSON with pre-authenticated download URLs | [VERIFIED] developer docs |
| Search / vector / warehouse | **Not disclosed** | [GAP] |

**Do not claim to know their vector store, orchestration framework, or model provider for the portal.** Those are not public. If asked, say: *"I haven't seen that published — my assumption is a retrieval layer over the tracker corpus plus a multi-agent orchestration for validation, but I'd want to confirm rather than guess."* That answer is stronger than a confident invention.

### 3.2 The AI layer — the two-layer architecture (this is the core technical answer)

From CTO Joe Bradley, on the record: [VERIFIED]

> **Layer 1 — MCP server.** "Essentially a pipe that gives Claude direct access to IDC's data, the trackers, the forecasts, the market figures. It also carries instructions for how that data is structured and how to use it."
>
> **Layer 2 — IDC's own Claude plugin.** "It shapes how the AI reasons about that data, tells it what's relevant for what purpose, and requires it to surface a source before handing over any answer."

And the consequence he draws: *"Claude isn't searching a phrase in a database. It's reasoning with IDC's own methodology built into the process."*

The **Skill** is the interesting artifact: a packaged piece of know-how in natural language covering dozens of research workflows (market share analysis, vendor evaluation, TAM), plus *navigation, attribution and brand-voice rules that keep every answer auditable* — so output looks the way an IDC analyst would produce it, and entitlement decides whether Quanta workflows or Tech Leader workflows fire. [VERIFIED]

### 3.3 Answer pipeline — what actually happens on a question

Reconstructed from IDC's own published descriptions: [VERIFIED for components, INFERRED for ordering]

1. **Identity & entitlement** — OAuth/SAML SSO resolves the user; token-derived identity scopes every query; group entitlements decide which corpora are visible.
2. **Intent interpretation** — a multi-agent system works the problem from multiple angles: interpret intent → query IDC → cross-validate citations. [VERIFIED]
3. **Retrieval over IDC data** — research documents, Trackers, Spending Guides, Black Book, Services Contract Database; **SQL scoping at the application layer** keeps tenants isolated. [VERIFIED]
4. **Customer context** — uploaded documents land in a private workspace; each file passes **malware scanning and prompt-injection detection before it reaches the model**. [VERIFIED]
5. **Reasoning + methodology** — the skill layer supplies workflow rules and attribution discipline.
6. **Validation** — a multi-agent validation system checks the response against IDC data; 300+ validation dimensions are claimed. [VERIFIED]
7. **Output contract** — structured response with **section-level citations**, source dates, and a live link back to idc.com; for document validation, it flags factual conflicts, numbers needing clarification, and gives specific edits. [VERIFIED]
8. **Persistence** — uploaded content auto-deleted after 90 days; never used for training. [VERIFIED]

### 3.4 Security & compliance stack — the numbers to quote
- Tenant isolation **at the application layer**: token-derived identity + SQL scoping. [VERIFIED]
- Upload screening: malware + **prompt-injection detection** before model ingestion. [VERIFIED]
- **No training on customer data — permanent commitment, not a setting.** [VERIFIED]
- **AES-256** encryption; **90-day** automatic deletion. [VERIFIED]
- **SOC 2 Type I** certified; **SOC 2 Type II** and **ISO 27001:2022** in progress. [VERIFIED]
- **BitSight score 800/900** as of July 2026, continuously verified. [VERIFIED]
- **Annual third-party pen test** + continuous vulnerability scanning; "24-vendor, 11-domain zero-trust stack" with round-the-clock monitoring. [VERIFIED]
- Public trust center: **trust.idc.com**. [VERIFIED] (403 to non-browser clients; assume a security team can read it.)

### 3.5 Internal toolchain — what IDC says about its own engineering
This is a gift for the "do you understand modern delivery?" question: [VERIFIED, Anthropic case study]
- Internal data repository rebuilt in **3 weeks vs. 3 months** estimated.
- Code review that **filled five days → ~30 minutes**.
- Writing a test: **days → ~20 minutes**.
- Planning sprints: **3 weeks → 3 days**.
- Product managers build working prototypes in Claude Code **before engineering starts**.
- Sales runs a Claude-built tool over CRM exports to flag stalled vs. winnable deals.

---

## 4. What this means for the China program (the actual job)

### 4.1 The evidence
- The PM JD never says "Quanta." It says "Enterprise AI Platform – China" and "the core platform." [VERIFIED JD]
- **The parallel Beijing VP JD does say it explicitly**: *"**Quanta China Implementation** — Lead IDC's Quanta platform implementation in Greater China from initiation through full production launch… Structure, negotiate, and manage relationships with implementation partners — system integrators, ISVs, and cloud partners — at the scale required by the **Quanta China Implementation Plan**."* [VERIFIED JD]
- The same VP JD names the model substitution: *"Evaluate and integrate Chinese AI models and platforms (**Deepseek, Baidu Ernie, Alibaba Qwen**, etc.) into IDC workflows."* [VERIFIED JD]
- IDC's China site does not promote Quanta; there is no public China instance. [VERIFIED as of Nov 18, 2026 — absence of evidence, stated as such]

**Conclusion [INFERRED, high confidence]:** the role is the China instance of Quanta. The "core platform" language and the "no codebase changes" requirement exist precisely because Quanta is a US-built platform whose entire Western delivery stack is unusable in mainland China.

### 4.2 The substitution problem — say this out loud in the interview
Every layer of Quanta's Western delivery has a China blocker:

| Western component | China blocker | Substitution |
|---|---|---|
| Claude plugin / MCP connector into Claude | Claude not available in mainland China | Domestic agent surface: WeCom / Feishu / DingTalk bot, or a China-hosted portal with an OpenAI-compatible gateway to Qwen / DeepSeek / Ernie / GLM |
| Microsoft Copilot connector | Copilot availability in China is restricted/enterprise-gated | Same domestic surface; M365 China operated by 21Vianet is a separate tenant |
| `brief@quanta.idc.com` email intake | Works technically, but model + hosting are offshore, and inbound mail carries customer documents | China-hosted intake with in-country processing; no cross-border document flow without assessment |
| Frontegg / SAML SSO to global IdP | Identity data is personal data under PIPL | Local IdP federation (WeCom/Feishu/DingTalk OAuth or local SAML), pseudonymized subject claims |
| AWS/Azure global hosting | Data residency, MLPS, cross-border transfer | Alibaba Cloud / Tencent Cloud / Huawei Cloud / AWS China / Azure China |
| Global research corpus | Mixed: public research vs. subscription IP vs. customer uploads | Classify before transfer; keep customer documents in-country; mirror only cleared content |
| Claude as reasoning engine | No access | Domestic LLM behind a model-agnostic gateway |

**The architectural thesis to present:** *the protocol layer is the portable asset.* Keep the MCP tool contract, the skill/methodology packaging, and the citation contract; swap the model, the host, and the identity provider. That is exactly the "no changes to the core platform codebase" pattern the JD asks for — and it is why a China Integration Layer / gateway, not a fork, is the right answer.

### 4.3 The five workstreams the China program will actually contain
1. **Platform & hosting** — China landing zone, VPC segmentation, private egress, KMS with KEKs outside China, no public inbound to backend services.
2. **Model layer** — parallel evaluation of Qwen / DeepSeek / Ernie / GLM against a **pass/fail threshold agreed before testing**, with a sanitized, export-control-clean prompt/response path.
3. **Research content & data** — which IDC corpora may cross the border; Chinese-language corpus and citation quality; tracker data delivery into China.
4. **Identity & entitlement** — local IdP federation, entitlement parity with the global subscription model, tenant isolation preserved.
5. **Regulatory** — MLPS tier determination, PIPL/DSL classification, CAC filings where applicable, filing agent on milestone-gated SOW, outside counsel.

### 4.4 Partner model
The VP JD is explicit that this runs through **system integrators, ISVs, and cloud partners**, negotiated at SOW level. So the PM is not building alone — which changes the risk profile from "can we build it" to "can we make three external partners hit the same gate on the same date." Frame your governance answer around partner SLAs, not internal sprints.

---

## 5. ARF vs. Quanta — side by side

### 5.1 Comparison table

| Dimension | IDC Quanta | ARF (what we built) |
|---|---|---|
| **Core job** | Deliver IDC's research corpus into workflows, cited and defensible | Score how much a company's valuation is bent by the AI narrative; run an investment research loop on top |
| **Data foundation** | 60 yrs research, 15B+ data points/yr, 1M+ companies, 404k surveys, Trackers / Spending Guides / Black Book | 73 companies, 2 legs (US 36 / China 37), fundamentals + prices + technicals in DuckDB; Gemini web-search layer for news |
| **Unit of output** | Cited answer, competitive brief, vendor shortlist, scorecard | ARF score 0–100, decile, froth flag, implied-growth gap, CIO decision packet |
| **Determinism** | LLM reasoning constrained by methodology + multi-agent validation + mandatory citation | **Math is deterministic and outside the model**: reverse-DCF solver, percentile ranks, `sqrt(E×V)`; LLM never computes a score |
| **Where the model sits** | At the center — it is the product | At the edge — narrative, extraction, summarization; gates run without it |
| **Hard gates** | Multi-agent validation (300+ dimensions), citation requirement | **G1–G4 deterministic gates**: data integrity, froth circuit-breaker, WACC hurdle, cross-node g* consistency — evaluated before any proposal is issued |
| **Provenance** | Section-level citations to named IDC deliverables + live link | Every row traceable to source fields; append-only `snapshot_revisions`, nothing deleted, revisioned re-runs |
| **Tool protocol** | **MCP** server + plugin + skill; powers Claude and Copilot | **Python function tools** (`query_quant_database` SELECT-only, `get_stock_quant_profile`, `search_value_chain_layer`, `fetch_external_candidate`) — same idea, internal only |
| **Domain modeling** | Proprietary semantic layer over trackers (dimensions/measures), methodology embedded in skill | **Code-first lightweight ontology** per ADR-001: Pydantic v2 (`extra="forbid"`) + networkx DAG + DuckDB; explicitly *no* Neo4j/RDF/OWL |
| **Surfaces** | Portal, email, Claude, Copilot, REST, SFTP, AWS Marketplace | Streamlit webapp (11 views), Markdown/PDF reports, weekly pipeline, parquet + HTML thermometer |
| **Identity** | Frontegg + SAML SSO + OAuth, entitlement-scoped | Single-tenant internal app; no SSO/entitlement layer (honest gap) |
| **Cloud** | AWS/Azure/GCP (unspecified regions) | Hybrid: GCP `asia-east1` (Cloud Run, GCS, Secret Manager) + Tencent Cloud Lighthouse in-country (proxy + batch runner) |
| **China posture** | Not deployed in China; Claude/Copilot unavailable | **Already cross-border by design**: China data fetched through a domestic proxy, China batch runner after A-share close, US/Gemini traffic direct, per-thread routing |
| **Localization** | English-first, then partner languages | Bilingual EN/ZH with a `tr(zh, en)` layer, English-first by default |
| **Security posture** | SOC 2 I, ISO 27001 in progress, BitSight 800/900, pen-test, zero-trust, 90-day deletion | No certifications; secrets in Secret Manager; no customer PII; public-market data only — a much smaller attack surface, and say so honestly |
| **Failure mode** | Confidently wrong without a citation — mitigated by validation + citation | Silent bad data (stale price, FX mismatch) — mitigated by gates + calibration tests + revision history |

### 5.2 Where ARF is genuinely ahead — say these with confidence
1. **The model is not allowed to do arithmetic.** Scores come from a reverse-DCF solver and percentile ranks; the LLM writes prose about numbers it did not compute. Quanta's own pitch is "cite the source"; ours is stronger on the math: *the number cannot be hallucinated because the model never touches it.*
2. **Gates run outside the model, before output.** G1–G4 are deterministic vetoes. That is the same discipline the playbook demands of the China LLM evaluation — pre-agreed pass/fail, no moving goalposts.
3. **Immutable, revisioned history.** `snapshot_revisions` is append-only; the `snapshots` view serves the latest revision per date. You can prove what the model saw on any date. Most AI products cannot.
4. **Hard-won cross-border data mechanics.** The China leg is not a demo: AkShare/Eastmoney scraping is geo-blocked, so it runs through a domestic proxy, with Baostock's raw socket confined to the in-country runner, and US/Gemini traffic kept direct. That is exactly the "which traffic goes where" problem the China program will hit.
5. **Bilingual by construction.** Chinese tickers get Chinese-language search hints; ROE uses 扣非 net profit, not reported net income; FX is handled on a reporting-currency basis (BABA/BIDU/TSM report in a currency they don't trade in). This is the kind of local-market detail that separates a real China build from a translated one.
6. **Cost discipline.** Batch quotas and deterministic evaluation instead of open-ended token burn — directly relevant to the "AI costs don't scale like IT costs" pain IDC itself is selling against.

### 5.3 Where Quanta is ahead — be honest, it buys credibility
- **Corpus scale and rights**: 60 years of proprietary research with subscription entitlements. We have public market data.
- **Distribution**: inside Claude, Copilot, email, Excel. We have a webapp people must visit.
- **Identity and entitlement**: Frontegg, SAML, OAuth, group-scoped tools. We have none.
- **Validation breadth**: 300+ validation dimensions and a multi-agent cross-check. We have four gates.
- **Trust artifacts**: SOC 2, ISO 27001 in progress, BitSight, public trust center. We have none.
- **Analyst-in-the-loop**: a live analyst as escalation. We have a Gemini news layer.

### 5.4 Three ideas worth porting into the China program (your value-add)
1. **Package the methodology, not just the tools.** Quanta's Skill is natural-language know-how shipped alongside the MCP server: workflow rules, attribution rules, brand voice. Our equivalent is the scoring spec + gate definitions. In China, that package is what keeps a domestic model producing IDC-shaped output instead of generic chat.
2. **Make citation a hard output contract.** Not "the model may cite" but "no answer without a source." Our version: no score without a snapshot revision and a source field.
3. **Multi-agent cross-validation as a gate.** Interpret intent → query → cross-validate the citation. Map it to the evaluation harness: one agent runs, another checks the run against the frozen rubric.

---

## 6. Demo branding — fixed November 18, 2026

**Was:** the demo page was titled *"IDC Quanta™ AI Analyst Research Desk — ARF MarketScape™"* and generated reports carried *"IDC Quanta™ Research Desk Platform"* and *"Copyright © 2026 IDC. All rights reserved."*

**Why it mattered:** Quanta™ and MarketScape™ are IDC trademarks, and Quanta is the product this program deploys. A page carrying that name, built on our own methodology and our own numbers, reads as passing off.

**Now:**
- Page title: **"ARF Analyst Desk — Vendor Quadrant & AI Spending"** (`/analyst-desk`).
- Methodology described as ARF's own, modelled on the public capabilities/strategies quadrant format; reports carry an explicit "not affiliated with or endorsed by any research firm" line.
- Report IDs are `ARF-RB-…` / `ARF-VP-…`; download filenames are `ARF_*`; no IDC copyright line anywhere in generated output.
- Module renamed `arf/idc.py` → `arf/analyst_desk.py`; view `11_idc_marketscape.py` → `11_analyst_desk.py`; tests renamed to match.
- Legacy `/IDC_MarketScape`, `/idc-marketscape`, and the Chinese alias URL still resolve to the renamed page (hidden aliases), so anything already shared does not 404.

**Still to check outside the repo:** the CV markdown/docx files in `Jobs/` and the VP application strategy doc still describe the platform as "IDC Quanta™" and link the old URL. The old URL works, but the *wording* in anything already sent cannot be recalled — be ready to re-frame it in the interview as "my own desk, modelled on the quadrant format."

---

## 7. Interview Q&A — twelve questions on Quanta

**Q1. "What do you know about Quanta?"**
> "It's IDC's shift from a destination to a layer. The product is the corpus plus a delivery mechanism: an MCP server that exposes trackers, forecasts and research as tools, and a plugin-and-skill layer that encodes IDC's methodology and requires a source before it answers. The surfaces are the portal, email intake, and plugins inside Claude and Copilot, with entitlement enforced per call. The China program is the interesting one, because none of those Western surfaces work in mainland China."

**Q2. "How does it actually work under the hood?"**
> "Two layers, per your CTO's own description. The MCP server is a pipe with a schema — it tells the model what the data is and how it's structured. The plugin goes further: it shapes how the model reasons, tells it what's relevant for which purpose, and forces a citation before the answer is released. Practically: intent interpretation, retrieval over IDC data, multi-agent cross-validation of the citations, then a structured response with section-level links back to idc.com. Uploaded documents are isolated per tenant, screened for malware and prompt injection before the model sees them, and deleted after 90 days."

**Q3. "What stack is it built on?"**
> "Publicly: Java and Spring microservices, Angular on the front end, PostgreSQL, standard CI/CD, with Frontegg behind the SSO. Data products ship as flat CSV in gzip with a dimension/measure schema, and the classic data API is `idctracker.com/api/v3` with an API-key header. Beyond that the retrieval and orchestration layers aren't published — I'd rather ask than guess."

**Q4. "Where would you expect the China version to diverge?"**
> "Four places. The model: Claude isn't available, so it's Qwen, DeepSeek, Ernie or GLM behind a model-agnostic gateway. The surface: no Claude plugin, no Copilot connector — so a China-hosted portal or a WeCom/Feishu bot. The identity: Frontegg and the global IdP don't carry personal data across the border cleanly, so local federation with pseudonymized claims. And hosting: an in-country landing zone with keys held outside. The protocol layer is what should survive unchanged — that's the whole point of keeping it model-agnostic."

**Q5. "Is this a fork of the platform or a wrapper?"**
> "Wrapper, and the JD says so explicitly — no changes to the core codebase. The pattern is an edge adapter: the core platform keeps calling configurable LLM endpoints and a standard IdP, and all China-specific behavior lives in a separate integration layer configured by environment, deployed on its own pipeline. You prove it by keeping the core repo's diff at zero."

**Q6. "Have you built anything like this?"**
> "Yes, at smaller scale and from the other direction. ARF is a research platform with an agent layer: deterministic scoring in DuckDB, a set of typed tools the agent can call, and four hard gates that veto output before a recommendation is issued. I also run it cross-border — China market data is geo-blocked, so it comes through an in-country proxy while US and model traffic stays direct. Different corpus, same architecture problem: keep the model away from the numbers, keep the data where it's allowed to be."

**Q7. "What would you do in week one?"**
> "Three things in parallel. Get the filing agent under a milestone-gated SOW. Get a written answer from the US technical owner on which parts of the platform are actually configurable — endpoints, IdP, routing — versus which are hard-coded, because that single answer determines whether this is a wrapper or a fork. And get the model evaluation rubric agreed in writing before any testing, so the pass/fail threshold can't move after results land."

**Q8. "How do you keep a domestic model producing IDC-grade output?"**
> "You don't do it with the model. You do it with the layer around it — workflow rules, attribution rules, output schema, and a validator that rejects anything without a source. Quanta already ships that as a skill; the China question is whether the equivalent rules survive translation and a different model's instruction-following. That's a testable question in week two, not an article of faith."

**Q9. "What's the biggest risk you see?"**
> "That the program is scoped as an infrastructure project when it is actually a content-rights project. The cloud and the model are solvable. The hard question is which IDC research may legally sit in China and be processed by a Chinese model, and who signs that off. If that isn't resolved by Gate 0, everything downstream is built on an assumption."

**Q10. "How is Quanta different from ChatGPT with a web search?"**
> "Provenance and entitlement. A general model gives you an answer you have to verify. Quanta gives you an answer with the specific IDC deliverable attached, drawn only from content your organization is entitled to, produced under methodology rules that make it look like an IDC analyst wrote it. Where the general model is confident, Quanta is checkable."

**Q11. "What would you change about it?"**
> "I'd want the evaluation of the answer quality to be as inspectable as the citations. They publish the security posture in detail — SOC 2, BitSight, pen-test cadence, trust center — and I'd want the equivalent for accuracy: what the pass/fail threshold is on a benchmark, and how it's tracked over model versions. That's the same discipline I'd apply to the China model evaluation, so it's a natural thing for me to own."

**Q12. "You've built your own version of this — why work on ours?"**
> "Because the interesting part isn't the demo, it's the deployment. I can build a research desk; what I haven't done at IDC's scale is take a platform with real entitlements, real legal exposure and a US engineering owner, and land it in China without forking the core. That's the problem I want."

---

## 8. Five questions to ask them about Quanta

1. **"When you say the core platform can't be modified — where does the configuration boundary actually sit today? Is the LLM endpoint and IdP already abstracted, or are there coupling points we'll need to wrap in Phase 1?"**
2. **"For the China instance, is the intent to mirror the MCP interface with a domestic model behind it, or is the China surface a different product with a different interaction model?"**
3. **"Which research corpora are already cleared for in-country processing, and who owns that decision — legal, the content owners, or the country lead?"**
4. **"What's the pass/fail definition of a successful model evaluation, and who signs it — the US technical owner, or does China have a say?"**
5. **"What did the beta customers complain about most? I'd rather design around a known failure than discover it at Gate 3."**

---

## 9. 60-second script if they ask "what do you know about Quanta?"

> "It's IDC's intelligence layer — the research corpus and 15 billion data points delivered into where people already work, with every answer traceable to a named deliverable. Architecturally it's two pieces: an MCP server that exposes the trackers and research as tools with a schema, and a skill layer that encodes IDC's methodology and refuses to answer without a source. Today it surfaces in the portal, over email, and inside Claude and Copilot with entitlement enforced per call.
>
> The reason I'm interested in this role specifically is that the China instance is where all of that gets tested. The model, the hosting, the identity provider and the delivery surface all have to be substituted, while the core platform stays untouched — and that's a program-management problem as much as an architecture one, because the model evaluation, the content rights, and the regulatory filing all have to land on the same gate."

---

## 10. Sources

Primary (IDC):
- Press release, Directions 2026 launch — https://www.idc.com/resource-center/press-releases/directions-2026-idc-quanta/
- Quanta overview — https://www.idc.com/quanta/
- Quanta for Tech Suppliers — https://www.idc.com/quanta/tech-supplier/
- Quanta for Tech Leaders + pricing tiers — https://www.idc.com/quanta/tech-leader/
- "No Black Box: How IDC Quanta Actually Works" (CTO Joe Bradley) — https://www.idc.com/resource-center/blog/how-idc-quanta-actually-works/
- "Five Questions to Ask Before You Trust an AI Vendor's Security Claim" — https://www.idc.com/resource-center/blog/idc-quanta-five-questions-security/
- Developer home (SSO / REST / SFTP / MCP) — https://www.idc.com/developer/
- Quanta in Claude and MCP (plugin, skill, Copilot, admin setup) — https://www.idc.com/developer/quanta/
- REST API overview — https://www.idc.com/developer/rest-api/
- Query Tool API – Classic — https://www.idc.com/developer/rest-api/data-api/
- Data format (dimensions/measures, CSV.gz) — https://www.idc.com/developer/data-format/
- Trust center — https://trust.idc.com
- Quanta TS eBook (PDF) — https://www.idc.com/wp-content/uploads/2026/10/IDC-Quanta-TS-eBook.pdf
- Customer stories (Kyndryl, Unit4, Belden, global tech co) — https://www.idc.com/wp-content/uploads/2026/10/IDC-Quanta-Vendor-Customer-Stories.pdf
- Tech Leader one-pager — https://www.idc.com/wp-content/uploads/2026/10/IDC-Quanta-Tech-Leader-1-Pager.pdf

Partner / press:
- Anthropic case study, Oct 28 2026 — https://claude.com/resources/articles/idc-brings-quanta-into-claude-and-adopts-claude-across-the-company
- IDC C-suite announcement (Joe Bradley CTO, "architect of Quanta") — https://www.globenewswire.com/news-release/2026/06/10/3309879/0/en/IDC-Strengthens-Its-C-Suite-as-It-Enters-a-New-Phase-of-Accelerated-Growth.html
- TechTarget Japan (Japanese trade coverage) — https://techtarget.itmedia.co.jp/tt/article/2607/08/226070811/
- The Data Tech Times (pricing structure) — https://thedatatechtimes.com/ai-ml/idc-launches-quanta-ai-platform-enterprise-tech-decision-makers
- Chinese-language coverage of the launch — https://ch.acnnewswire.com/Article.Asp?Art_ID=106253&lang=CH&cat=HL

Stack evidence (job postings):
- Sr. Software Engineer, Prague (Java, Angular, microservices, Claude Code) — https://www.glassdoor.ca/job-listing/sr-software-engineer-idc-international-data-corporation-JV_IC2296178_KO0,20_KE21,55.htm
- Senior Java Engineer, Digital Fulfillment (Spring, SSO/OAuth, PostgreSQL, Angular) — https://simplify.jobs/p/c96bdacd-ccec-4b35-bcf8-8a740fbf5044/Senior-Java-Engineer

Internal (this repo):
- `Jobs/IDC_INTERVIEW_PREP_PLAYBOOK_PROGRAM_MANAGER.md` — interview playbook
- `Jobs/Vice President, Technology & AI Enablement _ IDC咨询(北京)有限公司 _ LinkedIn.pdf` — names "Quanta China Implementation Plan"
- `webapp/views/11_analyst_desk.py`, `arf/analyst_desk.py` — renamed demo branding (§6)
- `arf/agent/cio_loop.py` — G1–G4 gates
- `docs/ADR-001-Next-Gen-Modeling-and-Lightweight-Ontology-for-Agents.md` — code-first ontology standard
