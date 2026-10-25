# -*- coding: utf-8 -*-
"""论文正文（单一来源）：build_tex.py 与 build_docx.py 都从这里取内容，避免两份手抄不一致。"""
# -*- coding: utf-8 -*-
from __future__ import annotations

TITLE = ("Rule-Enhanced Personalized LLM Agents for Substation Operation and "
         "Maintenance Training: Architecture, Deployment, and a Rule-Set Audit")

AUTHORS = "[Author One], [Author Two], and [Author Three]"
AFFIL = "[School / Company], [City], [Country]\nCorresponding author: [email@example.com]"

KEYWORDS = ("substation operation and maintenance; personalized training; large language model; "
            "declarative rule engine; guardrail; explainability; human-in-the-loop")

ABSTRACT = (
    "Training in a substation operation and maintenance (O&M) centre must satisfy hard safety-code "
    "constraints while adapting to the competence profile of each employee. Fixed curricula cannot "
    "adapt, whereas a purely generative large language model (LLM) may produce recommendations that "
    "violate operating codes or cannot be traced to any verifiable fact. Retrieval-augmented "
    "generation (RAG) narrows the factual gap but remains a soft constraint, because retrieved text "
    "does not itself enforce anything. This paper presents a rule-enhanced personalized agent that is "
    "being deployed in a substation O&M centre. The design separates a rule layer, a computation "
    "layer and a decision layer, so that a database-resident JSON rule set—not prompt text—owns the "
    "safety gate. Model output is accepted only if it passes contract, fact-consistency, permission "
    "and safety checks; otherwise the system falls back to the deterministic rule path and records "
    "why. A single run identifier links every execution to its rule hits, its suggestion, and the "
    "human decision, so that every conclusion can be traced to a rule code and a data point. We "
    "contribute a replay-based rule-set audit methodology and an open evaluation harness. Replaying "
    "18 production rules over 150 real employee profiles (450 executions) shows that the engine is "
    "100% deterministic and order-invariant with sub-millisecond in-process evaluation, but the audit "
    "also exposes three concrete defects: an examination threshold hard-coded at 60 against business "
    "pass lines of 80/85 that silently misses 80.0% of failing scores; a competence-level gate "
    "hard-coded at L3 that misses 62.7% of real gaps; and an unreachable terminal rule that escalates "
    "every comfortable gas reading to a medium alert. Cross-checking model-style reference outputs "
    "against the same profiles further reveals a specification ambiguity between position requirement "
    "and task authorisation threshold that accounts for 25.3% of level inconsistencies. We argue that "
    "in safety-critical training the guardrail layer guarantees correctness, while coverage must be "
    "shared between configurable rules and model expression."
)

# ---------------------------------------------------------------- 引用编号

