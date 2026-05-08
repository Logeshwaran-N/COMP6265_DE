import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Database, GitBranch, ShieldCheck, Search, Gauge, Receipt, Activity, Boxes, BrainCircuit, RefreshCcw } from "lucide-react";
import { api } from "./api";
import "./styles.css";

const pages = [
  ["dashboard", "Dashboard", Activity],
  ["query", "Query Console", Search],
  ["catalogue", "Data Catalogue", Boxes],
  ["trust", "Trust & Sources", Gauge],
  ["pricing", "Pricing Model", Receipt],
  ["audit", "Governance Audit", ShieldCheck],
  ["architecture", "Architecture", BrainCircuit],
];

function App() {
  const [page, setPage] = useState("dashboard");
  const [catalogue, setCatalogue] = useState({});
  const [sources, setSources] = useState([]);
  const [audit, setAudit] = useState([]);
  const [algorithm, setAlgorithm] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const [cat, src, aud, alg] = await Promise.all([api.catalogue(), api.sources(), api.audit(), api.algorithm()]);
      setCatalogue(cat); setSources(src); setAudit(aud); setAlgorithm(alg);
    } finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);

  const ctx = { catalogue, sources, audit, algorithm, refresh };
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Database size={22}/></div><div><b>Data Economy</b><span>Federated Trust Platform</span></div></div>
      <nav>{pages.map(([id, label, Icon]) => <button key={id} className={page===id?"active":""} onClick={()=>setPage(id)}><Icon size={18}/>{label}</button>)}</nav>
      <div className="sidebar-note"><GitBranch size={16}/> Backend: <b>{api.base}</b></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><h1>{pages.find(p=>p[0]===page)?.[1]}</h1><p>Policy-aware, trust-aware, cost-aware federated querying over CSV, SQLite and API sources.</p><small>Backend: {api.base}</small></div><button className="ghost" onClick={refresh}><RefreshCcw size={16}/> Refresh</button></header>
      {loading ? <div className="loader">Loading platform metadata…</div> : <Page page={page} ctx={ctx}/>} 
    </main>
  </div>;
}

function Page({page, ctx}) {
  if (page === "dashboard") return <Dashboard {...ctx}/>;
  if (page === "query") return <QueryConsole/>;
  if (page === "catalogue") return <Catalogue catalogue={ctx.catalogue}/>;
  if (page === "trust") return <Trust sources={ctx.sources}/>;
  if (page === "pricing") return <Pricing algorithm={ctx.algorithm}/>;
  if (page === "audit") return <Audit audit={ctx.audit}/>;
  return <Architecture algorithm={ctx.algorithm}/>;
}

function Dashboard({catalogue, sources, audit}) {
  const datasets = Object.keys(catalogue);
  const avgTrust = sources.length ? (sources.reduce((a,s)=>a+(s.computed_trust||0),0)/sources.length).toFixed(2) : "0";
  const last = audit[0];
  return <div className="grid two">
    <Metric title="Datasets" value={datasets.length} note="virtual schemas" />
    <Metric title="Sources" value={sources.length} note="CSV / SQLite / API" />
    <Metric title="Avg Trust" value={avgTrust} note="PageRank + authority + freshness" />
    <Metric title="Audit Events" value={audit.length} note="governance duty" />
    <section className="card wide hero-card"><h2>What this prototype demonstrates</h2><p>This is not a normal CRUD app. It models a data-economy component: a federated query gateway that estimates plans, enforces policy, prices query answers, checks source trust, detects conflicts and records an audit trail.</p><div className="flow"><span>Query</span><span>Policy</span><span>Optimiser</span><span>Sources</span><span>Conflict Resolver</span><span>Pricing</span><span>Audit</span></div></section>
    <section className="card"><h2>Latest audit</h2>{last ? <pre className="mini-pre">{JSON.stringify(last, null, 2)}</pre> : <p>No audit events yet. Run a query.</p>}</section>
  </div>;
}
function Metric({title,value,note}) { return <section className="metric"><span>{title}</span><b>{value}</b><small>{note}</small></section>; }

