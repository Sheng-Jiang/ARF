# IDC Formal Interview Preparation Playbook — Program Manager, Enterprise AI Platform - China (Contract)

**Target Role:** Program Manager, Enterprise AI Platform – China (Contract)  
**Employer:** IDC (`IDC咨询(北京)有限公司`, Beijing)  
**Candidate:** Sheng Jiang (蒋胜)  
**Interview Slot:** Saturday Morning Beijing Time (Friday Evening US Time) with US-based Stakeholder  
**Prepared:** November 17, 2026  
**Live Demo Verification (Pre-Interview Check):**
- `https://stock.thekingfilter.com/analyst-desk` — verified `HTTP 200`
- `https://ciso.thekingfilter.com/ui/jpmc-cockpit` — verified `HTTP 200`

> **Companion document:** `Jobs/IDC_QUANTA_RESEARCH_AND_ARF_COMPARISON.md` — a fact-checked dossier on IDC Quanta (product, architecture, stack, toolchain), a side-by-side against what we built in ARF, and 12 prepared Q&A answers. Read §6 of that document before the call: it flags a branding issue on the live demo page that should be fixed first.

---

## 1. Interview Context & US Interviewer Psychology (Friday Evening US / Saturday Morning Beijing)

### Timezone & Energy Calibration
- **Your slot (Sat 8:00–11:00 AM BJT)** = **Friday 4:00–7:00 PM PT (Pacific)** or **7:00–10:00 PM ET (Eastern)** for the interviewer.
- Someone taking an interview on a **Friday evening US time** is either personally invested in unblocking this launch or senior enough that their weekday calendar is packed.
- **Implication for delivery:** Respect their cognitive bandwidth. Lead every answer with the headline conclusion in 1–2 sentences, back it with 3 concrete bullets (architecture / governance / risk-control), and pause to ask if they want deeper detail. Avoid rambling chronological recitations.

### Likely US Interviewer Personas (From the JD)
Based directly on the role specification (`What You'll Own`), your US interviewer is most likely one of two profiles—or a combination of both:
1. **The US-Based Technical Product Owner** (owns pass/fail model quality thresholds, core platform codebase integrity, identity federation, and export-control clean test structure).
   - *Core anxieties:* Will this China deployment force intrusive changes onto my core US codebase? Will raw customer/proprietary data leak to Chinese model providers? Are China LLM benchmarks actually rigorous, or just "it looks okay"? Will export-control or legal teams block us because our test harness is sloppy?
2. **The US Program Representative / Global Program Lead** (owns end-to-end delivery timeline, escalation path, steering committee readiness, and cross-border visibility).
   - *Core anxieties:* Will a local Beijing contractor disappear into WeCom/Feishu and give me green statuses right up until a catastrophic surprise? Will CAC regulatory filings stall for months after we already burned cloud budget? Does this person truly understand *US HQ* governance expectations (Jira/Asana/Monday/M365) *and* on-the-ground China reality?

> **Terminology Discipline ("Quanta" Guardrail):**  
> IDC's parallel Beijing VP job description (*Vice President, Technology & AI Enablement*) references **Quanta** explicitly — it names a **"Quanta China Implementation Plan"** and a "Quanta China Implementation" workstream, and it names the domestic models (DeepSeek, Ernie, Qwen). This PM JD, by contrast, says **"Enterprise AI Platform – China"** and **"the core platform"**. **Do not drop the word "Quanta" first.** Mirror the interviewer's exact terminology (`"the Enterprise AI Platform"`, `"the China deployment"`, `"the core platform"`); only adopt *"Quanta"* if they introduce it first.
>
> **But be ready to go deep the moment they do.** If they ask "what do you know about Quanta," you should out-detail a generic candidate: the two-layer MCP-server + plugin/skill architecture, the multi-agent validation and citation contract, the security posture (tenant isolation via token-derived identity and SQL scoping, prompt-injection screening, no training, 90-day deletion, SOC 2 Type I, BitSight 800/900), and the surfaces (portal, `brief@quanta.idc.com`, Claude plugin, Copilot federated connector, REST/SFTP). See the companion dossier §7 for verbatim answers.