REFS = [
 ("Lewis P, Perez E, Piktus A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks. "
  "Advances in Neural Information Processing Systems (NeurIPS), 2020, 33: 9459-9474. "
  "https://doi.org/10.48550/arXiv.2005.11401"),
 ("Hu E J, Shen Y, Wallis P, et al. LoRA: low-rank adaptation of large language models. "
  "International Conference on Learning Representations (ICLR), 2022. "
  "https://doi.org/10.48550/arXiv.2106.09685"),
 ("Yao S, Zhao J, Yu D, et al. ReAct: synergizing reasoning and acting in language models. "
  "International Conference on Learning Representations (ICLR), 2023. "
  "https://doi.org/10.48550/arXiv.2210.03629"),
 ("Wei J, Wang X, Schuurmans D, et al. Chain-of-thought prompting elicits reasoning in large language models. "
  "Advances in Neural Information Processing Systems (NeurIPS), 2022, 35: 24824-24837. "
  "https://doi.org/10.48550/arXiv.2201.11903"),
 ("Ouyang L, Wu J, Jiang X, et al. Training language models to follow instructions with human feedback. "
  "Advances in Neural Information Processing Systems (NeurIPS), 2022, 35: 27730-27744. "
  "https://doi.org/10.48550/arXiv.2203.02155"),
 ("Bai Y, Kadavath S, Kundu S, et al. Constitutional AI: harmlessness from AI feedback. "
  "arXiv preprint, 2022. https://doi.org/10.48550/arXiv.2212.08073"),
 ("Shinn N, Cassano F, Gopinath A, et al. Reflexion: language agents with verbal reinforcement learning. "
  "Advances in Neural Information Processing Systems (NeurIPS), 2023, 36. "
  "https://doi.org/10.48550/arXiv.2303.11366"),
 ("Rebedea T, Dinu R, Sreedhar M, et al. NeMo Guardrails: a toolkit for controllable and safe LLM "
  "applications with programmable rails. Proc. EMNLP 2023 (Demo), 2023. "
  "https://doi.org/10.48550/arXiv.2310.10501"),
 ("Ji Z, Lee N, Frieske R, et al. Survey of hallucination in natural language generation. "
  "ACM Computing Surveys, 2023, 55(12): 1-38. https://doi.org/10.1145/3571730"),
 ("Zhao W X, Zhou K, Li J, et al. A survey of large language models. arXiv preprint, 2023. "
  "https://doi.org/10.48550/arXiv.2303.18223"),
 ("Gao Y, Xiong Y, Gao X, et al. Retrieval-augmented generation for large language models: a survey. "
  "arXiv preprint, 2023. https://doi.org/10.48550/arXiv.2312.10997"),
 ("Qwen Team. Qwen2.5 technical report. arXiv preprint, 2024. "
  "https://doi.org/10.48550/arXiv.2412.15115"),
 ("Zheng Y, Zhang R, Zhang J, et al. LLaMA-Factory: unified efficient fine-tuning of 100+ language models. "
  "Proc. ACL 2024 (System Demonstrations), 2024. https://doi.org/10.48550/arXiv.2403.13372"),
 ("Forgy C L. Rete: a fast algorithm for the many pattern / many object pattern match problem. "
  "Artificial Intelligence, 1982, 19(1): 17-37. https://doi.org/10.1016/0004-3702(82)90020-0"),
 ("Majumder S, Dong L, Doudi F, et al. Exploring the capabilities and limitations of large language models "
  "in the electric energy sector. Joule, 2024, 8(6): 1599-1608. https://doi.org/10.1016/j.joule.2024.05.009"),
 ("Piech C, Bassen J, Huang J, et al. Deep knowledge tracing. "
  "Advances in Neural Information Processing Systems (NeurIPS), 2015, 28: 505-513. "
  "https://doi.org/10.48550/arXiv.1506.05908"),
 ("Neshaei S P, Davis R L, Hazimeh A, et al. Towards modeling learner performance with large language "
  "models. arXiv preprint, 2024. https://doi.org/10.48550/arXiv.2403.14661"),
 ("Cho Y, AlMamlook R E, Gharaibeh T. A systematic review of knowledge tracing and large language models "
  "in education: opportunities, issues, and future research. arXiv preprint, 2024. "
  "https://doi.org/10.48550/arXiv.2412.09248"),
 ("Li Z, Wang J, Gu W, et al. TutorLLM: customizing learning recommendations with knowledge "
  "tracing and retrieval-augmented generation. Human-Computer Interaction - INTERACT 2025, "
  "LNCS, 2025: 137-146. https://doi.org/10.1007/978-3-032-05005-2_8"),
 ("Wang X, Wei J, Schuurmans D, et al. Self-consistency improves chain of thought reasoning in language "
  "models. International Conference on Learning Representations (ICLR), 2023. "
  "https://doi.org/10.48550/arXiv.2203.11171"),
 ("Xi Z, Chen W, Guo X, et al. The rise and potential of large language model based agents: a survey. "
  "arXiv preprint, 2023. https://doi.org/10.48550/arXiv.2309.07864"),
 ("Huang L, Yu W, Ma J, et al. A survey on hallucination in large language models: principles, taxonomy, "
  "challenges, and open questions. ACM Transactions on Information Systems, 2025, 43(2): 1-55. "
  "https://doi.org/10.1145/3703155"),
]

# ---------------------------------------------------------------- 公式（token DSL）
# 元素类型：str = 正体文本；("i", text) = 斜体；("sub", [..]) 下标；("sup", [..]) 上标；
#          ("frac", [num..], [den..]) 分数


def I(t): return ("i", t)


def SUB(*t): return ("sub", list(t))


def SUP(*t): return ("sup", list(t))


def FR(num, den): return ("frac", num, den)


EQ = {}
EQ[1] = [I("G"), SUB(I("i"), ",", I("k")), " = max(0, ", I("R"), SUB(I("i"), ",", I("k")),
         " − ", I("S"), SUB(I("i"), ",", I("k")), ")"]
EQ[2] = [I("F"), SUB(I("i"), ",", I("k")), " = max(0, ", I("D"), SUB(I("i"), ",", I("k")),
         " − ", I("S"), SUB(I("i"), ",", I("k")), ")"]
EQ[3] = [I("Pr"), SUB(I("i"), ",", I("k")), " = ", I("w"), SUB("1"), I("G"), SUB(I("i"), ",", I("k")),
         " + ", I("w"), SUB("2"), I("F"), SUB(I("i"), ",", I("k")),
         " + ", I("w"), SUB("3"), I("E"), SUB(I("i"), ",", I("k")),
         " + ", I("w"), SUB("4"), I("Q"), SUB(I("i"), ",", I("k")),
         " + ", I("w"), SUB("5"), I("C"), SUB(I("i"), ",", I("k")),
         " + ", I("w"), SUB("6"), I("A"), SUB(I("i"), ",", I("k"))]
EQ[4] = [I("p"), SUB(I("i"), ",", I("k")), " = ", I("P1"), "  if ", I("Pr"), SUB(I("i"), ",", I("k")),
         " ≥ ", I("θ"), SUB("1"), ";   ", I("P2"), "  if ", I("θ"), SUB("2"), " ≤ ",
         I("Pr"), SUB(I("i"), ",", I("k")), " < ", I("θ"), SUB("1"), ";   ", I("P3"), "  otherwise"]
