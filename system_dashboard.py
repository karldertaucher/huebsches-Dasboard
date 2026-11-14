#!/usr/bin/env python3
"""
Vibe System Dashboard – Live-Systemmonitor für deinen Computer.

Start:
    pip install psutil
    python system_dashboard.py

Dann im Browser öffnen:  http://localhost:8765
(Beendet mit Strg+C im Terminal.)
"""
import json
import platform
import shutil
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psutil
except ImportError:
    print("Bitte zuerst installieren:  pip install psutil")
    raise SystemExit(1)

HOST, PORT = "127.0.0.1", 8765

_latest = {}


def collect():
    vm = psutil.virtual_memory()
    sm = psutil.swap_memory()
    du = shutil.disk_usage("/")
    try:
        du_win = shutil.disk_usage("C:\\") if platform.system() == "Windows" else None
    except Exception:
        du_win = None
    temps = {}
    try:
        for name, entries in (psutil.sensors_temperatures() or {}).items():
            if entries:
                temps[name] = round(entries[0].current, 1)
    except Exception:
        pass
    battery = None
    try:
        b = psutil.sensors_battery()
        if b:
            battery = {"percent": round(b.percent, 0), "plugged": bool(b.power_plugged)}
    except Exception:
        pass
    net = psutil.net_io_counters()
    return {
        "ts": time.time(),
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "cpu": {
            "name": platform.processor() or platform.machine(),
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "percent": psutil.cpu_percent(interval=0.4),
            "freq_mhz": round(psutil.cpu_freq().current) if psutil.cpu_freq() else None,
            "temp": temps,
        },
        "memory": {
            "total_gb": round(vm.total / 1e9, 1),
            "used_gb": round(vm.used / 1e9, 1),
            "percent": vm.percent,
            "swap_percent": sm.percent,
        },
        "disk": {
            "total_gb": round(du.total / 1e9, 1),
            "used_gb": round(du.used / 1e9, 1),
            "percent": round(100 * du.used / du.total, 1),
            "windows_c_percent": round(100 * du_win.used / du_win.total, 1) if du_win else None,
        },
        "net": {"sent_mb": round(net.bytes_sent / 1e6, 1), "recv_mb": round(net.bytes_recv / 1e6, 1)},
        "battery": battery,
    }


def poll_loop():
    while True:
        global _latest
        try:
            _latest = collect()
        except Exception as e:
            print("Fehler beim Sammeln:", e)
        time.sleep(2)


HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vibe · System Dashboard</title>
<style>
  :root {
    --bg:#0b0e14; --panel:rgba(255,255,255,.04); --border:rgba(255,255,255,.08);
    --text:#e8ecf4; --dim:#8b93a7; --accent:#7c6cff; --accent2:#2fd4c4;
    --good:#3ddc84; --warn:#ffb454; --bad:#ff5f7e;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:"Segoe UI",system-ui,sans-serif;color:var(--text);min-height:100vh;
    background:radial-gradient(1200px 600px at 80% -10%,rgba(124,108,255,.18),transparent 60%),
               radial-gradient(900px 500px at -10% 110%,rgba(47,212,196,.12),transparent 60%),var(--bg);
    padding:32px clamp(16px,4vw,48px)}
  header{display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:24px}
  h1{font-size:22px;letter-spacing:-.02em}
  .sub{color:var(--dim);font-size:13px;margin-top:2px}
  .pill{display:inline-flex;align-items:center;gap:8px;background:var(--panel);border:1px solid var(--border);
    padding:8px 16px;border-radius:999px;font-size:13px;color:var(--dim)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 10px var(--good);animation:p 2s infinite}
  @keyframes p{50%{opacity:.4}}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px;margin-bottom:20px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:18px;padding:20px;backdrop-filter:blur(12px);
    transition:transform .2s,border-color .2s}
  .card:hover{transform:translateY(-3px);border-color:rgba(124,108,255,.4)}
  .label{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--dim)}
  .value{font-size:32px;font-weight:700;margin:8px 0 10px;font-variant-numeric:tabular-nums}
  .track{height:10px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden}
  .fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--accent2));
    transition:width .6s cubic-bezier(.22,1,.36,1)}
  .fill.warn{background:linear-gradient(90deg,#ff8f5c,#ffb454)}
  .fill.bad{background:linear-gradient(90deg,#ff5f7e,#ff8fae)}
  .meta{font-size:12px;color:var(--dim);margin-top:10px}
  .grid{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:20px}
  @media(max-width:900px){.grid{grid-template-columns:1fr}}
  .card h2{font-size:15px;font-weight:600;margin-bottom:14px}
  #chart{width:100%}
  .info{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
  .info div{background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:12px;padding:14px;font-size:13px}
  .info b{display:block;color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px;font-weight:500}
  footer{color:var(--dim);font-size:12px;text-align:center;margin-top:8px}
</style>
</head>
<body>
<header>
  <div>
    <h1>Vibe · System Dashboard</h1>
    <div class="sub" id="host">–</div>
  </div>
  <div class="pill"><span class="dot"></span> Live · aktualisiert alle 2 s</div>
</header>

<section class="kpis">
  <div class="card"><div class="label">CPU-Auslastung</div><div class="value" id="v-cpu">–</div>
    <div class="track"><div class="fill" id="b-cpu"></div></div><div class="meta" id="m-cpu">–</div></div>
  <div class="card"><div class="label">Arbeitsspeicher</div><div class="value" id="v-ram">–</div>
    <div class="track"><div class="fill" id="b-ram"></div></div><div class="meta" id="m-ram">–</div></div>
  <div class="card"><div class="label">Festplatte</div><div class="value" id="v-disk">–</div>
    <div class="track"><div class="fill" id="b-disk"></div></div><div class="meta" id="m-disk">–</div></div>
  <div class="card"><div class="label">CPU-Temperatur</div><div class="value" id="v-temp">–</div>
    <div class="track"><div class="fill" id="b-temp"></div></div><div class="meta" id="m-temp">–</div></div>
</section>

<section class="grid">
  <div class="card"><h2>CPU-Verlauf (letzte 60 s)</h2><div id="chart"></div></div>
  <div class="card"><h2>Systeminfos</h2><div class="info" id="info"></div></div>
</section>

<footer>Vibe System Dashboard · psutil + Python · localhost-only</footer>

<script>
const hist = [];
const MAX = 60;

function cls(el, pct) {
  el.className = "fill" + (pct >= 90 ? " bad" : pct >= 70 ? " warn" : "");
}
function set(id, txt) { document.getElementById(id).textContent = txt; }

async function tick() {
  try {
    const s = await (await fetch("/api/stats")).json();
    set("host", s.hostname + " · " + s.os);
    const c = s.cpu.percent;
    set("v-cpu", c.toFixed(0) + " %");
    document.getElementById("b-cpu").style.width = c + "%";
    cls(document.getElementById("b-cpu"), c);
    set("m-cpu", (s.cpu.name || "CPU") + " · " + s.cpu.cores_physical + " Kerne / " + s.cpu.cores_logical + " Threads"
      + (s.cpu.freq_mhz ? " · " + (s.cpu.freq_mhz / 1000).toFixed(1) + " GHz" : ""));

    set("v-ram", s.memory.percent.toFixed(0) + " %");
    document.getElementById("b-ram").style.width = s.memory.percent + "%";
    cls(document.getElementById("b-ram"), s.memory.percent);
    set("m-ram", s.memory.used_gb + " / " + s.memory.total_gb + " GB belegt · Auslagerung " + s.memory.swap_percent.toFixed(0) + " %");

    set("v-disk", s.disk.percent.toFixed(0) + " %");
    document.getElementById("b-disk").style.width = s.disk.percent + "%";
    cls(document.getElementById("b-disk"), s.disk.percent);
    set("m-disk", s.disk.used_gb + " / " + s.disk.total_gb + " GB belegt"
      + (s.disk.windows_c_percent != null ? " · C: " + s.disk.windows_c_percent.toFixed(0) + " %" : ""));

    const temps = Object.values(s.cpu.temp || {});
    if (temps.length) {
      const t = Math.max(...temps);
      set("v-temp", t.toFixed(0) + " °C");
      const p = Math.min(100, t / 100 * 100);
      document.getElementById("b-temp").style.width = p + "%";
      cls(document.getElementById("b-temp"), p);
      set("m-temp", Object.keys(s.cpu.temp).join(", "));
    } else {
      set("v-temp", "–");
      set("m-temp", "Auf Windows evtl. nur als Administrator oder mit Open Hardware Monitor verfügbar");
      document.getElementById("b-temp").style.width = "0%";
    }

    hist.push(c); if (hist.length > MAX) hist.shift();
    draw();
    const batt = s.battery ? ("Akku: " + s.battery.percent + " %" + (s.battery.plugged ? " (lädt)" : "")) : "Netzbetrieb (kein Akku)";
    document.getElementById("info").innerHTML = [
      ["Betriebssystem", s.os], ["Hostname", s.hostname],
      ["CPU", s.cpu.name || "–"],
      ["Kerne / Threads", s.cpu.cores_physical + " / " + s.cpu.cores_logical],
      ["RAM gesamt", s.memory.total_gb + " GB"],
      ["Festplatte", s.disk.total_gb + " GB"],
      ["Netzwerk gesendet", s.net.sent_mb + " MB"],
      ["Netzwerk empfangen", s.net.recv_mb + " MB"],
      ["Energie", batt]
    ].map(([k, v]) => `<div><b>${k}</b>${v}</div>`).join("");
  } catch (e) { console.error(e); }
}

function draw() {
  const w = 720, h = 220, pad = {t: 14, r: 14, b: 22, l: 34};
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const x = i => pad.l + iw * i / (MAX - 1);
  const y = v => pad.t + ih - ih * v / 100;
  const path = hist.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + "," + y(v).toFixed(1)).join(" ");
  let grid = "";
  for (let g = 0; g <= 4; g++) {
    const gy = pad.t + ih * g / 4;
    grid += `<line x1="${pad.l}" y1="${gy}" x2="${w-pad.r}" y2="${gy}" stroke="rgba(255,255,255,.06)"/>`
         + `<text x="${pad.l-8}" y="${gy+4}" fill="#8b93a7" font-size="10" text-anchor="end">${100-25*g}</text>`;
  }
  const dots = hist.map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="2.5" fill="#7c6cff"/>`).join("");
  document.getElementById("chart").innerHTML =
    `<svg viewBox="0 0 ${w} ${h}" width="100%" preserveAspectRatio="none">
      <defs><linearGradient id="f" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#7c6cff" stop-opacity=".35"/><stop offset="100%" stop-color="#7c6cff" stop-opacity="0"/>
      </defs></defs>${grid}
      <path d="${path} L${x(hist.length-1)},${y(0)} L${x(0)},${y(0)} Z" fill="url(#f)"/>
      <path d="${path}" fill="none" stroke="#7c6cff" stroke-width="2.5" stroke-linejoin="round"/>${dots}
      <text x="${pad.l}" y="${h-6}" fill="#8b93a7" font-size="10">vor 60 s</text>
      <text x="${w-pad.r}" y="${h-6}" fill="#8b93a7" font-size="10" text-anchor="end">jetzt</text>
    </svg>`;
}

tick(); setInterval(tick, 2000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/stats":
            body = json.dumps(_latest).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/index.html"):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=poll_loop, daemon=True).start()
    print(f"Vibe System Dashboard: http://{HOST}:{PORT}  (Strg+C zum Beenden)")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
