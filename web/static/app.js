"use strict";

const $ = (sel) => document.querySelector(sel);
const CUR_SYM = { USD: "$", INR: "₹", EUR: "€", GBP: "£", AED: "AED " };
const curLocale = (cur) => (cur === "INR" ? "en-IN" : undefined);
function money(n, cur) {
  const sym = CUR_SYM[cur] || (cur ? cur + " " : "");
  return `${sym}${Number(n).toLocaleString(curLocale(cur), { maximumFractionDigits: 0 })}`;
}
const gUrl = (o, d, date) =>
  "https://www.google.com/travel/flights?q=" +
  encodeURIComponent(`flights from ${o} to ${d} on ${date} one way`);
const gUrlRT = (o, d, out, ret) =>
  "https://www.google.com/travel/flights?q=" +
  encodeURIComponent(`flights from ${o} to ${d} on ${out} returning ${ret}`);
const getAdults = () => $("#adults").value || 1;
const getCurrency = () => ($("#currency").value || "USD").toUpperCase();
const dow = (dateStr) => {
  const dt = new Date(dateStr + "T00:00:00");
  return isNaN(dt) ? "" : dt.toLocaleDateString("en-US", { weekday: "short" });
};

/* Price → colour on a mint → amber → coral scale */
function tier(p, lo, hi) {
  if (hi <= lo) return "rgb(70,217,160)";
  const t = Math.max(0, Math.min(1, (p - lo) / (hi - lo)));
  const stops = [[70, 217, 160], [255, 178, 62], [255, 106, 106]];
  const [a, b, f] = t < 0.5 ? [stops[0], stops[1], t * 2] : [stops[1], stops[2], (t - 0.5) * 2];
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/* Client-side mirror of the server's daily-cheapest + stats (for live scan) */
function computeDaily(records) {
  const best = {};
  for (const r of records) {
    const day = (r.departure || "").slice(0, 10);
    if (!day || r.price == null) continue;
    if (!best[day] || r.price < best[day].price) {
      best[day] = {
        date: day, price: r.price, currency: r.currency || "USD",
        airline: r.airline, departure_time: (r.departure || "").slice(11, 16),
        duration: r.duration, stops: r.stops, recorded_at: r.recorded_at,
        return_date: r.return_date || "",
      };
    }
  }
  return Object.keys(best).sort().map((d) => best[d]);
}
function computeStats(daily) {
  if (!daily.length) return {};
  const prices = daily.map((d) => d.price).sort((a, b) => a - b);
  const n = prices.length;
  const median = n % 2 ? prices[(n - 1) / 2] : (prices[n / 2 - 1] + prices[n / 2]) / 2;
  const cheapest = daily.reduce((m, d) => (d.price < m.price ? d : m), daily[0]);
  return {
    min: prices[0], max: prices[n - 1], median: Math.round(median),
    avg: Math.round(prices.reduce((s, p) => s + p, 0) / n), count: n,
    cheapest_date: cheapest.date, cheapest_airline: cheapest.airline,
    currency: daily[0].currency,
  };
}

const state = { origin: "DEL", destination: "DPS", records: [], tripMode: "oneway" };

/* ── Rendering ──────────────────────────────────────────────── */
function renderStats(s) {
  const box = $("#stats");
  if (!s || !s.count) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  const cur = s.currency;
  box.innerHTML = `
    <div class="stat hero"><div class="k">CHEAPEST DAY</div><div class="v">${money(s.min, cur)}</div><div class="sub">${s.cheapest_date} · ${s.cheapest_airline}</div></div>
    <div class="stat"><div class="k">MEDIAN</div><div class="v">${money(s.median, cur)}</div><div class="sub">across ${s.count} days</div></div>
    <div class="stat"><div class="k">AVERAGE</div><div class="v">${money(s.avg, cur)}</div><div class="sub">per-day cheapest</div></div>
    <div class="stat"><div class="k">PRICIEST</div><div class="v">${money(s.max, cur)}</div><div class="sub">worst day</div></div>
    <div class="stat"><div class="k">DAYS TRACKED</div><div class="v">${s.count}</div><div class="sub">travel dates</div></div>`;
}

function renderBestDeal(daily) {
  const box = $("#best-deal");
  if (!daily.length) { box.classList.add("hidden"); return; }
  const b = daily.reduce((m, d) => (d.price < m.price ? d : m), daily[0]);
  const stops = b.stops === 0 ? "Nonstop" : `${b.stops} stop${b.stops > 1 ? "s" : ""}`;
  const rt = !!b.return_date;
  const verify = rt ? gUrlRT(state.origin, state.destination, b.date, b.return_date)
                    : gUrl(state.origin, state.destination, b.date);
  box.classList.remove("hidden");
  box.innerHTML = `
    <div class="deal-body">
      <div class="deal-tag">${rt ? "BEST WEEKEND ROUND-TRIP" : "BEST FARE THIS MONTH"}</div>
      <div class="deal-route">${state.origin}<span class="via">${rt ? "⇄" : "✈"}</span>${state.destination}</div>
      <div class="deal-meta">
        <div><span class="k">${rt ? "OUTBOUND" : "TRAVEL DATE"}</span><span class="val">${b.date} · ${dow(b.date)}</span></div>
        ${rt ? `<div><span class="k">RETURN</span><span class="val ret">${b.return_date} · ${dow(b.return_date)}</span></div>` : ""}
        <div><span class="k">CARRIER</span><span class="val">${b.airline}</span></div>
        <div><span class="k">DEPART</span><span class="val">${b.departure_time || "—"}</span></div>
        <div><span class="k">${rt ? "OUTBOUND DUR." : "DURATION"}</span><span class="val">${b.duration || "—"}</span></div>
        <div><span class="k">ROUTING</span><span class="val">${stops}</span></div>
      </div>
      <div class="detail-actions">
        <button class="track-btn" id="deal-track">◉ Track this fare over time</button>
        ${compareHtml(state.origin, state.destination, b.date, b.return_date || "", rt, b.airline)}
      </div>
    </div>
    <div class="deal-price-panel">
      <div class="deal-cur">${CUR_SYM[b.currency] || b.currency}${rt ? " · round trip" : ""}</div>
      <div class="deal-price">${Number(b.price).toLocaleString(curLocale(b.currency), { maximumFractionDigits: 0 })}</div>
      <div class="barcode"></div>
      <a class="deal-verify" href="${verify}" target="_blank" rel="noopener">Verify on Google Flights ↗</a>
    </div>`;
  const dt = $("#deal-track");
  if (dt) dt.addEventListener("click", () => openWatch(b.date, b.return_date || ""));
}

function renderBoard(daily) {
  const wrap = $("#board-rows");
  const section = $("#board-section");
  if (!daily.length) { section.classList.add("hidden"); wrap.innerHTML = ""; return; }
  section.classList.remove("hidden");
  $("#board-route").textContent = `${state.origin} → ${state.destination}`;
  const lo = Math.min(...daily.map((d) => d.price));
  const hi = Math.max(...daily.map((d) => d.price));
  wrap.innerHTML = "";
  daily.forEach((d, i) => {
    const color = tier(d.price, lo, hi);
    const isBest = d.price === lo;
    const stopChip = d.stops === 0
      ? `<span class="chip direct">Direct</span>`
      : `<span class="chip stops">${d.stops} stop${d.stops > 1 ? "s" : ""}</span>`;
    const row = document.createElement("div");
    row.className = "brow" + (isBest ? " best" : "");
    row.style.setProperty("--tier", color);
    row.style.animationDelay = `${Math.min(i * 35, 700)}ms`;
    row.dataset.date = d.date;
    const rt = !!d.return_date;
    const star = isBest ? ' <span class="star">★</span>' : "";
    const dateCell = rt
      ? `${dow(d.date)} ${d.date.slice(5)}${star} <span class="ret">→ ${dow(d.return_date)} ${d.return_date.slice(5)}</span>`
      : `${d.date}${star}<span class="dow">${dow(d.date)}</span>`;
    const verify = rt ? gUrlRT(state.origin, state.destination, d.date, d.return_date)
                      : gUrl(state.origin, state.destination, d.date);
    row.innerHTML = `
      <span class="c-date">${dateCell}</span>
      <span class="c-price">${money(d.price, d.currency)}</span>
      <span class="c-air" title="${d.airline}">${d.airline}</span>
      <span class="c-dep">${d.departure_time || "—"}</span>
      <span class="c-dur">${d.duration || "—"}</span>
      <span class="c-stop">${stopChip}</span>
      <a class="verify-link" href="${verify}" target="_blank" rel="noopener">Verify ↗</a>`;
    row.addEventListener("click", (e) => {
      if (e.target.closest(".verify-link")) return;
      toggleDetail(row, d.date);
    });
    wrap.appendChild(row);
  });
}

function toggleDetail(row, date) {
  const existing = row.querySelector(".detail");
  if (existing) { existing.remove(); return; }
  const offers = state.records
    .filter((r) => (r.departure || "").slice(0, 10) === date)
    .sort((a, b) => a.price - b.price);
  const ret = offers[0] && offers[0].return_date ? offers[0].return_date : "";
  const airline = offers[0] ? offers[0].airline : "";
  const det = document.createElement("div");
  det.className = "detail";
  det.addEventListener("click", (e) => e.stopPropagation());  // don't collapse the row
  det.innerHTML =
    offers.map((o) => `
      <div class="detail-row">
        <span class="p">${money(o.price, o.currency)}</span>
        <span>${o.airline}</span>
        <span>${(o.departure || "").slice(11)} → ${(o.arrival || "").slice(11)}</span>
        <span>${o.duration || "—"}</span>
        <span>${o.stops === 0 ? "Direct" : o.stops + " stop"}</span>
      </div>`).join("") +
    `<div class="detail-note">${offers.length} option${offers.length !== 1 ? "s" : ""} recorded · last pulled ${offers[0] ? offers[0].recorded_at : "—"}</div>` +
    `<div class="detail-actions">
       <button class="track-btn">◉ Track this price over time</button>
       ${compareHtml(state.origin, state.destination, date, ret, state.tripMode === "weekend", airline)}
     </div>`;
  det.querySelector(".track-btn").addEventListener("click", () => openWatch(date, ret));
  row.appendChild(det);
}

function renderAnalysis(a) {
  const section = $("#analysis-section");
  const hasData = a && ((a.day_avg && Object.keys(a.day_avg).length) || (a.hour_avg && Object.keys(a.hour_avg).length));
  if (!hasData) { section.classList.add("hidden"); return; }
  section.classList.remove("hidden");

  const barBoard = (obj, fmtLabel) => {
    const entries = Object.entries(obj).filter(([, v]) => v != null);
    if (!entries.length) return `<div class="detail-note">No data yet.</div>`;
    const vals = entries.map(([, v]) => v);
    const lo = Math.min(...vals), hi = Math.max(...vals);
    return entries.map(([k, v]) => {
      const pct = hi <= lo ? 100 : 20 + ((v - lo) / (hi - lo)) * 80;
      const best = v === lo;
      return `<div class="bar-row ${best ? "best" : ""}">
        <span class="lbl">${fmtLabel(k)}${best ? " ★" : ""}</span>
        <span class="bar-track"><span class="bar-fill" style="width:${pct}%"></span></span>
        <span class="amt">${Math.round(v)}</span></div>`;
    }).join("");
  };

  $("#dow").innerHTML = barBoard(a.day_avg, (k) => k.slice(0, 3));
  $("#hour").innerHTML = barBoard(a.hour_avg, (k) => `${String(k).padStart(2, "0")}:00`);
  $("#reco").textContent = a.recommendation || "Not enough data yet.";
}

/* ── Data flows ─────────────────────────────────────────────── */
function syncRoute() {
  state.origin = ($("#origin").value || "").trim().toUpperCase();
  state.destination = ($("#destination").value || "").trim().toUpperCase();
  $("#origin").value = state.origin;
  $("#destination").value = state.destination;
}

async function loadHistory() {
  syncRoute();
  if (!state.origin || !state.destination) return;
  const trip = state.tripMode === "weekend" ? "roundtrip" : "oneway";
  const res = await fetch(`/api/history?origin=${state.origin}&destination=${state.destination}&trip=${trip}`);
  const data = await res.json();
  state.records = data.records || [];
  const daily = data.daily || [];
  markActiveChip();
  if (!daily.length) {
    ["#stats", "#best-deal", "#board-section", "#analysis-section"].forEach((s) => $(s).classList.add("hidden"));
    $("#empty").classList.remove("hidden");
    return;
  }
  $("#empty").classList.add("hidden");
  renderStats(data.stats);
  renderBestDeal(daily);
  renderBoard(daily);
  loadAnalysis();
}

async function loadAnalysis() {
  const res = await fetch(`/api/analysis?origin=${state.origin}&destination=${state.destination}`);
  renderAnalysis(await res.json());
}

async function liveScan() {
  syncRoute();
  if (!state.origin || !state.destination) return;
  const btnScan = $("#btn-scan"), btnLoad = $("#btn-load");
  btnScan.disabled = btnLoad.disabled = true;
  const weekend = state.tripMode === "weekend";
  const o = state.origin, d = state.destination, a = getAdults(), c = getCurrency();

  // Build the list of scan units (a day, or a Thu/Fri→Sun weekend pair)
  let units;
  try {
    if (weekend) {
      const rj = await (await fetch(`/api/weekend-pairs?date=${$("#date").value}&end_date=${$("#end-date").value}`)).json();
      if (rj.error) throw new Error(rj.error);
      units = (rj.pairs || []).map((p) => ({
        label: `${p.dow} ${p.out} → Sun ${p.ret}`,
        url: `/api/search-weekend?origin=${o}&destination=${d}&out=${p.out}&ret=${p.ret}&adults=${a}&currency=${c}`,
      }));
    } else {
      const rj = await (await fetch(`/api/date-range?date=${$("#date").value}&end_date=${$("#end-date").value}`)).json();
      if (rj.error) throw new Error(rj.error);
      units = (rj.dates || []).map((day) => ({
        label: day,
        url: `/api/search-day?origin=${o}&destination=${d}&date=${day}&adults=${a}&currency=${c}`,
      }));
    }
  } catch (e) { alert(e.message); btnScan.disabled = btnLoad.disabled = false; return; }

  const prog = $("#progress"), bar = $("#progress-bar"), lbl = $("#progress-label");
  prog.classList.remove("hidden");
  $("#empty").classList.add("hidden");

  const records = [];
  let ok = 0, fail = 0;
  for (let i = 0; i < units.length; i++) {
    lbl.textContent = `Scanning ${units[i].label}  ·  ${i + 1}/${units.length}`;
    bar.style.width = `${(i / units.length) * 100}%`;
    try {
      const j = await (await fetch(units[i].url)).json();
      if (j.offers && j.offers.length) { records.push(...j.offers); ok++; } else fail++;
    } catch { fail++; }
    state.records = records.slice();
    const daily = computeDaily(records);
    if (daily.length) {
      $("#empty").classList.add("hidden");
      renderStats(computeStats(daily));
      renderBestDeal(daily);
      renderBoard(daily);
    }
  }
  bar.style.width = "100%";
  lbl.textContent = `Done · ${ok} ${weekend ? "weekends" : "days"} found${fail ? ` · ${fail} empty` : ""}`;
  setTimeout(() => prog.classList.add("hidden"), 2500);
  btnScan.disabled = btnLoad.disabled = false;
  loadHistory();  // reconcile against the freshly-saved Excel + refresh analysis
}

function setTripMode(mode) {
  state.tripMode = mode;
  document.querySelectorAll("#trip-toggle button").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  const weekend = mode === "weekend";
  document.querySelector(".board-title h2").textContent =
    weekend ? "Weekend round-trips — cheapest per weekend" : "Departures — cheapest per day";
  document.querySelector(".board-head .c-date").textContent = weekend ? "Weekend (out → back)" : "Date";
  document.querySelector(".board-head .c-dep").textContent = weekend ? "Out dep" : "Dep";
  document.querySelector(".board-head .c-price").textContent = weekend ? "RT fare" : "Fare";
  $("#range-hint").innerHTML = weekend
    ? `Weekend mode: <strong>Thu/Fri departures → the next Sunday back</strong>. Fare is the round-trip total.`
    : `Empty dates → <strong>today through end of month</strong>, auto-rolling.`;
  loadHistory();
}

/* ── Route chips ────────────────────────────────────────────── */
let allRoutes = [];
function renderChips() {
  const box = $("#routes");
  box.innerHTML = allRoutes.map((r) =>
    `<span class="route-chip" data-o="${r.origin}" data-d="${r.destination}">${r.origin} → ${r.destination}</span>`).join("");
  box.querySelectorAll(".route-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $("#origin").value = chip.dataset.o;
      $("#destination").value = chip.dataset.d;
      loadHistory();
    });
  });
  markActiveChip();
}
function markActiveChip() {
  document.querySelectorAll(".route-chip").forEach((c) => {
    c.classList.toggle("active", c.dataset.o === state.origin && c.dataset.d === state.destination);
  });
}

