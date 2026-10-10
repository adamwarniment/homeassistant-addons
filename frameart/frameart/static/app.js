// Frame Art UI. Plain JS, no build step. All URLs are relative so HA ingress works.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const state = {
  settings: null,
  status: null,
  photos: [],
  frameDraft: null,   // unsaved frame style
  designPaths: null,  // explicit photo(s) for the designer preview
};

const SWATCHES = [
  ["Bright white", "#F3F2EE", "#FBFAF7"],
  ["Soft white", "#E8E6DF", "#F6F4EE"],
  ["Antique", "#E2D9C6", "#F3EEE2"],
  ["Warm grey", "#C9C3B8", "#ECE8E0"],
  ["Sage", "#BFC6B4", "#EEF0E8"],
  ["Navy", "#26324A", "#F3F1EA"],
  ["Charcoal", "#3A3A38", "#EFEDE7"],
  ["Black", "#151515", "#F2F0EA"],
];

// ------------------------------------------------------------------ api

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    init.headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, init);
  if (!res.ok && !(opts.allow || []).includes(res.status)) {
    let msg = res.statusText;
    try { msg = (await res.json()).error || msg; } catch { /* not json */ }
    throw new Error(msg);
  }
  return opts.raw ? res : res.json();
}

function toast(msg, bad = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("bad", bad);
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), bad ? 6000 : 2800);
}

const thumbUrl = (p) => `api/thumb?path=${encodeURIComponent(p)}`;
const baseName = (p) => p.split("/").pop();

function ago(ts) {
  if (!ts) return "—";
  const s = Math.round(Date.now() / 1000 - ts);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return new Date(ts * 1000).toLocaleString();
}
function until(ts) {
  if (!ts) return "paused";
  const s = Math.max(0, Math.round(ts - Date.now() / 1000));
  if (s < 60) return `in ${s}s`;
  if (s < 3600) return `in ${Math.floor(s / 60)} min`;
  return `in ${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`;
}

// ------------------------------------------------------------------ tabs

function showTab(name) {
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${name}`));
  try { localStorage.setItem("frameart.tab", name); } catch { /* storage blocked */ }
  if (name === "frame") requestPreview();
  if (name === "library") loadPhotos();
  if (name === "history") loadHistory();
}
$$(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
$$("[data-goto]").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.goto)));

// ------------------------------------------------------------------ status / now showing

let lastCurrentKey = null;

async function refreshStatus() {
  try {
    state.status = await api("api/status");
  } catch (e) {
    $("#tvPill").className = "pill bad";
    $("#tvPill").textContent = "Add-on unreachable";
    return;
  }
  const s = state.status;
  const pill = $("#tvPill");
  if (s.dry_run) { pill.className = "pill warn"; pill.textContent = "Dry run – no TV"; }
  else if (s.last_error) { pill.className = "pill bad"; pill.textContent = "TV problem"; }
  else if (s.tv && s.tv.reachable === false) { pill.className = "pill bad"; pill.textContent = "TV offline"; }
  else if (s.tv && s.tv.reachable) { pill.className = "pill ok"; pill.textContent = "TV connected"; }
  else { pill.className = "pill"; pill.textContent = s.busy ? "Working…" : "Ready"; }

  const banner = $("#errorBanner");
  let err = s.last_error;
  if (!err && !s.folder_exists) err = `The photo folder ${s.folder} doesn't exist yet. Create it (e.g. via Media → My media) or change it in Settings.`;
  banner.hidden = !err;
  banner.textContent = err || "";

  $("#pauseBtn").textContent = s.enabled ? "Pause" : "Resume";
  $("#nextBtn").disabled = s.busy;
  $("#nowNext").textContent = s.enabled ? until(s.next_at) : "Rotation paused";
  $("#nowCount").textContent = `${s.photo_count} photo${s.photo_count === 1 ? "" : "s"}`;

  const cur = s.current;
  $("#nowWhen").textContent = cur ? ago(cur.time) : "—";
  $("#nowWhy").textContent = cur ? `${cur.reason}${cur.reused ? " · re-used upload" : ""}` : "—";
  $("#nowTitle").textContent = cur ? cur.paths.map(baseName).join("  +  ") : "Nothing shown yet";
  const key = cur ? cur.content_id : null;
  if (key !== lastCurrentKey) {
    lastCurrentKey = key;
    loadNowImage(cur);
    if (!state.designPaths && $("#tab-frame").classList.contains("active")) requestPreview();
  }
}

async function loadNowImage(cur) {
  const img = $("#nowImg");
  $("#nowEmpty").hidden = !!cur;
  if (!cur) { img.removeAttribute("src"); return; }
  img.classList.add("loading");
  try {
    const res = await api("api/preview", { method: "POST", raw: true, body: { paths: cur.paths, width: 1600 } });
    setBlobSrc(img, await res.blob());
  } catch { /* photo may have been removed */ }
  img.classList.remove("loading");
}

