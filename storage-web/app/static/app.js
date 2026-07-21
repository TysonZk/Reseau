"use strict";

const $ = (id) => document.getElementById(id);

function level(pct) {
  if (pct >= 90) return "red";
  if (pct >= 75) return "amber";
  return "green";
}

function renderFilesystems(list) {
  if (!list.length) {
    $("fs").innerHTML = '<div class="empty">Aucun système de fichiers.</div>';
    return;
  }
  $("fs").innerHTML = list
    .map((f) => {
      const lv = level(f.usePct);
      return `
        <div class="card">
          <div class="fs-head">
            <div>
              <div class="fs-mount">${f.mount}</div>
              <div class="fs-dev">${f.fs}</div>
            </div>
            <div class="fs-pct k-${lv}">${f.usePct}%</div>
          </div>
          <div class="bar"><span class="b-${lv}" style="width:${f.usePct}%"></span></div>
          <div class="fs-stats">
            <span><b>${f.used}</b> utilisés</span>
            <span><b>${f.avail}</b> libres</span>
            <span>sur <b>${f.size}</b></span>
          </div>
        </div>`;
    })
    .join("");
}

function renderAlerts(list) {
  const el = $("alerts");
  if (!list.length) {
    el.className = "ok";
    el.innerHTML = "✅ Aucun système de fichiers critique";
    return;
  }
  el.className = "";
  el.innerHTML = list
    .map(
      (f) =>
        `<div class="alert"><span style="font-size:18px">⚠️</span><span class="m k-red">${f.mount}</span>
         <span style="color:var(--muted)">→ ${f.usePct}% utilisé · ${f.avail} restant sur ${f.size}</span></div>`
    )
    .join("");
}

function renderDisks(list) {
  if (!list.length) {
    $("disks").innerHTML = '<div class="empty">Aucun disque détecté.</div>';
    return;
  }
  $("disks").innerHTML = list
    .map(
      (d) => `
      <div class="card">
        <div class="mini-label">${d.type}</div>
        <div class="mini-name">${d.name}</div>
        <div class="mini-size">${d.size}</div>
        <div class="mini-tag">${d.model}</div>
      </div>`
    )
    .join("");
}

function renderDocker(list) {
  if (!list || !list.length) {
    $("docker-sec").hidden = true;
    return;
  }
  $("docker-sec").hidden = false;
  $("docker").innerHTML = list
    .map(
      (r) => `
      <tr>
        <td><span class="pill">${r.type}</span></td>
        <td class="mono">${r.total}</td>
        <td class="mono">${r.active}</td>
        <td class="mono">${r.size}</td>
        <td class="mono" style="color:var(--muted)">${r.reclaimable}</td>
      </tr>`
    )
    .join("");
}

function renderLoops(list) {
  if (!list.length) {
    $("loops").innerHTML = '<div class="empty">Aucun.</div>';
    return;
  }
  $("loops").innerHTML = list
    .map((l) => {
      const free = l.mount === "(non monté)";
      return `<div class="loop ${free ? "free" : ""}"><b>${l.name}</b> · ${l.size} · ${l.mount}</div>`;
    })
    .join("");
}

async function loadConfig() {
  try {
    const r = await fetch("/api/config");
    const { alerts } = await r.json();
    $("threshold-label").textContent = `(≥ ${alerts.threshold} %)`;
    const badge = $("wh-badge");
    const btn = $("wh-test");
    badge.hidden = false;
    if (alerts.enabled) {
      badge.className = "wh-badge on";
      badge.textContent = `🔔 Webhook ${alerts.format} · toutes les ${alerts.interval}s`;
      btn.hidden = false;
    } else {
      badge.className = "wh-badge off";
      badge.textContent = "🔕 Webhook désactivé";
      btn.hidden = true;
    }
  } catch (e) {
    /* silencieux : la config est optionnelle */
  }
}

async function testWebhook() {
  const btn = $("wh-test");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Envoi…";
  try {
    const r = await fetch("/api/test-webhook", { method: "POST" });
    const d = await r.json();
    btn.textContent = d.ok ? "✅ Envoyé !" : "❌ Échec";
  } catch {
    btn.textContent = "❌ Échec";
  }
  setTimeout(() => {
    btn.textContent = original;
    btn.disabled = false;
  }, 2500);
}

async function load() {
  try {
    const r = await fetch("/api/storage");
    const d = await r.json();
    $("host").textContent = d.hostname;
    $("time").textContent = new Date(d.generated).toLocaleTimeString("fr-FR");
    renderAlerts(d.alerts);
    renderFilesystems(d.filesystems);
    renderDisks(d.disks);
    renderDocker(d.docker);
    renderLoops(d.loops);
    $("foot").textContent = `storage-web · port 8888 · ${d.hostname} · généré le ${new Date(
      d.generated
    ).toLocaleString("fr-FR")}`;
  } catch (e) {
    $("alerts").textContent = "Erreur de chargement : " + e.message;
  }
}

document.getElementById("wh-test").addEventListener("click", testWebhook);

loadConfig();
load();
setInterval(load, 15000); // auto-refresh toutes les 15 s
