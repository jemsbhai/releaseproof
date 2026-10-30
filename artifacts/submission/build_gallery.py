"""Author original submission diagrams and layouts around unmodified CUA captures.

Render the resulting HTML with the browser's screenshot API at 1800 x 1200.
No screenshots, measurements, or application state are synthesized here.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
CSS = r'''
*{box-sizing:border-box}html,body{margin:0;width:1800px;height:1200px;overflow:hidden}
body{font-family:'Segoe UI',Arial,sans-serif;color:#142b36;background:#f5f5ed;-webkit-font-smoothing:antialiased}
.page{width:1800px;height:1200px;padding:66px 82px;position:relative}
.brand{display:flex;align-items:center;gap:16px;font-size:29px;font-weight:650;letter-spacing:-1px}
.brand svg{width:40px;height:40px}.top{display:flex;justify-content:space-between;align-items:center}
.eyebrow{font-size:20px;letter-spacing:3px;text-transform:uppercase;font-weight:650;color:#587064}
.tag{font-size:18px;letter-spacing:1px;border:1px solid #b9c8ba;padding:10px 18px;border-radius:40px;color:#496150}
h1{font-size:76px;line-height:1.04;letter-spacing:-3.6px;font-weight:650;margin:54px 0 20px;max-width:1500px}
.lede{font-size:29px;line-height:1.45;color:#51656a;max-width:1500px;margin:0}
.footer{position:absolute;bottom:37px;left:82px;right:82px;border-top:1px solid #d1dacf;padding-top:20px;display:flex;justify-content:space-between;font-size:18px;color:#61746e}
.pill{display:inline-block;border-radius:40px;background:#deebce;color:#2d563e;padding:10px 19px;font-size:19px;font-weight:650;margin-right:9px}
.caption{font-size:22px;line-height:1.4;color:#52635f}
.screen{display:block;width:100%;border:1px solid #d2d9ce;border-radius:14px;box-shadow:0 18px 52px #1c362410}
.shot{margin-top:34px;display:grid;grid-template-columns:1250px 1fr;gap:38px;align-items:start}
.shot img{width:1250px;max-height:730px;object-fit:contain;object-position:top}
.notes{padding-top:2px}.note{border-top:2px solid #cedbc4;padding:22px 0 25px}.note b{font-size:27px;line-height:1.2;display:block;margin-bottom:12px}.note p{font-size:23px;line-height:1.45;margin:0;color:#536760}
.dark{background:#122834;color:#f3f5eb}.dark .eyebrow,.dark .lede,.dark .caption{color:#b8c9bb}.dark .tag{color:#d7e8c8;border-color:#506758}.dark .footer{color:#a5bbae;border-color:#40574e}
.dark h1{font-size:109px;line-height:.98;letter-spacing:-5px;margin-top:40px}
.cover-grid{display:grid;grid-template-columns:1160px 1fr;gap:42px;margin-top:36px}.cover-grid img{width:1160px;border:1px solid #59705e;border-radius:12px}.cover-side{display:flex;flex-direction:column;justify-content:center;gap:23px}.cover-side .num{font-size:59px;color:#d4e7b4;letter-spacing:-2px;font-weight:650}.cover-side p{font-size:24px;line-height:1.3;color:#c5d1c4;margin:3px 0}.cover-side small{font-size:18px;color:#a4b8ac}
.flow{display:grid;grid-template-columns:320px 55px 590px 55px 616px;align-items:stretch;margin-top:36px;gap:0}.flow .node{height:380px;padding:24px}.flow .node h2{font-size:34px}.flow .node p{font-size:22px}
.node{border:1px solid #cad6c3;background:#fffef8;border-radius:18px;padding:28px;min-height:330px}.node.dark{background:#15352d;color:#f3f6ec;border-color:#15352d}.node h2{font-size:37px;letter-spacing:-1px;margin:13px 0 18px}.node p{font-size:23px;line-height:1.45;margin:0;color:#607166}.node.dark p{color:#cedccf}.arrow{display:flex;align-items:center;justify-content:center;font-size:38px;color:#5c7859}.micro{font-size:17px;letter-spacing:2px;font-weight:700;text-transform:uppercase;color:#69885d}.node.dark .micro{color:#bed599}.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}.chip{font-size:19px;padding:8px 12px;border-radius:7px;background:#e9efdf;color:#405d42}.node.dark .chip{background:#345043;color:#e0edd1}
.lane{margin-top:26px;background:#e5edda;padding:24px 32px;border-radius:14px;font-size:25px;display:flex;justify-content:space-between;align-items:center}.lane b{font-size:27px}.foundations{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:30px}.foundation{border-top:3px solid #7f9c71;padding-top:18px}.foundation strong{font-size:30px}.foundation p{font-size:23px;line-height:1.4;color:#52675b;margin-top:9px}
.results-grid{display:grid;grid-template-columns:1000px 1fr;gap:34px;margin-top:36px}.panel{background:#fffef8;border:1px solid #cbd6c5;border-radius:17px;padding:30px}.panel h2{font-size:31px;letter-spacing:-1px;margin:0 0 10px}.panel .sub{font-size:21px;color:#687965;margin:0 0 32px}.result{margin:26px 0}.rowlabel{display:flex;justify-content:space-between;font-size:25px;margin-bottom:13px}.rowlabel strong{font-weight:650}.blocks{display:flex;gap:7px}.block{width:48px;height:42px;border-radius:5px;background:#d7e6ba}.block.fail{background:#b46047}.status{font-size:19px;color:#9b4b35;margin-left:18px;font-weight:700}.legend{display:flex;gap:27px;font-size:20px;color:#6a7663;margin-top:29px}.legend span:before{content:'';display:inline-block;width:16px;height:16px;background:#d7e6ba;margin-right:10px;border-radius:3px}.legend span:last-child:before{background:#b46047}.statbig{font-size:105px;letter-spacing:-5px;color:#29583b;line-height:1.1;font-weight:650;margin:15px 0}.panel.alt{background:#e5eed9}.panel.alt p{font-size:24px;line-height:1.45;color:#4d654b}.callout{background:#e8eddf;border-left:4px solid #789260;padding:19px 24px;font-size:22px;line-height:1.4;margin-top:28px}.trace{margin-top:35px;display:flex;gap:20px;align-items:center}.trace>div{flex:1;padding:25px;border-radius:12px;border:1px solid #d0dbca;background:#fffef8}.trace b{font-size:26px}.trace p{font-size:22px;color:#5c6f5f;line-height:1.4;margin:8px 0 0}.trace .stop{background:#f0e2d9;border-color:#d4ae9b}.trace .stop b{color:#8c4a35}
'''
ICON='<svg viewBox="0 0 40 40" fill="none"><path d="M7 8H24L34 20L24 32H7V8Z" stroke="currentColor" stroke-width="3"/><path d="M13 20L18 25L27 15" stroke="currentColor" stroke-width="3"/></svg>'

def page(slug,title,body,index,theme=''):
    html=f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{title}</title><style>{CSS}</style><body><main class="page {theme}"><div class="top"><div class="brand">{ICON}ReleaseProof</div><span class="tag">NEBIUS × NVIDIA · OCT 2026</span></div>{body}<div class="footer"><span>Agent release workbench · Actual dependencies. Inspectable decisions.</span><span>{index:02d} / 08</span></div></main></body></html>'
    (ROOT/f'{slug}.html').write_text(html,encoding='utf-8')

page('01-cover','ReleaseProof — Proof before permission', '''
<h1>Proof before permission.</h1><p class="lede">A release workbench for developers putting AI agents in charge of tools.</p>
<div style="margin-top:26px"><span class="pill">Qualify the candidate</span><span class="pill">Approve the exact contract</span><span class="pill">Revalidate every action</span></div>
<div class="cover-grid"><div><img src="screens/qualification.jpg" alt="Unmodified recorded live qualification screenshot"><p class="caption" style="font-size:19px;margin-top:13px">Actual captured application · Super + prompt v2 + distinct review-all policy · Recorded live calls</p></div><div class="cover-side"><div><div class="num">202</div><p>actual NVIDIA model calls<br>on Nebius Token Factory</p><small>145 local evaluation + 57 browser demo</small></div><div><div class="num">3 controls</div><p>Spending limits.<br>Evidence-bound approvals.<br>Behavioral drift holds.</p></div><div><div class="num">0</div><p>real customer messages sent</p><small>Isolated demo board; drafts require review</small></div></div></div>
''',1,'dark')

page('02-architecture','One release, three connected controls','''
<h1>One release. Three connected controls.</h1><p class="lede">The server owns the decision to spend, approve, and act.</p>
<div class="flow"><div class="node"><span class="micro">01 / Input</span><h2>Synthetic<br>support issues</h2><p>Eight qualification cases.<br>Four held-out board issues.</p><div class="chips"><span class="chip">Normal</span><span class="chip">Adversarial</span></div></div><div class="arrow">→</div><div class="node dark"><span class="micro">02 / ReleaseProof server</span><h2>Qualify → approve → revalidate</h2><p>Approval binds the exact tested contract and evidence. A changed or held release cannot write to the board.</p><div class="chips"><span class="chip">Model</span><span class="chip">Prompt</span><span class="chip">Tools</span><span class="chip">Policy</span><span class="chip">Evidence</span></div></div><div class="arrow">→</div><div class="node"><span class="micro">03 / Hosted inference + bounded action</span><h2>NVIDIA Nemotron<br>on Nebius Token Factory</h2><p>Structured triage decisions become labels, routes, and reviewable drafts on an isolated demo board.</p><div class="chips"><span class="chip">No GPU required</span><span class="chip">Draft only</span></div></div></div>
<div class="lane"><b>Every model call</b><span>Reserve worst-case cost</span><span>→</span><span>Dispatch if allowed</span><span>→</span><span>Reconcile observed usage</span></div>
<div class="foundations"><div class="foundation"><strong>Pollard 1.6.2</strong><p>Execution policy and metering.<br>Current approval is checked before board writes.</p></div><div class="foundation"><strong>Hashrope 0.2.2</strong><p>Versioned content and evidence.<br>SHA-256 contract and evidence fingerprints bind approval.</p></div><div class="foundation"><strong>Epicormic 0.2.0</strong><p>Repeated behavioral comparisons.<br>A hold governs future actions; fallback needs fresh proof.</p></div></div>
<p class="caption" style="margin-top:18px">Shared Firestore spending authority · SQLite session state · FastAPI + buildless JavaScript · Free CPU hosting</p>
''',2)

page('03-measured-results','The gate rejected plausible but noncompliant outputs','''
<h1>The gate said “not yet.”</h1><p class="lede">Real model calls exposed policy failures. Failed candidates stayed blocked.</p>
<div class="results-grid"><section class="panel"><h2>Original selective-review policy · prompt v2</h2><p class="sub">Local evaluation · eight synthetic cases × two repetitions · 16/16 required</p>'''+''.join(f'<div class="result"><div class="rowlabel"><strong>{name}</strong><span><b>{score}/16</b><span class="status">BLOCKED</span></span></div><div class="blocks">'+''.join(f'<i class="block {"fail" if i>=score else ""}"></i>' for i in range(16))+'</div></div>' for name,score in [('Nemotron 3.5 Lightning',13),('Nemotron 3 Super',14),('Nemotron 3 Ultra · diagnostic',13)])+'''
<div class="legend"><span>Passed check</span><span>Failed check</span></div><p class="caption" style="margin-top:25px">Failures included invalid routing and review-policy violations. Pilots and earlier prompt-v1 failures remain in the evidence.</p></section><section class="panel alt"><span class="micro">A different, more supervised contract</span><h2 style="margin-top:18px">Require human review<br>for every draft</h2><div class="statbig">16/16</div><p><b>Super + prompt v2 + policy v2</b><br>Label and route checks unchanged. Expected review flag becomes true for every case.</p><p>Approval permitted one held-out draft. A later fresh replication also passed 16/16.</p><div class="callout">This changes the workflow. It is not an improved score on the original policy or a model ranking.</div></section></div>
<p class="caption" style="margin-top:26px">Small public development panel, not a general benchmark. Free-text factuality is outside these checks; unsupported claims occurred.</p>
''',3)

def shot(slug,title,lede,file,notes,index,label):
    n=''.join(f'<div class="note"><b>{a}</b><p>{b}</p></div>' for a,b in notes)
    page(slug,title,f'<h1>{title}</h1><p class="lede">{lede}</p><div class="shot"><div><img class="screen" src="screens/{file}" alt="Unmodified captured application screenshot"><p class="caption" style="font-size:20px;margin:15px 0">{label}</p></div><aside class="notes">{n}</aside></div>',index)

shot('04-qualification','Inspect the evidence. Then approve.','Full-suite qualification makes every observed failure and contract visible.','qualification.jpg',[
('Recorded live run','The public-browser run used NVIDIA Super on Nebius Token Factory and a policy requiring review for every draft.'),
('16/16 is scoped','Eight synthetic cases, two repetitions. Passing makes this exact workflow eligible for explicit approval.'),
('Compare contracts','The adjacent Lightning run uses a different policy. The UI retains both results and fingerprints.')],4,'RECORDED LIVE CALLS · Public-browser demonstration · Prompt v2, tools v1, review-all policy v2')

shot('05-reviewed-draft','An approved release earns one action.','A fresh held-out issue becomes a routed draft on the isolated demo board.','board.jpg',[
('Actual model output','A live Super call labelled the issue “bug” and routed it to engineering.'),
('Human review required','The draft is marked Needs review. No reply is sent to a customer or issue tracker.'),
('Checks stay on','The server revalidates the current approval before each consequential board operation.')],5,'RECORDED LIVE CALL · Synthetic held-out issue · Draft stored, not sent')

shot('06-stale-approval','Change the contract. Lose permission.','Changing the tools invalidated approval; the next board action was refused.','refusal.jpg',[
('Server-enforced refusal','Pollard denied the prospective write after the exact release contract changed.'),
('No new model call','The stale candidate was refused before another provider dispatch. The board remained unchanged.'),
('Completed work remains','The earlier draft stays in the record. Requalification and explicit approval are required to act again.')],6,'RECORDED SYSTEM REFUSAL · Declared tool-contract edit · Not a claim of silent provider drift')

shot('07-budget','Reserve first. Reconcile after.','A shared spending authority covers local and hosted inference.','budget.jpg',[
('Before dispatch','Reserve a conservative input bound plus capped output. Refuse work that cannot fit.'),
('After the response','Reconcile provider-reported tokens against the reservation and visible model pricing.'),
('Protect recovery','Session budgets preserve validation/recovery capacity; the global ledger survives restarts.')],7,'RECORDED LIVE BUDGET EVIDENCE · Token costs are estimates, not invoices · No new calls for these visuals')

shot('08-drift','Notice change. Hold what comes next.','A controlled fixture experiment makes drift mitigation visible and reproducible.','drift.jpg',[
('Explicitly synthetic','An injected behavior shift produced 80 observations and p = 0.001 using real Epicormic statistics.'),
('Future actions held','The release loses permission to act. Fallback still requires qualification and approval.'),
('Separate live probe','16 fresh versus 16 baseline observations found no detected change (p = 1). Small panels have low power.')],8,'CONTROLLED SYNTHETIC DRIFT · Real statistical calculation · Not provider drift, correctness, or causation')

manifest={'size':[1800,1200],'format':'JPEG','method':'Original HTML/CSS diagrams and typography; unmodified genuine CUA screenshots embedded with contain scaling. No fabricated UI or model outputs.','screenshots_source':'../video/raw/current/manifest.json','images':[p.stem+'.jpg' for p in sorted(ROOT.glob('0*.html'))]}
(ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Authored',len(manifest['images']),'gallery pages')