/* ── Compare across platforms ───────────────────────────────── */
const AIRLINE_SITES = {
  // India
  "IndiGo": "https://www.goindigo.in", "Air India": "https://www.airindia.com",
  "Air India Express": "https://www.airindiaexpress.com", "Vistara": "https://www.airvistara.com",
  "Akasa Air": "https://www.akasaair.com", "SpiceJet": "https://www.spicejet.com",
  "Alliance Air": "https://www.allianceair.in", "Star Air": "https://www.starair.in",
  // Middle East
  "Emirates": "https://www.emirates.com", "Etihad": "https://www.etihad.com",
  "Etihad Airways": "https://www.etihad.com", "Qatar Airways": "https://www.qatarairways.com",
  "Saudia": "https://www.saudia.com", "Oman Air": "https://www.omanair.com",
  "Kuwait Airways": "https://www.kuwaitairways.com", "flydubai": "https://www.flydubai.com",
  "Air Arabia": "https://www.airarabia.com", "Gulf Air": "https://www.gulfair.com",
  "Royal Jordanian": "https://www.rj.com", "EgyptAir": "https://www.egyptair.com",
  "Turkish Airlines": "https://www.turkishairlines.com", "Pegasus": "https://www.flypgs.com",
  "Air Astana": "https://www.airastana.com", "Uzbekistan Airways": "https://www.uzairways.com",
  // SE / East Asia
  "Singapore Airlines": "https://www.singaporeair.com", "Scoot": "https://www.flyscoot.com",
  "Malaysia Airlines": "https://www.malaysiaairlines.com", "Batik Air": "https://www.batikair.com",
  "Batik Air Malaysia": "https://www.batikair.com", "Malindo Air": "https://www.batikair.com",
  "AirAsia": "https://www.airasia.com", "AirAsia X": "https://www.airasia.com",
  "Thai AirAsia": "https://www.airasia.com", "Thai AirAsia X": "https://www.airasia.com",
  "Indonesia AirAsia": "https://www.airasia.com", "Garuda Indonesia": "https://www.garuda-indonesia.com",
  "Citilink": "https://www.citilink.co.id", "Lion Air": "https://www.lionair.co.id",
  "Thai Lion Air": "https://www.lionairthai.com", "THAI": "https://www.thaiairways.com",
  "Thai Airways": "https://www.thaiairways.com", "Bangkok Airways": "https://www.bangkokair.com",
  "Vietnam Airlines": "https://www.vietnamairlines.com", "VietJet Air": "https://www.vietjetair.com",
  "Cathay Pacific": "https://www.cathaypacific.com", "HK Express": "https://www.hkexpress.com",
  "Philippine Airlines": "https://www.philippineairlines.com", "Cebu Pacific": "https://www.cebupacificair.com",
  "Japan Airlines": "https://www.jal.com", "ANA": "https://www.ana.co.jp",
  "All Nippon Airways": "https://www.ana.co.jp", "Korean Air": "https://www.koreanair.com",
  "Asiana Airlines": "https://flyasiana.com", "China Airlines": "https://www.china-airlines.com",
  "EVA Air": "https://www.evaair.com", "Air China": "https://www.airchina.com",
  "China Southern": "https://www.csair.com", "China Eastern": "https://www.ceair.com",
  "Hainan Airlines": "https://www.hainanairlines.com", "Xiamen Air": "https://www.xiamenair.com",
  // South Asia
  "SriLankan Airlines": "https://www.srilankan.com", "Biman Bangladesh Airlines": "https://www.biman-airlines.com",
  "Nepal Airlines": "https://www.nepalairlines.com.np", "Druk Air": "https://www.drukair.com.bt",
  "Maldivian": "https://www.maldivian.aero",
  // Oceania
  "Qantas": "https://www.qantas.com", "Jetstar": "https://www.jetstar.com",
  "Virgin Australia": "https://www.virginaustralia.com", "Air New Zealand": "https://www.airnewzealand.com",
  "Fiji Airways": "https://www.fijiairways.com",
  // Europe
  "Lufthansa": "https://www.lufthansa.com", "Swiss": "https://www.swiss.com",
  "Austrian Airlines": "https://www.austrian.com", "Brussels Airlines": "https://www.brusselsairlines.com",
  "British Airways": "https://www.britishairways.com", "Air France": "https://www.airfrance.com",
  "KLM": "https://www.klm.com", "Iberia": "https://www.iberia.com",
  "ITA Airways": "https://www.ita-airways.com", "TAP Air Portugal": "https://www.flytap.com",
  "Aer Lingus": "https://www.aerlingus.com", "Finnair": "https://www.finnair.com",
  "SAS": "https://www.flysas.com", "Scandinavian Airlines": "https://www.flysas.com",
  "Norwegian": "https://www.norwegian.com", "Ryanair": "https://www.ryanair.com",
  "easyJet": "https://www.easyjet.com", "Wizz Air": "https://www.wizzair.com",
  "Vueling": "https://www.vueling.com", "Virgin Atlantic": "https://www.virginatlantic.com",
  "LOT Polish Airlines": "https://www.lot.com", "Aegean Airlines": "https://en.aegeanair.com",
  // Americas
  "American Airlines": "https://www.aa.com", "Delta": "https://www.delta.com",
  "United": "https://www.united.com", "Southwest": "https://www.southwest.com",
  "JetBlue": "https://www.jetblue.com", "Alaska Airlines": "https://www.alaskaair.com",
  "Spirit Airlines": "https://www.spirit.com", "Frontier": "https://www.flyfrontier.com",
  "Hawaiian Airlines": "https://www.hawaiianairlines.com", "Air Canada": "https://www.aircanada.com",
  "WestJet": "https://www.westjet.com", "LATAM": "https://www.latamairlines.com",
  "Avianca": "https://www.avianca.com", "Aeromexico": "https://www.aeromexico.com",
  "Copa Airlines": "https://www.copaair.com", "GOL": "https://www.voegol.com.br",
  "Azul": "https://www.voeazul.com.br",
  // Africa
  "Ethiopian Airlines": "https://www.ethiopianairlines.com", "Kenya Airways": "https://www.kenya-airways.com",
  "South African Airways": "https://www.flysaa.com", "RwandAir": "https://www.rwandair.com",
  "Royal Air Maroc": "https://www.royalairmaroc.com",
};