function setBlobSrc(img, blob) {
  const old = img.dataset.blob;
  const url = URL.createObjectURL(blob);
  img.src = url;
  img.dataset.blob = url;
  if (old) setTimeout(() => URL.revokeObjectURL(old), 1000);
}

$("#nextBtn").addEventListener("click", async () => {
  const btn = $("#nextBtn");
  btn.disabled = true;
  btn.textContent = "Sending…";
  try {
    const r = await api("api/command", { method: "POST", body: { action: "next" } });
    r.ok ? toast("Sent to the Frame") : toast(r.error || "Could not show photo", true);
  } catch (e) { toast(e.message, true); }
  btn.textContent = "Next photo";
  btn.disabled = false;
  refreshStatus();
});

$("#pauseBtn").addEventListener("click", async () => {
  const action = state.status && state.status.enabled ? "pause" : "resume";
  await api("api/command", { method: "POST", body: { action } });
  state.settings.playback.enabled = action === "resume";
  fillSettingsForm();
  toast(action === "pause" ? "Rotation paused" : "Rotation resumed");
  refreshStatus();
});

// ------------------------------------------------------------------ frame designer

const fmt = {
  border: (v) => `${Math.round(v * 2160)} px`,
  bottom_weight: (v) => `+${Math.round(v * 2160)} px`,
  portrait_gap: (v) => `${Math.round(v * 2160)} px`,
  bevel: (v) => `${(v * 2160).toFixed(0)} px`,
  emboss_offset: (v) => `${Math.round(v * 2160)} px`,
  light_angle: (v) => (v < 60 ? "right" : v > 120 ? "left" : "top") + ` ${v}°`,
};
const pct = (v) => `${Math.round(v * 100)}%`;

function buildSwatches() {
  const wrap = $("#swatches");
  wrap.innerHTML = "";
  for (const [name, mat, core] of SWATCHES) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "swatch";
    b.dataset.mat = mat;
    b.innerHTML = `<b style="background:${mat}"></b><span>${name}</span>`;
    b.addEventListener("click", () => {
      state.frameDraft.mat_color = mat;
      state.frameDraft.core_color = core;
      syncFrameControls();
      frameChanged();
    });
    wrap.appendChild(b);
  }
}

function syncFrameControls() {
  const f = state.frameDraft;
  $$("#tab-frame [data-key]").forEach((el) => {
    const k = el.dataset.key;
    if (el.classList.contains("seg")) {
      $$("button", el).forEach((b) => b.classList.toggle("on", b.dataset.v === f[k]));
    } else if (el.type === "checkbox") {
      el.checked = !!f[k];
    } else if (el.type === "color") {
      el.value = (f[k] || "#000000").toLowerCase();
    } else {
      el.value = f[k];
      const out = el.parentElement.querySelector("output");
      if (out) out.textContent = (fmt[k] || pct)(Number(f[k]));
    }
  });
  $$(".swatch").forEach((s) => s.classList.toggle("on", s.dataset.mat.toLowerCase() === (f.mat_color || "").toLowerCase()));
  const dirty = JSON.stringify(f) !== JSON.stringify(state.settings.frame);
  const note = $("#dirtyNote");
  note.textContent = dirty ? "Unsaved changes" : "All changes saved";
  note.className = dirty ? "dirty" : "muted";
}

function frameChanged() {
  syncFrameControls();
  requestPreview();
}

$$("#tab-frame [data-key]").forEach((el) => {
  const k = el.dataset.key;
  if (el.classList.contains("seg")) {
    $$("button", el).forEach((b) => b.addEventListener("click", () => { state.frameDraft[k] = b.dataset.v; frameChanged(); }));
    return;
  }
  el.addEventListener("input", () => {
    if (el.type === "checkbox") state.frameDraft[k] = el.checked;
    else if (el.type === "color") state.frameDraft[k] = el.value.toUpperCase();
    else state.frameDraft[k] = Number(el.value);
    frameChanged();
  });
});

$("#reseed").addEventListener("click", () => {
  state.frameDraft.seed = Math.floor(Math.random() * 1e6);
  frameChanged();
});

let previewTimer = null;
let previewSeq = 0;
function requestPreview(width) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => renderPreview(width), 220);
}

