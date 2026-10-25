import React, { useEffect, useState } from "react";
import { ResponsiveContainer, ComposedChart, LineChart, BarChart, Line, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";

const card = { background: "#fff", border: "1px solid #e3e8ef", borderRadius: 10, padding: 16 };
const fmt = (v) => (v == null ? "–" : Math.round(v).toLocaleString());
const Card = ({ title, children }) => <div style={card}><h3 style={{ margin: "0 0 8px", fontSize: 15 }}>{title}</h3>{children}</div>;
const Kpi = ({ label, value, hint }) => (
  <div style={card}><div style={{ fontSize: 12, color: "#64748b" }}>{label}</div>
    <div style={{ fontSize: 26, fontWeight: 700 }}>{value}</div><div style={{ fontSize: 12, color: "#64748b" }}>{hint}</div></div>
);

export default function App() {
  const [start, setStart] = useState("2026-01-01");
  const [end, setEnd] = useState("2026-01-31");
  const [cutoff, setCutoff] = useState(9);
  const [data, setData] = useState(null);
  const [hor, setHor] = useState([]);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true); setErr(null);
    fetch(`/api/compare?start=${start}&end=${end}&cutoff_hour=${cutoff}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText))).then(setData)
      .catch((e) => setErr(String(e))).finally(() => setLoading(false));
  }, [start, end, cutoff]);
  useEffect(() => { fetch("/api/horizon").then((r) => r.json()).then(setHor).catch(() => {}); }, []);

  const m = data?.metrics || {};
  const pts = (data?.points || []).map((p) => ({ ...p, t: p.t.slice(5, 16).replace("T", " ") }));
  return (
    <div style={{ fontFamily: "system-ui, sans-serif", background: "#f4f6fa", minHeight: "100vh", padding: 24 }}>
      <h1 style={{ margin: 0 }}>UK Wind Forecast Reliability</h1>
      <p style={{ color: "#475569", marginTop: 4 }}>Day-ahead purchasing, January 2026 · Elexon FUELHH (actual) vs WINDFOR (forecast) · national wind, MW</p>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "12px 0" }}>
        <label>From <input type="date" value={start} min="2026-01-01" max="2026-01-31" onChange={(e) => setStart(e.target.value)} /></label>
        <label>To <input type="date" value={end} min="2026-01-01" max="2026-01-31" onChange={(e) => setEnd(e.target.value)} /></label>
        <label>Decision time (D-1, UK) <select value={cutoff} onChange={(e) => setCutoff(+e.target.value)}>
          {[6, 7, 8, 9, 10, 11, 12].map((h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}</select></label>
        {loading && <span>Loading Elexon data (first load can take ~30s)…</span>}
        {err && <span style={{ color: "crimson" }}>Error: {err}</span>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
        <Kpi label="MAE (MW)" value={fmt(m.mae)} hint="average miss per hour" />
        <Kpi label="RMSE (MW)" value={fmt(m.rmse)} hint="penalises large misses" />
        <Kpi label="Bias (MW)" value={fmt(m.bias)} hint=">0 over-forecasts wind" />
        <Kpi label="wMAPE" value={m.wmape_pct == null ? "–" : m.wmape_pct.toFixed(1) + "%"} hint="error / total actual" />
        <Kpi label="90% error band (MW)" value={`${fmt(m.p5)} to ${fmt(m.p95)}`} hint="buffer to plan around forecast" />
      </div>
      <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
        <Card title="Forecast available at decision time vs actual wind (MW)">
          <ResponsiveContainer width="100%" height={320}><LineChart data={pts}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="t" minTickGap={60} fontSize={11} /><YAxis fontSize={11} />
            <Tooltip /><Legend />
            <Line dataKey="actual" stroke="#0f766e" dot={false} name="Actual" />
            <Line dataKey="forecast" stroke="#d97706" dot={false} name="Forecast (latest before cutoff)" /></LineChart></ResponsiveContainer>
        </Card>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(340px,1fr))", gap: 12 }}>
          <Card title="Error by hour of day (MW)"><ResponsiveContainer width="100%" height={240}><BarChart data={data?.by_hour || []}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="hour" fontSize={11} /><YAxis fontSize={11} /><Tooltip /><Legend />
            <Bar dataKey="mae" fill="#6366f1" name="MAE" /><Bar dataKey="bias" fill="#f43f5e" name="Bias" /></BarChart></ResponsiveContainer></Card>
          <Card title="Error vs forecast horizon (hours ahead)"><ResponsiveContainer width="100%" height={240}><ComposedChart data={hor}>
            <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="bucket" fontSize={11} unit="h" /><YAxis fontSize={11} /><Tooltip /><Legend />
            <Line dataKey="mae" stroke="#6366f1" name="MAE" /><Line dataKey="bias" stroke="#f43f5e" name="Bias" /></ComposedChart></ResponsiveContainer></Card>
        </div>
      </div>
      <p style={{ color: "#64748b", fontSize: 12 }}>Error = forecast − actual. Each target hour uses the latest forecast published before the chosen decision time on the previous day.</p>
    </div>
  );
}