/** Resolve an airline display name to its official site, tolerant of small variations. */
function airlineSite(name) {
  const first = (name || "").trim();
  if (!first) return null;
  if (AIRLINE_SITES[first]) return AIRLINE_SITES[first];
  const low = first.toLowerCase();
  for (const k in AIRLINE_SITES) if (k.toLowerCase() === low) return AIRLINE_SITES[k];
  for (const k in AIRLINE_SITES) {
    const kl = k.toLowerCase();
    if (low.startsWith(kl) || kl.startsWith(low)) return AIRLINE_SITES[k];
  }
  return null;
}

function compareLinks(o, d, date, ret, rt) {
  const slash = (s) => { const [y, m, dd] = s.split("-"); return `${dd}/${m}/${y}`; };
  const dmy = (s) => { const [y, m, dd] = s.split("-"); return `${dd}${m}${y}`; };
  const ymd = (s) => { const [y, m, dd] = s.split("-"); return `${y.slice(2)}${m}${dd}`; };
  const two = rt && ret;
  const mmt = two ? `${o}-${d}-${slash(date)}_${d}-${o}-${slash(ret)}` : `${o}-${d}-${slash(date)}`;
  return [
    ["Google Flights", two ? gUrlRT(o, d, date, ret) : gUrl(o, d, date), "google"],
    ["MakeMyTrip", `https://www.makemytrip.com/flight/search?itinerary=${encodeURIComponent(mmt)}&tripType=${two ? "R" : "O"}&paxType=A-1_C-0_I-0&cabinClass=E&intl=true`, ""],
    ["ixigo", `https://www.ixigo.com/search/result/flight?from=${o}&to=${d}&date=${dmy(date)}${two ? `&returnDate=${dmy(ret)}` : ""}&adults=1&children=0&infants=0&class=e`, ""],
    ["Skyscanner", `https://www.skyscanner.co.in/transport/flights/${o.toLowerCase()}/${d.toLowerCase()}/${ymd(date)}/${two ? ymd(ret) + "/" : ""}`, ""],
    ["KAYAK", two ? `https://www.kayak.co.in/flights/${o}-${d}/${date}/${ret}` : `https://www.kayak.co.in/flights/${o}-${d}/${date}`, ""],
  ];
}
/** One official-site chip per airline on the itinerary (codeshares list several). */
function airlineLinks(airline) {
  if (!airline) return [];
  const names = [...new Set(airline.split(",").map((s) => s.trim()).filter(Boolean))];
  return names.map((n) => {
    const url = airlineSite(n) || `https://www.google.com/search?q=${encodeURIComponent(n + " book flights official site")}`;
    return [`${n} ✈`, url, "airline"];
  });
}
function compareHtml(o, d, date, ret, rt, airline) {
  const links = compareLinks(o, d, date, ret, rt).concat(airlineLinks(airline));
  return `<span class="clabel">COMPARE</span>` + links.map(([label, url, cls]) =>
    `<a class="cmp-link ${cls || ""}" href="${url}" target="_blank" rel="noopener">${label} ↗</a>`).join("");
}