EQ[5] = [I("y"), " = ", I("f"), SUB("model"), "(", I("x"), ")  if ", I("Valid"), "(", I("x"),
         ") = true;   ", I("f"), SUB("rule"), "(", I("x"), ")  otherwise"]
EQ[6] = [I("ρ"), " = ", FR([I("u"), " − ", I("u"), SUB("0")], [I("u"), SUB("max"), " − ", I("u"), SUB("0")])]
EQ[7] = [I("s"), SUP("*"), " = ", I("s"), SUB("j"), ",   j = arg max", SUB("h ∈ H"),
         " rank(", I("s"), SUB("h"), ")"]
EQ[8] = [I("m"), SUB("exam"), " = ", FR(["|{ ", I("i"), " : ", I("e"), SUB("i"), " < ",
         I("e"), SUB("pass,i"), " ∧ ¬", I("fired"), "(", I("i"), ") }|"], ["N"]),
         ",     ", I("N"), " = 150"]

# ---------------------------------------------------------------- 表格数据

T_APPROACH = {
  "num": "1", "caption": "Comparison of representative training-agent approaches.",
  "header": ["Approach", "Strength", "Main limitation", "Constraint enforcement"],
  "rows": [
    ["Fixed courseware system", "Human-reviewed content; stable deployment",
     "One path for everyone; cannot reflect individual gaps", "Editorial, not runtime"],
    ["Pure LLM agent", "Interactive; flexible case generation",
     "Code hallucination; uncontrollable output", "None beyond the prompt"],
    ["RAG training agent", "Grounded in regulation text",
     "Soft constraint; no hard interception; no profile-driven path", "Soft (retrieval only)"],
    ["Rule-enhanced personalized agent (ours)", "Rigid safety boundary + profile adaptation + model expression",
     "Rule base must be maintained and audited", "Hard, declarative, auditable"],
  ]}

T_LAYERS = {
  "num": "2", "caption": "Three-layer responsibility split. The engine writes only rule_result.",
  "header": ["Layer", "Table", "Question answered"],
  "rows": [
    ["Rule layer (configuration)", "rule", "What rules are configured"],
    ["Computation layer (this run)", "rule_result", "What was computed, which rules fired, why"],
    ["Decision layer (governance)", "agent_suggestion + decision_log",
     "Who was advised and how a human decided"],
  ]}

T_OPS = {
  "num": "3", "caption": "Condition-operator whitelist of the declarative rule DSL (v1).",
  "header": ["Category", "Operators"],
  "rows": [
    ["Numeric (Decimal arithmetic)", "eq, ne, gt, gte, lt, lte, between"],
    ["Set membership", "in, not_in"],
    ["Text", "contains, not_contains, contains_any, starts_with, ends_with"],
    ["Boolean / existence", "is_true, is_false, exists, missing"],
    ["Combinators (nestable)", "all (AND), any (OR), not (NOT)"],
    ["Cross-fact comparison", "value replaced by other_fact to compare two facts"],
  ]}

T_INVENTORY = {
  "num": "4", "caption": "Production rule inventory extracted from the migration scripts.",
  "header": ["Scene", "Rules", "Group", "Codes"],
  "rows": [
    ["PERSONAL_GAP", "1", "default", "SKILL_GAP_L3"],
    ["EXAM_RESULT", "1", "default", "EXAM_LOW_SCORE"],
    ["TALENT_GAP", "2", "default", "BACKUP_SHORTAGE, FUTURE_DEMAND_GAP"],
    ["REPORT_ANALYSIS", "2", "default", "PRACTICE_SKILL_CAUSE, PRACTICE_HUMAN_CAUSE"],
    ["REPORT_GAS", "12", "VALUE (5) + KEYWORD (7)",
     "REPORT_GAS_OVER_MARGIN_{HIGH,MID,LOW}, REPORT_GAS_WITHIN_NEAR, REPORT_GAS_WITHIN; "
     "RULE-KW-{LEAK,DECOMP,HEAT,PD,MOISTURE,HEALTH,WORSENING}"],
  ]}

T_ADAPTER = {
  "num": "5", "caption": "Fact-adapter specification used in the replay. Only profile text is read.",
  "header": ["Profile field (source text)", "Fact", "Scene"],
  "rows": [
    ["Certificate: “... L1 资格”", "current_level", "PERSONAL_GAP"],
    ["Career goal: “关键任务：倒闸操作票复核达到L4”", "required_level", "PERSONAL_GAP"],
    ["Career goal: “目标等级：L4”", "future_level", "PERSONAL_GAP"],
    ["Safety record: “越权操作 / 无票作业 / 未监护 / ...”", "safety_risk (0–2), safety_violation", "PERSONAL_GAP, REPORT_ANALYSIS"],
    ["Exam: “考试58分，合格线85分”", "score, pass_score", "EXAM_RESULT"],
    ["Practical task: “计划2.6小时，实际2.9小时”", "actual_hours_ratio", "REPORT_ANALYSIS"],
    ["Safety record (authorisation violations)", "sop_preparation", "REPORT_ANALYSIS"],
  ]}