const examples = [
  "SELECT rate FROM fx_rates WHERE pair = 'GBP_INR' WITH VERIFICATION",
  "SELECT name, price_gbp FROM fruits WHERE name = 'apple' WITH VERIFICATION",
  "SELECT name, price_gbp, quality_grade FROM fruits WHERE price_gbp > 5",
  "SELECT customer_email FROM orders WHERE order_id = 'O-1002'",
  "SELECT supplier_id, supplier_name, rating FROM suppliers WHERE rating > 4",
  "SELECT name, price_gbp, supplier_name FROM fruits JOIN suppliers ON supplier_id = supplier_id WHERE name = 'apple'",
];
function QueryConsole({onAfterRun}) {
  const [payload, setPayload] = useState({query: examples[0], role:"researcher", purpose:"research", strategy:"balanced", verification:false, show_all_conflicts:true});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      const res = await api.runQuery(payload);
      // Keep the result visible on this page. Do not trigger global refresh here,
      // because global loading unmounts QueryConsole and clears local state.
      setResult(res);
    } catch(e){
      setResult({ok:false,message:e.message});
    } finally { setBusy(false); }
  };
  return <div className="grid query-grid">
    <section className="card query-card"><h2>Federated query console</h2><label>Example queries</label><select onChange={e=>setPayload({...payload,query:e.target.value})} value={payload.query}>{examples.map(x=><option key={x}>{x}</option>)}</select><label>SQL-like query</label><textarea value={payload.query} onChange={e=>setPayload({...payload,query:e.target.value})}/><div className="form-row"><Field label="Role"><select value={payload.role} onChange={e=>setPayload({...payload,role:e.target.value})}>{["guest","analyst","researcher","data_steward","admin"].map(x=><option key={x}>{x}</option>)}</select></Field><Field label="Purpose"><select value={payload.purpose} onChange={e=>setPayload({...payload,purpose:e.target.value})}>{["research","planning","commercial","internal_audit"].map(x=><option key={x}>{x}</option>)}</select></Field><Field label="Strategy"><select value={payload.strategy} onChange={e=>setPayload({...payload,strategy:e.target.value})}>{["balanced","cheapest","trust_first","privacy_first"].map(x=><option key={x}>{x}</option>)}</select></Field></div><label className="check"><input type="checkbox" checked={payload.verification} onChange={e=>setPayload({...payload,verification:e.target.checked})}/> Force verified multi-source plan</label><button className="primary" onClick={run} disabled={busy}>{busy?"Running…":"Run Query"}</button></section>
    <section className="card result-card"><h2>Result</h2>{result ? <ResultView result={result}/> : <p className="muted">Run a query to see policy decision, optimiser plan, pricing, conflicts and result rows.</p>}</section>
  </div>;
}
function Field({label,children}) {return <div className="field"><label>{label}</label>{children}</div>}
function ResultView({result}) {
  return <div className="result"><div className={result.ok?"status ok":"status deny"}>{result.ok?"Allowed & Executed":"Denied / Error"}: {result.message}</div>{result.policy_decision && <Details title="Policy decision" data={result.policy_decision}/>} {result.selected_plan?.plan_id && <Plan plan={result.selected_plan}/>} {result.pricing?.total_user_price != null && <PricingBox pricing={result.pricing}/>} {result.conflicts?.length>0 && <ConflictList conflicts={result.conflicts}/>} {result.ok && result.result_rows?.length === 0 && <p className="muted">Query executed, but no rows matched the filter.</p>} {result.result_rows?.length>0 && <Table rows={result.result_rows}/>} {result.candidate_plans?.length>0 && <Details title="Candidate plans compared" data={result.candidate_plans}/>}</div>;
}
function Plan({plan}) {return <div className="plan"><h3>Selected plan: {plan.plan_id}</h3><div className="pill-row"><span>mode: {plan.mode}</span><span>score: {plan.optimiser_score}</span><span>trust: {plan.mean_trust}</span><span>cost: {plan.estimated_execution_cost}</span><span>latency: {plan.estimated_latency_ms}ms</span></div><p>{plan.explanation}</p><small>{plan.complexity_class}</small></div>}
function PricingBox({pricing}) {return <div className="pricing-box"><b>{pricing.total_user_price} {pricing.currency}</b><span>User-facing query price</span><p>{pricing.pricing_note}</p><p>{pricing.arbitrage_note}</p></div>}
function ConflictList({conflicts}) {return <div><h3>Conflicts detected</h3>{conflicts.map((c,i)=><div className="conflict" key={i}><b>{c.entity_value}.{c.column}</b><span>Chosen {String(c.chosen_value)} from {c.chosen_source}</span><small>{c.reason}</small>{c.alternatives?.length>0 && <ul>{c.alternatives.map((a,j)=><li key={j}>{a.source}: {String(a.value)} (score {a.source_score})</li>)}</ul>}</div>)}</div>}
function Table({rows}) {const cols = Object.keys(rows[0]||{}); return <div className="table-wrap"><table><thead><tr>{cols.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{cols.map(c=><td key={c}>{String(r[c])}</td>)}</tr>)}</tbody></table></div>}
function Details({title,data}) {return <details><summary>{title}</summary><pre>{JSON.stringify(data,null,2)}</pre></details>}