/* ── Price Watch ────────────────────────────────────────────── */
const watchState = { origin: "", destination: "", date: "", return_date: "", trip: "oneway" };
let emailConfigured = false;

function watchQuery() {
  return new URLSearchParams({
    origin: watchState.origin, destination: watchState.destination, date: watchState.date,
    trip: watchState.trip, return_date: watchState.return_date, currency: getCurrency(),
    threshold: ($("#watch-threshold").value || "").trim(),
  }).toString();
}

function updateAlertHint() {
  const el = $("#watch-alert-hint");
  if (!el) return;
  const th = ($("#watch-threshold").value || "").trim();
  if (!th) { el.textContent = ""; el.className = ""; return; }
  if (emailConfigured) {
    el.textContent = `✓ Email alert armed — you'll be emailed if it drops to/below ${money(th, getCurrency())}.`;
    el.className = "on";
  } else {
    el.textContent = "⚠ Email not set up yet — add SMTP_* + ALERT_TO to .env to receive drop emails.";
    el.className = "off";
  }
}

async function openWatch(date, ret) {
  watchState.origin = state.origin;
  watchState.destination = state.destination;
  watchState.date = date;
  watchState.return_date = ret || "";
  watchState.trip = state.tripMode === "weekend" ? "roundtrip" : "oneway";
  const sec = $("#watch-section");
  sec.classList.remove("hidden");
  $("#watch-target").textContent = watchState.trip === "roundtrip"
    ? `${watchState.origin} ⇄ ${watchState.destination} · out ${date} → back ${ret}`
    : `${watchState.origin} → ${watchState.destination} · ${date}`;
  sec.scrollIntoView({ behavior: "smooth", block: "start" });
  await refreshWatch();
}