T_STACK = {
  "num": "6", "caption": "Deployment stack and evaluation configuration.",
  "header": ["Item", "Value"],
  "rows": [
    ["Backend", "Spring Boot 3.5.16, spring-boot-starter-jdbc (JdbcTemplate, no ORM), SpringDoc OpenAPI"],
    ["Database", "MySQL 8, single schema train_system; rules and verdicts stored in JSON columns"],
    ["Frontend", "Vue 3 + Vite + Element Plus; relative /api/v1 proxied by nginx to backend:8080"],
    ["Packaging", "docker-compose (MySQL + API + Web)"],
    ["Auth", "HMAC-signed bearer token; path-prefix authorisation; four roles with data scopes"],
    ["Base model", "Qwen2.5-7B-Instruct (bf16 weights, 4-bit bitsandbytes quantisation at serving)"],
    ["Fine-tuning toolkit", "LLaMA-Factory, Alpaca-format dataset"],
    ["Serving sampling", "temperature 0.7, top_k 20, top_p 0.8, repetition_penalty 1.05"],
    ["SFT corpus", "150 Alpaca-style samples, one instruction, 11-key JSON output contract"],
  ]}

T_REPLAY = {
  "num": "7", "caption": "Replay coverage over 150 real profiles (450 executions).",
  "header": ["Scene", "Executions", "Matched", "Match rate", "Firing rules"],
  "rows": [
    ["PERSONAL_GAP", "150", "26", "17.3%", "SKILL_GAP_L3"],
    ["EXAM_RESULT", "150", "12", "8.0%", "EXAM_LOW_SCORE"],
    ["REPORT_ANALYSIS", "150", "127", "84.7%", "PRACTICE_SKILL_CAUSE (52), PRACTICE_HUMAN_CAUSE (75)"],
    ["Any rule fired", "150", "132", "88.0%", "—"],
  ]}

T_AUDIT = {
  "num": "8", "caption": "Rule-set audit: threshold drift, level hard-coding and safety coverage.",
  "header": ["Finding", "Value"],
  "rows": [
    ["EXAM_RESULT true positive (below pass line and fired)", "12"],
    ["EXAM_RESULT false negative (below pass line, not fired)", "120"],
    ["EXAM_RESULT false positive", "0"],
    ["Silent-miss rate m_exam  (Eq. 8)", "80.0%"],
    ["Recall against the business pass line", "9.1%"],
    ["Precision of the hard-coded threshold", "100%"],
    ["PERSONAL_GAP fired", "26"],
    ["PERSONAL_GAP missed because required_level ≠ 3", "94 (62.7%)"],
    ["PERSONAL_GAP skipped as undecidable", "0"],
    ["Profiles with a future-axis gap and no rule to cover it", "120"],
    ["Profiles carrying a safety-negative record", "125 of 150 (83.3%)"],
    ["of which authorisation violations", "75 (50.0%)"],
    ["Safety negatives consumed by any rule", "0"],
  ]}

T_DETERMINISM = {
  "num": "9", "caption": "Determinism, order invariance and in-process latency.",
  "header": ["Metric", "Value"],
  "rows": [
    ["Executions measured", "450"],
    ["Byte-identical on repeat run", "450 / 450 (100%)"],
    ["Verdict identical after shuffling physical rule order", "450 / 450 (100%)"],
    ["Mean in-process evaluation time", "0.0082 ms"],
    ["p50 / p95 / max", "0.0074 / 0.0128 / 0.0334 ms"],
  ]}

T_GUARDRAIL = {
  "num": "10", "caption": "Guardrail audit of 150 structured reference outputs.",
  "header": ["Check", "Pass rate"],
  "rows": [
    ["11-key output contract complete", "100%"],
    ["Level arithmetic job_gap / future_gap consistent", "100%"],
    ["National skill-level mapping consistent", "100%"],
    ["Priority order consistent with gap magnitude", "100%"],
    ["Learning-path deadlines strictly increasing", "100%"],
    ["Safety boundary contains an authorisation element", "100%"],
    ["Quantitative baseline equals profile values", "100%"],
    ["Evidence items traceable to the profile", "100%"],
    ["Evidence covers ≥ 4 fact categories", "100%"],
    ["Safety negative explicitly addressed in the output", "100%"],
    ["Gap levels equal the profile-derived facts", "74.7%"],
    ["Numbers traceable to the profile (2 324 numbers)", "99.8% (4 unverifiable)"],
    ["Outputs containing at least one unverifiable number", "2.7%"],
  ]}

T_GROUP = {
  "num": "11", "caption": "Group-semantics verification on a 200-case parameter grid.",
  "header": ["Semantic property", "Correct", "Accuracy"],
  "rows": [
    ["VALUE ladder, implemented condition", "200 / 200", "100%"],
    ["VALUE ladder, business intent from rule remark", "160 / 200", "80.0%"],
    ["KEYWORD group with max_hits = 3", "200 / 200", "100%"],
    ["Severity merge (most severe wins)", "200 / 200", "100%"],
    ["*_from fact indirection (120 applicable cases)", "120 / 120", "100%"],
  ]}

