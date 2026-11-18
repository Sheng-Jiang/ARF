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

## 7. Quick Pre-Call Checklist (Friday Night / Saturday Morning BJT)
- [ ] Join 5 minutes early; quiet room, strong wired/fiber connection, clean lighting (US Friday evening calls appreciate crisp audio/video).
- [ ] Open in two pinned browser tabs (ready only if invited):
  - `https://stock.thekingfilter.com/analyst-desk` (check English toggle active)
  - `https://ciso.thekingfilter.com/ui/jpmc-cockpit`
- [ ] Keep this playbook and the LinkedIn JD PDF open on a second monitor / side pane for rapid bullet reference.
- [ ] Core posture to hold throughout: **Calm, concise, US-engineering fluent, Beijing-street smart, zero-surprise execution.**