async function refreshWatch() {
  const data = await (await fetch(`/api/timeline?${watchQuery()}`)).json();
  renderWatch(data);
}

function renderWatch(data) {
  const s = data.summary || {}, cur = data.currency || getCurrency();
  const sig = s.signal || "watch";
  const badge = { buy: "BUY", wait: "WAIT", watch: "KEEP WATCHING", neutral: "STABLE" }[sig] || "WATCH";
  const sg = $("#watch-signal");
  sg.className = `signal ${sig}`;
  sg.innerHTML = `<span class="badge">${badge}</span><div class="rec">${s.recommendation || ""}</div>`;

  const mv = (v) => (v == null ? "—" : money(v, cur));
  const deltaCls = s.delta > 0 ? "up" : s.delta < 0 ? "down" : "";
  const deltaTxt = (s.samples || 0) < 2 || s.delta == null ? "—"
    : `${s.delta > 0 ? "▲ +" : s.delta < 0 ? "▼ −" : ""}${money(Math.abs(s.delta), cur)} (${s.pct_change > 0 ? "+" : ""}${s.pct_change}%)`;
  $("#watch-stats").innerHTML = `
    <div class="wstat"><div class="k">CURRENT</div><div class="v">${mv(s.current)}</div><div class="sub">${s.current_airline || ""}</div></div>
    <div class="wstat"><div class="k">SINCE LAST</div><div class="v ${deltaCls}">${deltaTxt}</div><div class="sub">vs previous sample</div></div>
    <div class="wstat"><div class="k">LOWEST SEEN</div><div class="v down">${mv(s.observed_min)}</div><div class="sub">${s.observed_min_time ? s.observed_min_time.slice(5, 16) : ""}</div></div>
    <div class="wstat"><div class="k">HIGHEST SEEN</div><div class="v up">${mv(s.observed_max)}</div><div class="sub">${s.observed_max_time ? s.observed_max_time.slice(5, 16) : ""}</div></div>
    <div class="wstat"><div class="k">VOLATILITY</div><div class="v">${s.volatility_pct != null ? s.volatility_pct + "%" : "—"}</div><div class="sub">range swing</div></div>
    <div class="wstat"><div class="k">SAMPLES</div><div class="v">${s.samples || 0}</div><div class="sub">${s.trend || ""}</div></div>`;

  drawChart(data.points || [], cur);
  $("#watch-compare").innerHTML = compareHtml(watchState.origin, watchState.destination, watchState.date, watchState.return_date, watchState.trip === "roundtrip", s.current_airline);

  const tb = $("#watch-toggle");
  tb.classList.toggle("watching", !!data.watching);
  tb.textContent = data.watching ? "◉ Watching — stop" : "◉ Watch (auto)";
  updateAlertHint();
}