---

## 2. Opening 90-Second Pitch & Handling the "Why Contract / Overqualification?" Question

### 2A. Opening 90-Second English Pitch ("Tell me about yourself / Walk me through your background")

> "Thank you for making time on a Friday evening—I'll keep this crisp and directly relevant to your China platform launch.
>
> I'm a bilingual Systems Architect and Cross-Border Delivery Director based in Beijing with over 28 years of experience delivering enterprise software, cloud infrastructure, and regulatory compliance programs between US/European headquarters and China operations.
>
> Three anchors make me unusually well-suited to own this program from Day 1:
> 1. **US Engineering DNA:** I earned my Master's in Software Engineering in the US and spent **6 years as an SDE at Microsoft HQ in Redmond** on Visual Studio .NET and distributed enterprise frameworks—so I think like a US product/engineering team when protecting core platform codebases and designing identity federation and API adapters.
> 2. **US/EU-to-China Enterprise Delivery & Compliance:** Over the past decade-plus in Beijing, I've led China localization, cloud stand-ups (AWS China, Azure China, Alibaba Cloud, Tencent Cloud), IT service transformations, and regulatory compliance for multinationals like **BMW China, Umicore, Sika, and ZF**, and served as a CISA/TOGAF governance auditor for the **Shanghai and Shenzhen Stock Exchanges**—including managing CAC data compliance, PIPL/DSL reviews, and MLPS filings with local filing agents and outside counsel.
> 3. **Hands-On Enterprise AI & China LLM Benchmarking:** Most recently, I built and deployed a live cross-border hybrid-cloud AI platform bridging GCP and Tencent Cloud Beijing, incorporating non-intrusive data protection pipelines and deterministic pass/fail evaluation gates for China-approved models like DeepSeek and Qwen.
>
> I'm excited about this role because it sits at the exact intersection of technical architecture, China regulatory execution, and disciplined US-facing program governance."

### 2B. Addressing "You've held Director/VP-level titles—why take a 1-year Contract PM role?"

*Deliver this calmly, matter-of-factly, and without defensiveness:*

> "Two practical reasons. First, **zero-to-one cross-border AI launches in China don't fail on PowerPoint—they fail in the trenches**, at the seams between cloud isolation, external encryption key custody, regulatory filings, and LLM benchmark rigor. A purely administrative PM can track Asana tickets, but gets blocked the moment legal asks how data sanitization prevents raw transmission to a Chinese model endpoint, or when a filing agent stalls. I genuinely enjoy hands-on 0-to-1 delivery where architecture, compliance, and program control meet.
>
> Second, **the structure aligns with how I work best:** high accountability, clear milestones, and a defined production go-live target over 12 months. As noted in the spec, if we deliver a rock-solid, compliant China launch and there is a natural fit for a permanent leadership role afterward, I'm very open to that—and in the meantime, you get principal-level execution and zero ramp-up friction from Week 1."

---

## 3. Phased Program Plan (4-Gate / 90+ Day Execution Blueprint)

Use this framework when asked *"How would you structure the phased program plan from kickoff to go-live?"* Notice how **Regulatory Filings run in parallel from Day 1** rather than sitting downstream as a surprise blocker.

