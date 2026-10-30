# ReleaseProof v0 interface contract

Python 3.12; FastAPI server serving buildless web/index.html, styles.css, app.js. Container-compatible single process with SQLite persistence. No Node production dependency. Frontend uses relative /api URLs. All JSON responses are UTF-8. Root owns HTTP and persistence; runtime owns pure/application engine with serializable state.

## Engine interface

`new_state(session_id: str) -> dict`
`perform(state: dict, action: str, payload: dict, *, live_enabled: bool=False) -> dict`

perform returns updated state and must never trust client-provided pass verdicts, metrics, approval IDs, fingerprint values, or budget balances. Root serializes actions per session, stores state, and exposes failures as JSON. Long actions run in background executor; frontend polls snapshot. Provider credentials from environment only. Engine may expose progress callback later; final state is required first.

Root HTTP routes:
- GET /api/health -> {status, live_available, provider, versions, storage_bytes}
- GET /api/catalog -> {models: [{id,label,input_per_million,output_per_million}], workflows:[{id,label}], scenarios:[{id,label}]}
- POST /api/sessions -> state (session_id contains secure random capability; isolated per browser, no account needed)
- GET /api/sessions/{session_id} -> state + busy + last_error
- POST /api/sessions/{session_id}/actions -> {action, payload}; returns 202 {accepted:true}; GET polls completion. Unknown/invalid action -> 400, busy -> 409.
- GET /api/sessions/{session_id}/export -> downloadable qualification/evidence packet JSON; never secrets.

Actions: qualify, mutate, promote, execute, canary, mitigate, configure_budget, reset.

Payloads:
- qualify: {mode:'fixture'|'live', model_id?:str, repetitions?:1..3, suite:'quick'|'full'}
- mutate: {change:'prompt'|'policy'|'tools'}
- promote: {} (explicit user action; bound to server current candidate only)
- execute: {issue_id?:str, mode:'fixture'|'live'}
- canary: {scenario:'stable'|'injected_drift'} (clearly labelled local controlled experiment until live observation support implemented)
- mitigate: {strategy:'hold'|'fallback'|'requalify'}
- configure_budget: {limit_usd:0..1, reserve_percent:10..50, strategy:'balanced'|'economy'|'quality'}
- reset: {}

State required top-level keys:
```
{
 session_id, name:'ReleaseProof', revision:1,
 mode:'fixture', status:'unqualified',
 candidate:{model_id,label,prompt_version,tool_version,policy_version,fingerprint},
 active:null|{model_id,label,fingerprint,approved_at},
 qualification:null|{id,mode,status,passed,total,accuracy,latency_ms,tokens,cost_usd,created_at,fingerprint,cases:[]},
 budget:{limit_usd,spent_usd,reserved_usd,remaining_usd,reserve_percent,strategy,blocked_calls,decisions:[]},
 governance:{status,reasons:[],approval_valid:false,checks:[],blocked_actions:0},
 drift:{status:'unknown',p_value:null,observations:0,mode:'not_run',mitigation:'none',details:[]},
 evidence:{fingerprint,versions:[],changed:[],snapshot_bytes:0,seal:null},
 board:[{id,title,body,labels:[],route:null,draft:null,status:'open'}],
 events:[{id,time,kind,title,detail,status,source}],
 metrics:{live_calls:0,fixture_calls:0,replayed_calls:0,blocked_calls:0},
 busy:false,last_error:null
}
```

Additional keys allowed. API should remain stable while functionality improves. Case shape: {id,title,expected,actual,passed,latency_ms,input_tokens,output_tokens,cost_usd,source,error,tool_calls:[]}. Event sources: live, fixture, replay, fault_injection, system. Budget costs in fixture mode explicitly simulated; live provider cost is estimated from observed tokens and displayed pricing. No authoritative USD bill claims.

## Data contract

data/issues.json: list of {id,title,body,expected:{label,route},risk:'low'|'high',split:'qualification'|'holdout'}.
Allowed labels: bug, feature, question, security. Allowed routes: engineering, product, support, security. Include ambiguous and adversarial content, clear enough gold criteria and documented limitations. No live private user issues.
Agent schema: {label,route,draft,needs_review:boolean}. Tool operations: read_issue, read_policy, label_issue, route_issue, draft_response (draft only). Security issues must route security and need human review. Deterministic schema/policy checks judge outcomes.

UI: crisp polished developer tool; navy/ink and warm-white panels with green/amber accents, strong readable typography, compact sidebar, prominent release decision, configuration comparison, spend/reserve indicator, inspectable traces, evidence versions, triage board. Clear labelled source modes always. Main actions functional. Defaults show unqualified state with a clear Run qualification CTA; a guided synthetic demonstration is acceptable if labelled. No invented measured results on initial load.