function drawChart(points, cur) {
  const svg = $("#watch-chart"), W = 720, H = 240, pad = 46;
  if (points.length < 2) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="#8b96b4" font-family="IBM Plex Mono" font-size="14">Need ≥2 samples to chart — Sample now, or leave the watch running.</text>`;
    return;
  }
  const prices = points.map((p) => p.price);
  const lo = Math.min(...prices), hi = Math.max(...prices), span = hi - lo || 1;
  const x = (i) => pad + (i / (points.length - 1)) * (W - 2 * pad);
  const y = (p) => pad + (1 - (p - lo) / span) * (H - 2 * pad);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.price).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points.length - 1).toFixed(1)},${H - pad} L${x(0).toFixed(1)},${H - pad} Z`;
  const dots = points.map((p, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(p.price).toFixed(1)}" r="3.2" fill="${p.price === lo ? "#46d9a0" : p.price === hi ? "#ff6a6a" : "#ffb23e"}"/>`).join("");
  const yHi = y(hi).toFixed(1), yLo = y(lo).toFixed(1);
  svg.innerHTML = `
    <defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="rgba(255,178,62,0.35)"/><stop offset="1" stop-color="rgba(255,178,62,0)"/>
    </linearGradient></defs>
    <line x1="${pad}" y1="${yHi}" x2="${W - pad}" y2="${yHi}" stroke="rgba(255,106,106,0.25)" stroke-dasharray="4 4"/>
    <line x1="${pad}" y1="${yLo}" x2="${W - pad}" y2="${yLo}" stroke="rgba(70,217,160,0.3)" stroke-dasharray="4 4"/>
    <path d="${area}" fill="url(#ag)"/>
    <path d="${line}" fill="none" stroke="#ffb23e" stroke-width="2"/>
    ${dots}
    <text x="${pad}" y="${(y(hi) - 8).toFixed(1)}" fill="#ff6a6a" font-family="IBM Plex Mono" font-size="11">${money(hi, cur)}</text>
    <text x="${pad}" y="${(y(lo) + 16).toFixed(1)}" fill="#46d9a0" font-family="IBM Plex Mono" font-size="11">${money(lo, cur)}</text>
    <text x="${pad}" y="${H - 12}" fill="#5a678a" font-family="IBM Plex Mono" font-size="10">${points[0].t.slice(5, 16)}</text>
    <text x="${W - pad}" y="${H - 12}" text-anchor="end" fill="#5a678a" font-family="IBM Plex Mono" font-size="10">${points[points.length - 1].t.slice(5, 16)}</text>`;
}

async function sampleNow() {
  const btn = $("#watch-sample"), label = btn.textContent;
  btn.disabled = true; btn.textContent = "Sampling…";
  try { await fetch(`/api/sample-now?${watchQuery()}`); await refreshWatch(); }
  finally { btn.disabled = false; btn.textContent = label; loadWatches(); }
}

async function toggleWatch() {
  const action = $("#watch-toggle").classList.contains("watching") ? "remove" : "add";
  await fetch(`/api/watch/${action}?${watchQuery()}`);
  await refreshWatch();
  loadWatches();
}

async function loadWatches() {
  const data = await (await fetch("/api/watches")).json();
  const bar = $("#watchbar"), ws = data.watches || [];
  const iv = $("#watch-interval"); if (iv) iv.textContent = data.interval_minutes || 30;
  emailConfigured = !!data.email_alerts; updateAlertHint();
  if (!ws.length) { bar.classList.add("hidden"); bar.innerHTML = ""; return; }
  bar.classList.remove("hidden");
  bar.innerHTML = `<span class="wb-label">WATCHING</span>` + ws.map((w) => {
    const label = w.trip === "roundtrip"
      ? `${w.origin}⇄${w.destination} ${w.date}→${w.return_date}`
      : `${w.origin}→${w.destination} ${w.date}`;
    return `<span class="watch-chip" data-o="${w.origin}" data-d="${w.destination}" data-date="${w.date}" data-ret="${w.return_date || ""}" data-trip="${w.trip}"><span class="live"></span>${label}</span>`;
  }).join("");
  bar.querySelectorAll(".watch-chip").forEach((c) => c.addEventListener("click", () => {
    setTripMode(c.dataset.trip === "roundtrip" ? "weekend" : "oneway");
    $("#origin").value = c.dataset.o; $("#destination").value = c.dataset.d;
    state.origin = c.dataset.o; state.destination = c.dataset.d;
    openWatch(c.dataset.date, c.dataset.ret);
  }));
}

/* ── Boot ───────────────────────────────────────────────────── */
function tickClock() {
  $("#clock").textContent = new Date().toLocaleTimeString("en-GB");
}

async function init() {
  tickClock(); setInterval(tickClock, 1000);
  $("#btn-load").addEventListener("click", loadHistory);
  $("#btn-scan").addEventListener("click", liveScan);
  document.querySelectorAll("#trip-toggle button").forEach((b) =>
    b.addEventListener("click", () => setTripMode(b.dataset.mode)));
  $("#watch-sample").addEventListener("click", sampleNow);
  $("#watch-toggle").addEventListener("click", toggleWatch);
  $("#watch-close").addEventListener("click", () => $("#watch-section").classList.add("hidden"));
  $("#watch-threshold").addEventListener("input", updateAlertHint);
  $("#swap").addEventListener("click", () => {
    const o = $("#origin").value; $("#origin").value = $("#destination").value; $("#destination").value = o;
    loadHistory();
  });
  [$("#origin"), $("#destination")].forEach((inp) =>
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") loadHistory(); }));

  try {
    const res = await fetch("/api/routes");
    const data = await res.json();
    allRoutes = data.routes || [];
    $("#provider-pill").textContent = data.provider || "ready";
    renderChips();
    if (allRoutes.length && !allRoutes.some((r) => r.origin === state.origin && r.destination === state.destination)) {
      $("#origin").value = allRoutes[0].origin;
      $("#destination").value = allRoutes[0].destination;
    }
  } catch { $("#provider-pill").textContent = "offline"; }

  loadHistory();
  loadWatches();
}

document.addEventListener("DOMContentLoaded", init);