async function renderPreview(width) {
  if (!state.frameDraft) return;
  const seq = ++previewSeq;
  const img = $("#designImg");
  $("#designSpin").hidden = false;
  img.classList.add("loading");
  try {
    const w = width || Math.min(1920, Math.round(img.clientWidth * (window.devicePixelRatio || 1)) || 1280);
    const res = await api("api/preview", {
      method: "POST", raw: true,
      body: { paths: state.designPaths, style: state.frameDraft, width: w },
    });
    if (seq === previewSeq) setBlobSrc(img, await res.blob());
  } catch (e) {
    if (seq === previewSeq) toast(e.message, true);
  }
  if (seq === previewSeq) {
    $("#designSpin").hidden = true;
    img.classList.remove("loading");
  }
}

$("#designPhoto").addEventListener("change", (e) => {
  state.designPaths = e.target.value ? [e.target.value] : null;
  requestPreview();
});
$("#designRandom").addEventListener("click", () => {
  if (!state.photos.length) return;
  const p = state.photos[Math.floor(Math.random() * state.photos.length)];
  $("#designPhoto").value = p.path;
  state.designPaths = [p.path];
  requestPreview();
});
$("#designZoom").addEventListener("click", async () => {
  const res = await api("api/preview", {
    method: "POST", raw: true,
    body: { paths: state.designPaths, style: state.frameDraft, width: 3840 },
  });
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
});

async function saveFrame(andShow) {
  try {
    state.settings = await api("api/settings", { method: "PUT", body: { frame: state.frameDraft } });
    state.frameDraft = { ...state.settings.frame };
    syncFrameControls();
    if (andShow) {
      toast("Saved – sending to the Frame…");
      const paths = state.designPaths || (state.status.current && state.status.current.paths) || null;
      const r = await api("api/command", { method: "POST", body: { action: "show", path: paths } });
      r.ok ? toast("Showing on the Frame") : toast(r.error, true);
      refreshStatus();
    } else {
      toast("Frame style saved");
    }
  } catch (e) { toast(e.message, true); }
}
$("#frameSave").addEventListener("click", () => saveFrame(false));
$("#frameSaveShow").addEventListener("click", () => saveFrame(true));
$("#frameRevert").addEventListener("click", () => {
  state.frameDraft = { ...state.settings.frame };
  frameChanged();
});

// ------------------------------------------------------------------ library

async function loadPhotos() {
  try { state.photos = await api("api/photos"); } catch (e) { toast(e.message, true); return; }
  renderLibrary();
  const sel = $("#designPhoto");
  const keep = sel.value;
  sel.replaceChildren(new Option("Current photo", ""), ...state.photos.map((p) => new Option(p.path, p.path)));
  sel.value = keep;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderLibrary() {
  const q = $("#libSearch").value.trim().toLowerCase();
  const list = state.photos.filter((p) => !q || p.path.toLowerCase().includes(q));
  const current = new Set((state.status && state.status.current && state.status.current.paths) || []);
  $("#libCount").textContent = `${list.length} of ${state.photos.length}`;
  const grid = $("#libGrid");
  grid.innerHTML = "";
  const empty = $("#libEmpty");
  empty.hidden = state.photos.length > 0;
  if (!state.photos.length) {
    const folder = state.settings ? state.settings.library.folder : "/media/frame";
    empty.innerHTML = `No photos yet. Drop images into <code>${escapeHtml(folder)}</code> — they'll appear here within a minute.`;
  }
  for (const p of list) {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "tile" + (current.has(p.path) ? " current" : "");
    tile.innerHTML = `<img loading="lazy" alt="" src="${thumbUrl(p.path)}">
      <div class="badges">${p.portrait ? "<span>portrait</span>" : ""}${p.shown ? "<span>shown</span>" : ""}</div>
      <div class="cap">${escapeHtml(baseName(p.path))}</div>`;
    tile.addEventListener("click", () => openPhoto(p));
    grid.appendChild(tile);
  }
}
$("#libSearch").addEventListener("input", renderLibrary);
$("#rescan").addEventListener("click", async () => {
  const r = await api("api/command", { method: "POST", body: { action: "rescan" } });
  toast(`Found ${r.count} photos`);
  loadPhotos();
});

let dialogPhoto = null;
function openPhoto(p) {
  dialogPhoto = p;
  $("#dlgImg").src = `api/thumb?path=${encodeURIComponent(p.path)}`;
  $("#dlgName").textContent = p.path;
  $("#dlgInfo").textContent = `${p.width} × ${p.height} · ${p.portrait ? "portrait" : "landscape"} · added ${ago(p.mtime)}` +
    (p.portrait && state.settings.playback.pair_portraits ? " · will be paired with another portrait" : "");
  $("#photoDialog").showModal();
}
$("#dlgShow").addEventListener("click", async () => {
  $("#photoDialog").close();
  toast("Sending to the Frame…");
  const r = await api("api/command", { method: "POST", body: { action: "show", path: dialogPhoto.path } });
  r.ok ? toast("Showing on the Frame") : toast(r.error, true);
  refreshStatus();
});
$("#dlgDesign").addEventListener("click", () => {
  $("#photoDialog").close();
  state.designPaths = [dialogPhoto.path];
  $("#designPhoto").value = dialogPhoto.path;
  showTab("frame");
});

// ------------------------------------------------------------------ settings

function fillSettingsForm() {
  const form = $("#settingsForm");
  for (const el of form.elements) {
    if (!el.name) continue;
    const [section, key] = el.name.split(".");
    const v = state.settings[section][key];
    if (el.type === "checkbox") el.checked = !!v;
    else el.value = v;
  }
}

async function saveSettings() {
  const patch = {};
  for (const el of $("#settingsForm").elements) {
    if (!el.name) continue;
    const [section, key] = el.name.split(".");
    patch[section] = patch[section] || {};
    patch[section][key] = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
  }
  state.settings = await api("api/settings", { method: "PUT", body: patch });
  fillSettingsForm();
  $("#settingsNote").textContent = "Saved " + new Date().toLocaleTimeString();
}

$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await saveSettings();
    toast("Settings saved");
    refreshStatus();
    loadPhotos();
  } catch (err) { toast(err.message, true); }
});