| Gate | Target Window | Core Technical & Architecture Workstream | Parallel Regulatory, Legal & Security Track | Program Governance & Exit Criteria ("What Success Looks Like") |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 0: Kickoff & Baseline** | Weeks 1–2 | • Align scope, core platform API/SSO contracts, and non-modification boundary with US Tech PO.<br>• Finalize China cloud vendor RFP/selection criteria & test dataset spec. | • **Engage qualified local filing agent at kickoff.**<br>• Begin Data Security & Privacy classification review (PIPL/DSL/MLPS target tier vs. current posture).<br>• Initiate cloud contract legal redlines (gov't disclosure notification clause). | • Deliverables Log initialized with owners, rationale & downstream dependencies.<br>• **Jointly agree Pass/Fail LLM quality thresholds** *before* testing begins.<br>• Filing agent SOW signed with milestone gates. |
| **Gate 1: Isolated Cloud & Test Env Stand-Up** | Weeks 3–5 | • Provision China VPC, network isolation/segmentation, private egress, and external KMS key custody (**KEKs held outside China**).<br>• Deploy non-intrusive data-protection adapter & federated IdP bridge (OIDC/SAML) with **zero core codebase changes**. | • Submit preliminary regulatory filing package via filing agent.<br>• Lock clean, synthetic/sanitized **export-control-compliant test harness** reviewed with IDC legal & outside counsel.<br>• Document Data-Protected Architecture & Identity Federation specs. | • Test environment online & security baseline verified.<br>• Multi-week filing process in-flight with SLA check-ins (2x/week with agent) so it cannot become a late blocker.<br>• Dual toolchain live (`Jira/Asana/M365 ↔ WeCom/Feishu`). |
| **Gate 2: Parallel China LLM Eval & Build-Out** | Weeks 6–9 | • Run parallel evaluation of China-approved LLMs (`Qwen`, `DeepSeek`, `Ernie`, `GLM`) behind the sanitized gateway.<br>• Stand up supporting China production servers, logging/audit trails & failover. | • Conduct MLPS gap remediation & penetration/security testing.<br>• Complete formal DPIA / cross-border transfer assessment documentation with outside counsel. | • Reproducible **Model Evaluation Scorecard** signed off jointly with US Tech PO against pre-agreed pass/fail thresholds.<br>• Architecture & build-out docs finalized with verified zero raw-data leakage. |
| **Gate 3: Production Readiness & Go-Live** | Weeks 10–12+ | • Production deployment & cutover rehearsal.<br>• Verify key rotation/revocation drill, monitoring alerts, and zero impact on global core platform. | • Confirm required regulatory filings **approved or cleared for launch gate** with zero open blocking items.<br>• Legal sign-off on contract clauses & export-control dossier. | • **Production-ready China cloud environment validated ahead of go-live.**<br>• Steering Committee Go/No-Go sign-off with full RAID closure & zero surprise risks. |

---

## 4. Deep-Dive Q&A Scripts for the 6 Core Pillars

### Q1. China Regulatory Filings & Data Security Classification
**Likely Question:** *"How do you manage China regulatory filings end-to-end so a multi-week government review doesn't derail our go-live timeline, and how do you assess our required certification level?"*

**Verbatim Core Answer:**
> "I treat regulatory filings as a **critical-path engineering dependency starting in Week 1**, never as a legal checklist at the end.
>
> First, on **data classification and certification posture**: within the first two weeks, we classify every data element flowing in China under China's **Data Security Law (DSL)**, **PIPL**, and **MLPS 2.0 (等级保护)**: Does the platform store public/corporate market data, enterprise user identities, or sensitive personal/important data? That classification dictates whether we require **MLPS Level 2 or Level 3** certification, and whether cross-border identity/telemetry flows qualify under the **March 2024 CAC cross-border exemptions** or need a Standard Contract / Security Assessment with outside counsel. I document the *required certification tier vs. current posture* in a concise gap matrix so leadership knows the exact delta, cost, and timeline.
>
> Second, on **AI / CAC filings**: I distinguish early with outside counsel and our filing agent between registering a foundation model (`大模型备案`) versus **enterprise B2B deployment / Algorithm Filing (`算法备案`)**. If we integrate pre-registered commercial Chinese model APIs (such as Qwen via Alibaba Cloud Model Studio or Ernie) behind enterprise B2B agreements rather than fine-tuning and serving public C-end weights, we dramatically shrink approval scope and cycle time.
>
> Third, on **keeping the filing agent on track**: I select a qualified filing agent at kickoff using **milestone-gated SOW payments**—tied to complete dossier submission, acceptance receipt, and regulator Q&A turnaround SLAs—and track their sub-tasks inside our master deliverables log twice a week alongside technical stand-up, so no missing technical diagram or Chinese translation stalls the queue."

*Technical follow-up anchors if probed:*
- Emphasize having **technical architecture diagrams, data-flow inventories, and localized privacy policies** drafted *by engineering/PM in parallel with cloud provisioning*, rather than waiting for the filing agent to ask for them at Week 5.

---

### Q2. China Cloud Provisioning, Encryption Keys Held Outside China & Gov Disclosure Clauses
**Likely Question:** *"Walk us through how you would provision our China cloud infrastructure—specifically network isolation, holding encryption keys outside China, and contract protections."*

**Verbatim Core Answer:**
> "This comes down to three concrete controls built into the landing zone and vendor agreements before any production workload lands:
>
> 1. **Network Isolation & Segmentation:** We deploy inside an isolated China landing zone (Alibaba Cloud, Tencent Cloud, or AWS/Azure China depending on enterprise fit) using separate **Management, Application, and Egress VPCs/subnets**, strict security-group deny-by-default rules, private endpoints (PrivateLink) to approved China LLM APIs, and zero direct inbound public exposure to backend services or databases.
> 2. **Encryption with External Key Custody (Outside China):** We use **envelope encryption / HYOK-BYOK architecture** where Data Encryption Keys (DEKs) encrypt data at rest in China, while the root **Key Encryption Keys (KEKs) or master cryptographic control stay in a Western KMS / HSM / Secret Manager outside China**, with short-lived wrapped DEK leases, strict audit logging, and an immediate remote revocation ("kill switch") capability if unauthorized access or an unnotified compulsion event occurs. Note carefully: we verify early with legal whether the China cloud region's native KMS allows pure external key origin (HYOK) or whether application-layer envelope encryption in our adapter is cleaner—application-layer envelope wrapping is cloud-agnostic and guarantees keys never touch China cloud KMS storage.
> 3. **Government Disclosure Notification Clauses:** Before signing any China cloud MSA/order form, I partner with IDC legal and outside counsel to make **mandatory prior-notice / government disclosure notification clauses** (requiring the provider to notify IDC promptly upon any government data request, unless legally prohibited, and to challenge overbroad orders) a **non-negotiable procurement gate** alongside local SLAs."

---

### Q3. Data-Protected Architecture, Identity Federation & "Zero Core Platform Codebase Changes"
**Likely Question:** *"Our US product team requires that none of this China build-out modifies the core platform codebase, and no raw data can reach Chinese model providers. How do you verify and document that?"*

**Verbatim Core Answer:**
> "The architectural pattern here is a **non-intrusive Edge Adapter / Strangler Proxy** sitting in front of the China environment—the core US codebase stays completely untouched:
>
> 1. **Zero Core Codebase Changes via OpenAI-Compatible Gateway:** Assuming the core platform invokes LLMs through configurable endpoints, schemas, and OIDC/SAML authentication, all China adaptation lives in a standalone **China Integration Layer / LLM Gateway** configured strictly via environment/config injection (endpoint URLs, token issuers, routing headers). No forks, no `if country == 'CN'` branches inside core platform repositories. We explicitly prove this by keeping core platform repo diffs at zero and managing all China components in an isolated deployment repo/pipeline.
> 2. **Identity Federation Design:** User authentication uses **SAML 2.0 / OIDC federation** to the enterprise global IdP, issuing scoped, short-lived, pseudonymized JWT tokens (`sub` pseudonyms + minimal role claims) to the China runtime—so full HR/customer directories never replicate onto China servers.
> 3. **Pre-Inference Data Protection Layer:** Before any request crosses out of our isolated VPC to a China-approved model API, a local **Sanitization & Context-Minimization Pipeline** inside our VPC strips PII, internal client identifiers, credentials, and raw proprietary datasets—passing only anonymized, structured snippets or placeholders—and enforces enterprise ZDR (**Zero Data Retention** / no-training-on-API-prompts) contractual terms with the commercial API tier. Everything is documented in a living **Data-Protected Architecture & Data Flow Diagram** signed off by security and the US Tech PO."

---

### Q4. Parallel Evaluation of China-Approved LLMs & Export Control Test Structure
**Likely Question:** *"How will you run parallel evaluations across China-approved LLMs so leadership can trust the decision, while keeping export control happy?"*

**Verbatim Core Answer:**
> "Credibility with both leadership and legal rests on **pre-commitment** and **clean test hygiene**:
>
> 1. **Pre-Agreed Pass/Fail Thresholds (Zero Moving Goalposts):** Before executing a single evaluation run, I work with the US Technical Product Owner to lock a weighted pass/fail rubric in writing:
>    - **Functional / Reasoning Accuracy** (domain tasks vs. global baseline on a golden test set),
>    - **Structured Output & Schema Compliance** (JSON/tool-call parse rate >= threshold—critical if core platform uses structured agents),
>    - **Grounding & Hallucination Rate** (citation accuracy on RAG/enterprise context),
>    - **Operational SLAs** (TTFT, p95 latency, concurrency limits, rate-limit stability), and
>    - **Content Filter / Refusal Rate** on benign business/geopolitical/compliance queries (testing edge cases where domestic censorship filters might unexpectedly break enterprise workflows).
> 2. **Parallel Model Harness:** We run the identical frozen evaluation suite in parallel across candidates—typically **Alibaba Qwen (Max / 2.5 / 3), DeepSeek (V3 / R1 enterprise hosted in China), Baidu Ernie 4.0, and Zhipu GLM-4**—under identical temperature, prompt templates, and token budgets, producing a side-by-side statistical pass/fail scorecard with failure-mode taxonomy.
> 3. **Clean Structure for Export Control & Legal Review:** To support US export control review cleanly, the evaluation harness uses **strictly synthetic, public, or formally cleared non-controlled datasets** (zero proprietary US defense/controlled dual-use IP or real PII), maintains immutable audit logs of *who ran what prompt on which endpoint/region with which model version*, and ships zero US-origin restricted weights/code into the China harness."

---

### Q5. Day-to-Day Program Governance, Dual-Toolchain & "Zero-Surprise" Escalation
**Likely Question:** *"How do you manage day-to-day execution across Beijing engineering/vendors and US leadership without things falling between WeCom/Feishu and Jira/Asana/M365?"*

**Verbatim Core Answer:**
> "I enforce a strict **Single Source of Truth vs. Local Execution Velocity** separation:
>
> - **Dual-Toolchain Workflow:** China-based vendors, filing agents, and local engineers work daily in **WeCom / Feishu / DingTalk** so nothing slows down local execution. However, **Asana / Monday / Jira and Microsoft 365 remain the authoritative system of record** for milestones, deliverables, decisions, and RAID items. I run automated AI-assisted summaries—extracting daily Chinese chat blockers and decision confirmations into structured English updates in Jira/Asana and weekly M365 executive briefs—so the US team never has to chase translations or screenshot threads.
> - **Deliverables Log with Rationale & Downstream Dependencies:** Every deliverable in the log tracks not just `% complete` and owner, but **Decision Rationale** (why we chose X over Y, e.g., cloud envelope encryption vs. native KMS) and **Flagged Downstream Dependencies** (e.g., *'Delayed filing confirmation from Agent slips Gate 3 legal review by 5 days -> impacts prod DNS cutover'*).
> - **Zero-Surprise Steering Committee Escalation:** My rule is that a Steering Committee should **never discover a high-rated risk after it has turned red**. Whenever a risk crosses our trigger threshold, I escalate immediately to the China Country Lead and US Program Representative with a 1-page structured brief: **(1) What changed, (2) Quantified milestone/budget blast radius, (3) Option A & Option B mitigations with trade-offs, and (4) Recommended decision needed by [Date].**"

---

### Q6. Prior Budget Responsibility & Vendor Accountability
**Likely Question:** *"Tell us about your budget responsibility on comparable engagements and how you keep China cloud/consulting spend under control."*

**Verbatim Core Answer:**
> "I've owned full P&L and multimillion-RMB engagement budgets across **Sino Convergence**, **ITpreneurs APAC** (where I grew regional delivery operations by 150%), and multinational localization programs for **BMW China, Umicore, Sika, and ZF** under Next Level Consulting.
>
> For this program, budget discipline focuses on four buckets: **(1) China Cloud Commit & API token burn**, **(2) Qualified Filing Agent SOWs**, **(3) MLPS security testing & audit lab fees**, and **(4) External legal review**. I run **milestone-based holdbacks** on local filing/SI vendors, cap token consumption on parallel LLM evals via deterministic batch quotas before testing begins, track committed vs. forecast burn bi-weekly against contingency reserves, and route any scope change affecting the core boundary or budget through formal Steering Committee change control."

---

## 5. Optional 2-Minute Live Screen-Share Playbook

> **Rule of Thumb:** Do **NOT** interrupt the flow to pitch a demo unprompted. Only offer it if the conversation naturally touches **LLM evaluation harnesses**, **hybrid US-China cloud isolation**, or **cross-border regulatory auditing**—for example, toward the end of technical Q&A:  
> *"If it's helpful and we have two minutes, I actually built a live dual-cloud AI evaluation platform and a cross-border regulatory audit cockpit running right now—happy to share my screen briefly to show the exact hybrid architecture and deterministic evaluation gates in practice."*

> **✅ Branding fixed (Nov 18, 2026):** the demo is now the **"ARF Analyst Desk — Vendor Quadrant & AI Spending"** page at `https://stock.thekingfilter.com/analyst-desk`. All IDC Quanta™ / MarketScape™ / "Copyright © IDC" strings were removed from the page, generated reports, and file names; reported methodology is now described as ARF's own, modelled on the public quadrant format. Legacy `/IDC_MarketScape` links still resolve to the renamed page.

### If They Say Yes — Tight 2-Minute Walkthrough Script
1. **Tab 1 — Cross-Border Compliance Cockpit (`https://ciso.thekingfilter.com/ui/jpmc-cockpit`) [45 sec]:**
   - Show how multinational Western cloud/security standards map cleanly against China regulatory controls (CAC cross-border export rules, PIPL, MLPS Level 3), proving hands-on fluency with audit evidence and compliance gap tracking.
2. **Tab 2 — Hybrid US/China AI Platform & Evaluation Gates (`https://stock.thekingfilter.com/analyst-desk`) [60 sec]:**
   - Explain the **production architecture** behind the live screen: **global GCP compute + Western Secret Manager** isolated from **domestic China Tencent Cloud infrastructure**, with **local DuckDB/Python computing sensitive data cleanly on-box** so zero raw financial datasets leak to model APIs, and **deterministic G1–G4 evaluation gates** checking model outputs against hard quality thresholds before acceptance.
   - *(Notice this also subtly signals deep familiarity with IDC's core MarketScape domain without overclaiming or dropping internal codenames!)*

---

## 6. Top 5 High-Impact Questions to Ask the US Interviewer

Ask **2 to 3** of these at the end—prioritize based on whether your interviewer leans Technical Product Owner (#1, #2, #3) or Program Representative (#4, #5):

1. **"On the architecture boundary: is the core platform already abstracted behind an OIDC/SAML IdP and configurable OpenAI-compatible LLM endpoints, or are there remaining coupling points we need to wrap in Phase 1?"** *(Shows you already think in zero-codebase-change adapter patterns.)*
2. **"As the US Technical Product Owner / Program Lead, which failure mode in China LLMs worries you most right now—structured JSON/tool-calling reliability, reasoning parity, latency, or unexpected domestic safety filter refusals?"** *(Gets their real pain point on the table immediately.)*
3. **"Where do things currently stand on choosing the China cloud provider, outside counsel, and filing agent—are those vendor selections already contracted, or will selecting and onboarding the filing agent be one of my Week 1 deliverables?"** *(Helps calibrate your exact Day 1 plan.)*
4. **"What does the current Steering Committee cadence look like between Beijing and the US, and what reporting format has worked best (or failed) for you on past cross-border launches?"** *(Shows pragmatic dual-toolchain governance empathy.)*
5. **"Fast-forwarding 90 days into this contract—what specific milestone, if completed cleanly with zero surprises, would make you feel confident the launch is de-risked?"** *(Defines the exact win bar.)*

---

## Appendix A: China Regulatory Filings & Data Security Classification Cheat Sheet (2025–2026)

### A1. The 5-Layer China Regulatory Filing Stack
Launching an enterprise AI platform in Mainland China involves up to five filings across three regulators (**MIIT**, **MPS/PSB**, and **CAC**). Knowing which tracks are mandatory, which are simplified, and which can be avoided via clean architecture prevents costly multi-month delays:

| # | Filing / License | Regulator | Trigger & Applicability | Lead Time & Execution Lever |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **ICP Filing (`ICP备案`)** *(vs. ICP Commercial License)* | **MIIT** (via China cloud vendor) | Hosting any web UI, domain, or API on a Mainland China server. Must be filed under the **local onshore China legal entity** (e.g., IDC Beijing WFOE), never a foreign parent. | **2–4 weeks.** Hard technical gate: China cloud firewalls block HTTP/HTTPS on unfiled domains. |
| **2** | **PSB Networking Filing (`公安联网备案`) + MLPS 2.0 (`等保2.0`)** | **MPS / Local Public Security Bureau (PSB)** | PSB networking filing within 30 days of launch; MLPS Level 2 or Level 3 grading & filing under **GB/T 22239-2019**. | **3–6 months** end-to-end (Scoping → Expert Review → PSB Filing Certificate → Remediation & Licensed Lab Testing `测评`). |
| **3** | **CAC AI Application Registration (`大模型登记`) vs. Model Filing (`大模型备案`)** | **Provincial CAC** (registration) / **National CAC** (full filing) via **`beian.cac.gov.cn`** | • **Full Model Filing (`大模型备案`, 6–8+ mos):** Training, pre-training, or substantially fine-tuning a public model.<br>• **Application Registration (`大模型登记`, 1–3 mos):** Calling an **already-filed China commercial LLM API** (Qwen, DeepSeek, Ernie, Doubao) with no weight modifications; must display upstream model name + filing number in UI.<br>• **Internal-Only Exemption:** Strictly internal enterprise use (zero public `境内公众` access) is generally exempt from GenAI public filings (CSL/DSL/PIPL/MLPS still apply). | **Key Architectural Lever:** Consuming pre-filed commercial APIs behind a non-intrusive gateway avoids a 6–8 month national filing bottleneck. |
| **4** | **Algorithm Filing (`算法备案`) + AI Content Labeling (`GB 45438-2025`)** | **CAC** (`beian.cac.gov.cn`) | Generative/synthesis or ranking algorithms with public-opinion / social-mobilization attributes. Under the **Sept 1, 2025** labeling rules + **GB 45438-2025**, public AI services must apply both **explicit** (visible UI notice) and **implicit** (file metadata) labels. | **1–3 months** (submitted alongside `大模型登记` on the consolidated CAC portal). Content-labeling headers/notices can be injected at the China Edge Gateway with zero core codebase changes. |
| **5** | **Cross-Border Data Transfer (CBDT) Filing** | **CAC** | Only triggered if **Important Data** or **Personal Information (PI)** above statutory annual thresholds leaves Mainland China (e.g., telemetry, logs, user directories). | **Exempt** if designed cleanly under March 2024 thresholds (see A2 below). |

### A2. China Data Security Classification Standards & Thresholds
- **GB/T 43697-2024 (*Rules for Data Classification and Grading*, effective Oct 1, 2024):** Operationalizes Data Security Law (DSL) Art. 21 via a 3-step method (*Industry Sector → Business Attribute/Process → Compromise Impact Matrix*), classifying data into three tiers:
  1. **Core Data (`核心数据`):** Direct political security, national security lifelines, or major public interest impact. Strictest prohibitions.
  2. **Important Data (`重要数据`):** Sector/region-specific data impacting economic operations, social stability, or public health/safety—identified via regulator-issued **Important Data Catalogs**. *Critical exclusion:* data whose impact is limited solely to a single enterprise or individual is generally **not** Important Data.
  3. **General Data (`一般数据`):** Everything outside Core and Important Data (routine commercial/enterprise data, typically sub-graded internally Levels 1–4 for access and encryption controls).
- **Network Data Security Management Regulation (`《网络数据安全管理条例》`, State Council Decree No. 790, effective Jan 1, 2025):** Unifies execution of **CSL + DSL + PIPL**, requiring handlers of Important Data to maintain formal catalogs, appoint a dedicated data security officer, and run annual risk assessments.
- **MLPS 2.0 (`GB/T 22239-2019` & `GB/T 22240`):**
  - **Level 2:** General enterprise systems / limited-impact internal apps; PSB filing mandatory, typically reassessed every **2 years**.
  - **Level 3:** Core business/commercial platforms or large user repositories; mandatory **pre-launch + annual** licensed lab evaluation (`测评机构`), expert review (`专家评审`), and *"One Center, Three Defenses"* (`一个中心，三重防护`: centralized audit/security ops + network, perimeter, and compute protection, WAF, DB audit, ≥6-month log retention).
  - **Cloud Shared-Responsibility Caveat:** Hosting on Alibaba Cloud / Tencent Cloud (whose physical IaaS holds MLPS Level 3) **does not make the tenant compliant**—IDC remains the legal *"Network Operator"* for its VPC, servers, databases, identity federation, and app layer.
- **Cross-Border Data Flow Thresholds (CAC Order No. 16 — March 22, 2024) + Beijing FTZ Negative List:**
  - Calculated **cumulatively from January 1 of the calendar year** for non-CIIOs:
    - **`< 100,000` non-sensitive PI individuals / year:** **Exempt** from CAC Security Assessment, Standard Contract (SCC), and certification.
    - **`100,000 – 1,000,000` non-sensitive PI** (and `< 10,000` sensitive PI): Standard Contract (SCC) filing or PI certification.
    - **`≥ 1,000,000` non-sensitive PI**, **`≥ 10,000` sensitive PI**, or **any Important Data**: Mandatory formal CAC Security Assessment.
  - **Beijing Entity Advantage:** Entities registered inside the **China (Beijing) Pilot Free Trade Zone** follow the **Beijing FTZ Data Export Negative List** first—transfers outside negative-list scenarios use simplified export channels.
- **Generative AI Safety & Labeling Standards (`GB/T 45654-2025` & `GB 45438-2025`):** **GB/T 45654-2025** (formalized from **TC260-003**) codifies testable security clauses (corpus IP/legality provenance, refusal benchmarks, safety moderation) used during CAC filing evaluations; **GB 45438-2025** governs explicit + implicit synthetic content labeling effective **Sept 1, 2025**.

### A3. 4 Practitioner Soundbites for the US Interviewer
1. **Architecture Drives Compliance Scope:** *"By calling already-filed China commercial model APIs via a non-intrusive gateway—with zero model weight fine-tuning—we stay out of the 6–8 month national `大模型备案` track and keep scope to provincial registration (or internal-use exemption if not public-facing)."*
2. **No False Security from Cloud Vendor Badges:** *"Cloud IaaS MLPS Level 3 certificates cover Alibaba or Tencent's infrastructure, not our application. We still own tenant-level MLPS Level 2/3 scoping, PSB filing, and licensed testing on our VPC, WAF, DB audit, and 180-day logs."*
3. **Engineering Below Cross-Border Filing Thresholds:** *"By pairing OIDC/SAML pseudonymized tokens with GB/T 43697-2024 classification showing zero Core or Important Data, routine cross-border operational telemetry stays comfortably under the March 2024 100,000 non-sensitive PI exemption."*
4. **Zero Core Codebase Impact Even for Sept 2025 AI Labeling:** *"Explicit and implicit AI content labels required under GB 45438-2025 can be injected cleanly inside the China Edge Gateway/adapter layer—zero changes to the US core platform codebase."*

---

## 7. Quick Pre-Call Checklist (Friday Night / Saturday Morning BJT)
- [ ] Join 5 minutes early; quiet room, strong wired/fiber connection, clean lighting (US Friday evening calls appreciate crisp audio/video).
- [ ] Open in two pinned browser tabs (ready only if invited):
  - `https://stock.thekingfilter.com/analyst-desk` (check English toggle active)
  - `https://ciso.thekingfilter.com/ui/jpmc-cockpit`
- [ ] Keep this playbook and the LinkedIn JD PDF open on a second monitor / side pane for rapid bullet reference.
- [ ] Core posture to hold throughout: **Calm, concise, US-engineering fluent, Beijing-street smart, zero-surprise execution.**