function Catalogue({catalogue}) {return <div className="grid two">{Object.entries(catalogue).map(([name,d])=><section className="card" key={name}><div className="card-title"><h2>{name}</h2><span>{d.domain}</span></div><p>{d.description}</p><h3>Columns</h3><div className="chips">{Object.entries(d.columns).map(([c,m])=><span key={c} className={m.pii?"chip warn":"chip"}>{c}{m.pii?" PII":""}</span>)}</div><h3>Sources</h3>{Object.entries(d.sources).map(([s,src])=><div className="source-line" key={s}><b>{s}</b><span>{src.type}</span><span>trust {src.trust?.computed_trust}</span><span>fresh {src.freshness_days}d</span></div>)}</section>)}</div>}
function Trust({sources}) {return <section className="card"><h2>Source trust and reputation</h2><p>Trust is not a hard-coded label only. It combines base trust, authority, provider PageRank and freshness.</p><Table rows={sources.map(s=>({source:s.source_name,dataset:s.dataset,type:s.source_type,provider:s.provider,base:s.base_trust,authority:s.authority_level,pagerank:s.pagerank_reputation,freshness:s.freshness_score,computed:s.computed_trust,conflict_risk:s.conflict_risk}))}/></section>}
function Pricing({algorithm}) {return <div className="grid two"><section className="card"><h2>Pricing model</h2><p>The platform separates internal execution cost from user-facing data price.</p><ul><li>Internal cost: rows scanned, source access cost, API calls and latency.</li><li>User price: base fee, selected column value, source premium, verification and conflict-resolution fees.</li><li>Arbitrage guard: selected columns cannot be priced higher than a published view that determines them.</li></ul></section><section className="card"><h2>Algorithm details</h2><pre>{JSON.stringify(algorithm?.pricing_model || {}, null, 2)}</pre></section></div>}
function Audit({audit}) {return <section className="card"><h2>Governance audit log</h2><p>Audit logging is implemented as a policy duty. Denied and allowed requests are recorded.</p>{audit.length ? <Table rows={audit.map(a=>({time:a.timestamp,audit_id:a.audit_id,role:a.role,purpose:a.purpose,allowed:a.allowed,query:a.raw_query,price:a.price ?? "-",conflicts:a.conflict_count ?? "-"}))}/> : <p>No events yet.</p>}</section>}
function Architecture({algorithm}) {return <div className="grid two"><section className="card wide"><h2>Architecture pipeline</h2><div className="big-flow">{(algorithm?.pipeline||[]).map((x,i)=><div key={x}><b>{i+1}</b><span>{x}</span></div>)}</div></section><section className="card"><h2>Cost model</h2><pre>{JSON.stringify(algorithm?.cost_model || {}, null, 2)}</pre></section><section className="card"><h2>Complexities</h2><pre>{JSON.stringify(algorithm?.complexities || {}, null, 2)}</pre></section></div>}

createRoot(document.getElementById("root")).render(<App/>);