$("#tvTest").addEventListener("click", async () => {
  const out = $("#tvTestResult");
  out.textContent = "Connecting… (accept the prompt on the TV if it appears)";
  try {
    await saveSettings(); // test what's in the form, not what was saved earlier
    const s = await api("api/tv/test", { method: "POST" });
    out.textContent = !s.reachable ? `Not reachable: ${s.error || "unknown error"}`
      : s.art_mode_supported === false ? "Connected, but this TV has no Art Mode"
      : `Connected · art mode ${s.art_mode}`;
  } catch (e) { out.textContent = e.message; }
  refreshStatus();
});

let storageOthers = 0;
async function checkStorage() {
  const info = $("#storageInfo");
  const clean = $("#storageClean");
  info.textContent = "Asking the TV…";
  clean.hidden = true;
  try {
    const s = await api("api/tv/storage");
    if (!s.ok) { info.textContent = s.error; return; }
    storageOthers = s.others;
    info.textContent = `${s.total} photo${s.total === 1 ? "" : "s"} in My Photos: ${s.ours} managed by Frame Art, ` +
      `${s.others} old or unmanaged.` + (s.others ? "" : " Nothing to clean up.");
    clean.hidden = !s.others;
    clean.textContent = `Delete ${s.others} old photo${s.others === 1 ? "" : "s"}`;
  } catch (e) { info.textContent = e.message; }
}
$("#storageCheck").addEventListener("click", checkStorage);
$("#storageClean").addEventListener("click", async () => {
  if (!confirm(`Permanently delete ${storageOthers} photo(s) from the TV's My Photos?\n\n` +
               "Everything Frame Art isn't currently managing goes, except the image on screen. " +
               "Art Store pieces are not affected.")) return;
  const btn = $("#storageClean");
  btn.disabled = true;
  btn.textContent = "Deleting…";
  try {
    const r = await api("api/command", { method: "POST", body: { action: "cleanup" } });
    r.ok ? toast(`Deleted ${r.deleted} photo(s) from the TV`) : toast(r.error, true);
  } catch (e) { toast(e.message, true); }
  btn.disabled = false;
  checkStorage();
});

// ------------------------------------------------------------------ history

async function loadHistory() {
  const items = await api("api/history");
  const ol = $("#historyList");
  ol.innerHTML = items.length ? "" : `<li class="card empty-state">Nothing shown yet.</li>`;
  for (const h of items) {
    const li = document.createElement("li");
    li.className = "card";
    li.innerHTML = `<img loading="lazy" alt="" src="${thumbUrl(h.paths[0])}" onerror="this.style.visibility='hidden'">
      <div>${h.paths.map((p) => escapeHtml(baseName(p))).join(" + ")}
        <span class="tag">${escapeHtml(h.reason)}</span>${h.reused ? '<span class="tag">re-used</span>' : ""}</div>
      <div class="when">${new Date(h.time * 1000).toLocaleString()}</div>`;
    ol.appendChild(li);
  }
}

// ------------------------------------------------------------------ boot

(async function init() {
  buildSwatches();
  try {
    state.settings = await api("api/settings");
  } catch (e) {
    toast("Could not load settings: " + e.message, true);
    return;
  }
  state.frameDraft = { ...state.settings.frame };
  syncFrameControls();
  fillSettingsForm();
  await refreshStatus();
  loadPhotos();
  let tab = "now";
  try { tab = localStorage.getItem("frameart.tab") || "now"; } catch { /* storage blocked */ }
  showTab(tab);
  setInterval(refreshStatus, 5000);
  window.addEventListener("resize", () => $("#tab-frame").classList.contains("active") && requestPreview());
})();