T_ABLATION = {
  "num": "12", "caption": "Ablation-style comparison on the same 150-profile corpus.",
  "header": ["Criterion", "Unguarded model output", "Rule layer (facts → rules)"],
  "rows": [
    ["Unverifiable-number rate", "2.7%", "0%"],
    ["Level-arithmetic failure rate", "0%", "0%"],
    ["Gap levels inconsistent with the profile", "25.3%", "0%"],
    ["Safety negative explicitly addressed", "100%", "0%"],
    ["Silent miss of sub-pass-line examinations", "—", "80.0%"],
    ["Silent miss of real competence gaps", "—", "62.7%"],
    ["Determinism (byte-identical repeat)", "not guaranteed", "100%"],
  ]}

TABLES = [T_APPROACH, T_LAYERS, T_OPS, T_INVENTORY, T_ADAPTER, T_STACK,
          T_REPLAY, T_AUDIT, T_DETERMINISM, T_GUARDRAIL, T_GROUP, T_ABLATION]

# ---------------------------------------------------------------- 正文

BODY = [
 ("h1", "I. Introduction"),
 ("p",
  "Substation operation and maintenance (O&M) centres are moving from experience-driven to "
  "data-assisted operation. Competence in this setting is not a single skill level: it is shaped by "
  "examination results, field experience, certificate validity, safety records and team collaboration. "
  "A training system that only stores courses, examinations and personnel files cannot answer the "
  "questions that actually matter for talent development—why this employee needs this competence now, "
  "which data the recommendation rests on, and whether a human has confirmed the resulting action."),
 ("p",
  "Large language models (LLMs) make conversational, case-rich training feasible, and LLM-based agents "
  "have been applied across the electric energy sector [15], [21]. Three limitations are specific to "
  "safety-critical industrial training. First, a purely generative agent can hallucinate regulation "
  "content [9], [22] or produce recommendations that contradict an operating code. Second, "
  "retrieval-augmented generation (RAG) [1], [11] grounds the answer in retrieved text but is still a "
  "soft constraint: retrieval does not enforce anything, so a confidently phrased violation can still "
  "reach a learner. Third, personalisation requires a persistent, structured view of the learner that "
  "the model does not own; without one, recommendations become generic. The same concerns appear in "
  "educational applications of LLMs, where knowledge tracing and learner-performance modelling remain "
  "open problems [17], [18]."),
 ("p",
  "This paper reports on a rule-enhanced personalized agent for substation O&M training that is "
  "implemented as a working MVP. Its central design decision is to give the safety gate to a "
  "declarative, database-resident rule engine rather than to a prompt. The contribution is "
  "architectural rather than a new model:"),
 ("list", [
   "**A three-layer architecture** that separates rule configuration, rule computation and decision "
   "governance, with a contract-isolated switch between the rule path and the model path "
   "(source ∈ {rule, model}) so that the model can be replaced without touching controllers, DTOs or "
   "the frontend.",
   "**A declarative rule DSL** with a strict operator whitelist, group-scoped convergence "
   "(stop_on_match and max_hits act per group, not per scene) and *_from fact indirection that lets a "
   "single rule serve an entire family of gas types and grade bands.",
   "**Full-chain traceability**: one run identifier links rule hits, the emitted suggestion and the "
   "human decision; every conclusion is explainable down to a rule code and a data point, and the "
   "agent is advisory-only—high-risk suggestions always require human confirmation.",
   "**A replay-based rule-set audit methodology** with an open harness. Replaying the production rule "
   "set over 150 real employee profiles turns rule maintenance into a measurable activity and, in our "
   "case, exposed three classes of defect that would otherwise have remained invisible."]),
 ("p",
  "Section III describes the architecture and the DSL. Section IV documents the rule set, the fact "
  "adapter and the fine-tuning corpus. Section V presents the replay evaluation and the audit "
  "findings. Section VI discusses threats to validity. We deliberately report defects in our own rule "
  "set: they are the strongest evidence that a rule-enhanced agent must be accompanied by a rule audit "
  "harness."),

 ("h1", "II. Related Work"),
 ("h2", "A. LLM agents and personalisation in education"),
 ("p",
  "LLM agents combine reasoning with tool use [3], [4] and can be steered by self-consistency [20]. In "
  "education, knowledge tracing predicts learner state from interaction history [16], and recent work "
  "studies whether LLMs can model learner performance [17], trace knowledge in tutoring dialogues, or "
  "drive learning recommendation [19]. These systems optimise for learning outcome; they rarely treat "
  "regulatory or safety constraints as first-class runtime objects, which is the gap we address."),
 ("h2", "B. Hallucination, guardrails and constrained generation"),
 ("p",
  "Hallucination in LLMs is well documented [9], [22], and alignment methods reduce but do not "
  "eliminate it [5], [6]. Runtime guardrails such as NeMo Guardrails [8] place a programmable, "
  "model-independent layer between the user and the model and express rails in a dedicated language. "
  "Our rule layer has the same intent but differs in two ways that matter for an industrial setting: "
  "rails live in relational tables and are editable by an administrator without a deployment, and "
  "every evaluation is persisted together with an explanation and a human decision."),
 ("h2", "C. Rules in safety-critical industrial systems"),
 ("p",
  "Production rule systems have a long history, from the Rete match algorithm [14] to modern business "
  "rule engines. Their weakness is rule-base decay: conditions drift away from business thresholds, "
  "and dead rules accumulate. Our audit methodology is aimed exactly at this weakness, using the "
  "engine's own skip channel as the diagnostic signal."),

 ("h1", "III. Architecture"),
 ("h2", "A. Requirements and hard constraints"),
 ("p",
  "The deployment context imposes four constraints. (i) Roles have strict data scopes: an employee "
  "sees only personal data, a team lead sees the team, an executive sees company-wide aggregates, and "
  "the administrator configures and audits but takes no business decision. (ii) Mental-health and "
  "care data are personal by default. (iii) A failing safety result has the highest priority in any "
  "talent decision and triggers a veto. (iv) Only a MySQL instance is available—no external rule "
  "engine, no ORM, no additional store. The last constraint rules out Drools-style frameworks and "
  "leads to the JSON-column design below."),
 ("h2", "B. Three-layer separation"),
 ("p",
  "Fig. 1 shows the architecture. Facts for a scene are assembled by a per-scene adapter from the "
  "operational tables; the engine evaluates the enabled rules of that scene in descending priority and "
  "converges per group; the verdict is merged and, when a suggestion is emitted, persisted. Table 2 "
  "summarises the responsibility split. Two invariants are enforced by code: the engine writes only "
  "rule_result and never mutates business data, and need_human_confirm is always true for emitted "
  "suggestions."),
 ("fig", ("fig1_architecture.png",
          "Three-layer architecture. The rule layer owns the safety gate; the computation layer "
          "records what was computed and why; the decision layer records what a human decided.")),
 ("h2", "C. Declarative rule DSL"),
 ("p",
  "A rule is a row of the rule table: rule_code, scene, condition_json, action_json, priority, "
  "rule_group, enabled, stop_on_match and max_hits. condition_json is a pure data tree; no scripting "
  "engine, no SpEL and no SQL concatenation is involved, because rule content is treated as untrusted "
  "input. Table 3 lists the operator whitelist. Fields ending in _from are fact indirections: at "
  "output time the field name is replaced by the current value of the referenced fact, so one rule can "
  "serve every gas type and grade band instead of one rule per pair."),
 ("p",
  "Matching proceeds as follows. Rules with enabled = 1 and a matching scene are ordered by priority "
  "descending, then by rule_code ascending, which makes the outcome reproducible regardless of the "
  "physical row order. Conditions are evaluated one by one. A condition that cannot be decided—an "
  "unknown operator, a missing fact, a type mismatch—is recorded in the skip channel together with its "
  "reason and is not treated as a hit; a single undecidable rule never aborts the execution. "
  "Convergence is group-scoped: stop_on_match terminates only its own group, and max_hits caps only "
  "its own group, so a grade-band group and a keyword-supplement group can each reach a decision "
  "without one silencing the other. Un-grouped rules share the empty default group, which preserves "
  "the original highest-priority-wins semantics. Finally the verdict is merged: actions and causes are "
  "de-duplicated in encounter order, the primary cause is the first cause seen, and the severity is "
  "the most severe among hits,"),
 ("eq", 7),
 ("p",
  "with rank(低) < rank(中) < rank(高). If nothing fires, the engine returns matched = false together "
  "with an unmatched_reason instead of raising an error, which is what makes a replay analysis "
  "possible."),
 ("h2", "D. Guardrail, fallback and model switch"),
 ("p",
  "Model output is accepted only if it passes four checks: structural contract validity, "
  "fact consistency against the assembled facts, permission boundaries, and safety rules. Formally,"),
 ("eq", 5),
 ("p",
  "A rejected output triggers at most one bounded rewrite attempt; if that also fails, the system "
  "returns the rule-path result and writes a fallback_note explaining why. Because the response "
  "carries source ∈ {rule, model} and the three stable agent endpoints keep a fixed request and "
  "response shape, replacing the model is a Service-implementation change only—controllers, DTOs, "
  "paths and the frontend do not move. Fig. 2 shows the flow."),
 ("fig", ("fig2_guardrail.png",
          "Guardrail and fallback flow. Field completeness, fact consistency and safety compliance "
          "are checked in order; failure leads to a bounded rewrite, then to the rule path, and "
          "high-risk outputs always end in human confirmation.")),
 ("h2", "E. Personalisation model"),
 ("p",
  "For employee i and competence k, the job gap and the future-need gap are"),
 ("eq", 1),
 ("eq", 2),
 ("p",
  "where R is the level required by the position, D the level demanded by the company's forward "
  "capability plan, and S the demonstrated level. The reinforcement priority combines both gaps with "
  "examination, practical, certificate and safety terms,"),
 ("eq", 3),
 ("p",
  "and is mapped onto three priority bands"),
 ("eq", 4),
 ("p",
  "which the frontend renders as P1/P2/P3. The weights are configuration, not code, so a utility can "
  "favour certificate validity or safety exposure without a release."),

 ("h1", "IV. Rule Set, Fact Adapter and Corpus"),
 ("h2", "A. Rule inventory"),
 ("p",
  "Table 4 lists the 18 production rules across five scenes. The gas-attribution scene is the most "
  "developed: five rules in the VALUE group grade the reading against a configurable threshold ladder, "
  "and seven rules in the KEYWORD group supplement causes from the report text with a group cap of "
  "three. The ladder is driven by a single margin ratio,"),
 ("eq", 6),
 ("p",
  "where u is the measured value, u0 the alarm threshold and umax the instrument full scale. The "
  "grading rules compare ρ against configured bands and take their cause and actions from the "
  "per-gas configuration by fact indirection, which is why one rule serves every gas type. The rule "
  "catalogue is loaded at start-up and re-read from the database, so enabling or disabling a rule "
  "takes effect on the next execution."),
 ("h2", "B. Fact adapter"),
 ("p",
  "A scene has exactly one fact source. Adapters are deterministic and read only operational input; "
  "they never read a previous model conclusion, which is what makes two consecutive attributions of "
  "the same report produce identical rule references. Table 5 gives the adapter used in the replay."),
 ("h2", "C. Fine-tuning corpus and model configuration"),
 ("p",
  "The personalised diagnosis is supported by a 150-sample Alpaca-format corpus. Each sample carries "
  "one fixed instruction, a structured employee profile as input, and a target output that follows an "
  "11-key JSON contract (conclusion, evidence, root_cause, gaps, learning_path, roadmap, "
  "level_mapping, skill_dependencies, safety_boundary, quantitative_baseline, "
  "personalization_basis). The contract is shared by the frontend, the backend and the corpus, which "
  "is what allows the guardrail to validate a model response field by field. Table 6 lists the stack."),
 ("p",
  "We state the serving configuration explicitly and mark what is still pending: the base model is "
  "Qwen2.5-7B-Instruct [12] served through LLaMA-Factory [13] with 4-bit quantisation; the training "
  "hyper-parameters and the adapter checkpoint of the current run are being consolidated and are not "
  "reported here. The agent endpoints that would expose this model are still stubs returning fixed "
  "content, and the rule path is the live behaviour in production."),

 ("h1", "V. Replay Evaluation and Rule-Set Audit"),
 ("h2", "A. Protocol"),
 ("p",
  "We evaluate by replay rather than by a live trial. The 18 rules are extracted from the migration "
  "scripts, the 150 profiles are parsed into scene facts by the adapter of Table 5, and the documented "
  "DSL semantics are executed by a reference evaluator. 450 executions are produced, each twice for "
  "the determinism check. The same facts can be pushed to the live endpoint POST /api/v1/rules/execute "
  "to confirm that the reference evaluator and the Java engine agree; the harness and all raw results "
  "accompany this paper. This protocol has one property that a live trial cannot offer: it is exactly "
  "reproducible, including every skip reason."),
 ("h2", "B. Coverage (RQ1)"),
 ("p",
  "Table 7 shows coverage. Coverage is not a weakness of the engine; it is the measured size of the "
  "rule set's reach. Table 8 is the audit that matters. The examination rule tests score < 60, while "
  "the business pass lines in the corpus are 80 and 85, so 120 of 150 failing scores receive no "
  "remediation at all—a silent-miss rate of 80.0% (Eq. 8) with perfect precision, which is the most "
  "dangerous combination a guardrail can have. The competence rule additionally demands "
  "required_level = 3, which excludes 94 of the 120 profiles that have a real gap; and no rule at all "
  "consumes the future-need axis, although 120 profiles carry such a gap. Most seriously, no rule "
  "reads the safety facts, even though 125 profiles carry a safety-negative record and 75 of them are "
  "authorisation violations—the very cases that the requirements say must dominate any talent "
  "decision."),
 ("eq", 8),
 ("h2", "C. Determinism and latency (RQ2)"),
 ("p",
  "Table 9 confirms the engine contract. All 450 executions are byte-identical on a repeat run, and "
  "the verdict is unchanged when the physical order of rules is reversed, because ordering is "
  "canonical by priority and code. In-process evaluation is sub-millisecond; we stress that this "
  "excludes database access, fact assembly, model inference and network time."),
 ("h2", "D. Guardrail audit of reference outputs (RQ3)"),
 ("p",
  "Table 10 audits the 150 structured reference outputs against the same profiles. The corpus is "
  "internally very clean—contract, level arithmetic, priority order, deadline monotonicity, safety "
  "boundary and evidence grounding all pass at 100%—which is a property of the corpus construction "
  "rather than of a live model. Two results are informative. First, 2.7% of outputs contain at least "
  "one number that cannot be traced to the profile, which is exactly the class of defect that the "
  "unverified_numbers soft check is designed to expose and that compresses reported confidence. "
  "Second, gap levels agree with the profile-derived facts in only 74.7% of outputs. On inspection "
  "the disagreement is systematic rather than random: where a profile states a key-task authorisation "
  "threshold of L4, the outputs report a position requirement of L3 and a future requirement of L4. "
  "In other words, the corpus and the adapter resolve the same text into two different notions of "
  "'required level'. This is a specification ambiguity, not a modelling error, and it is precisely the "
  "kind of defect that a fixed fact adapter exists to prevent: if the model and the rule layer silently "
  "adopt different definitions, a quarter of otherwise plausible outputs would be rejected or rewritten "
  "for reasons no one can explain."),
 ("h2", "E. Group semantics (RQ4)"),
 ("p",
  "Table 11 reports the 200-case parameter grid for the gas scene. The implemented semantics are "
  "correct everywhere: the VALUE ladder fires exactly once per case, the KEYWORD group honours its cap "
  "of three, severity merging picks the most severe, and fact indirection resolves on every applicable "
  "case. Measured against the business intent written in the rule remarks, however, the ladder is "
  "correct in only 80% of cases, and the reason is a real defect: REPORT_GAS_WITHIN_NEAR tests only "
  "ratio ≤ 0.10 without a lower bound, so it also matches readings far below the threshold and, being "
  "higher in priority and stopping its group, makes the terminal rule REPORT_GAS_WITHIN unreachable "
  "for the entire grid. The practical consequence is a 100% false-escalation rate on the 40 "
  "comfortable readings in the grid—every comfortable reading is graded medium and scheduled for "
  "two-hourly re-testing. The defect is visible only because the grid compares implemented semantics "
  "against stated intent, which is the argument for keeping the audit in the loop."),
 ("h2", "F. Ablation (RQ5)"),
 ("p",
  "Table 12 contrasts an unguarded structured output with the rule layer. The two paths fail in "
  "opposite directions. The model path is expressive and safety-aware in its text but not guaranteed "
  "traceable; the rule path is deterministic and perfectly traceable but, on today's rule set, blind "
  "to both the pass line and the safety axis. Neither is sufficient alone, which is the empirical "
  "basis for the architecture."),
 ("h2", "G. Remediation"),
 ("p",
  "Three changes follow directly and are queued: make every threshold a configuration field instead "
  "of a literal in condition_json; add a safety-precedence rule group that consumes the safety facts "
  "and can veto any action; and add lower bounds to the VALUE ladder so that the terminal rule becomes "
  "reachable. Because the harness replays the same corpus, each fix can be re-audited in seconds."),

 ("h1", "VI. Discussion and Threats to Validity"),
 ("p",
  "**Construct validity.** The reference outputs are SFT targets, not live model responses; the "
  "unguarded baseline in Table 12 therefore measures the quality of the corpus, not of a model. The "
  "in-process latency excludes the database and the model. Both are stated where they apply."),
 ("p",
  "**Internal validity.** The fact adapter is part of our contribution, and the level-mismatch result "
  "depends on how 'required level' is defined. We therefore report the mismatch as a specification "
  "ambiguity with the systematic pattern that produces it, rather than as a model error, and we publish "
  "the adapter so the definition can be inspected."),
 ("p",
  "**External validity.** One utility, one domain, 150 profiles and 18 rules. The architectural "
  "invariants are domain-independent, but the coverage numbers are not and should not be quoted "
  "elsewhere."),
 ("p",
  "**Conclusion validity.** No human expert rating or field adoption data is available yet; "
  "consequently we make no claim about learning outcomes. The claim we do make is narrower and fully "
  "supported: the engine is deterministic and traceable, the audit finds real defects, and coverage "
  "must be shared between rules and model."),

 ("h1", "VII. Conclusion and Future Work"),
 ("p",
  "We presented a rule-enhanced personalized agent for substation O&M training, built around a "
  "declarative JSON rule engine with group-scoped convergence, fact indirection, a contract-isolated "
  "model switch and a full decision traceability chain. Its evaluation is a replay-based rule-set "
  "audit that is exactly reproducible, and it earned its keep: it found a hard-coded examination "
  "threshold that silently misses 80% of failing scores, a hard-coded level gate that misses 63% of "
  "real gaps, an unreachable terminal rule that escalates every comfortable gas reading, and a "
  "specification ambiguity that accounts for a quarter of level inconsistencies in the training "
  "corpus. Future work is threefold: connect the three agent endpoints to the engine and to the "
  "fine-tuned model under the fixed contract; extend the wired scenes to operations attribution and "
  "material checking; and run a controlled expert-rating and field-adoption study, for which the "
  "harness and the corpus released with this paper provide the baseline."),
]

# 图（用脚本生成）
FIGURES = {
 "fig1_architecture.png": None,
 "fig2_guardrail.png": None,
}
