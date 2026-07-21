"""
Alertes de stockage par webhook.

Surveille périodiquement les systèmes de fichiers et envoie une notification
lorsqu'un montage dépasse le seuil (par défaut 85 %), puis une notification de
retour à la normale. Compatible Discord, Slack ou webhook JSON générique.

Configuration (variables d'environnement) :
  ALERT_WEBHOOK_URL      URL du webhook. Vide = alertes désactivées.
  ALERT_THRESHOLD        Seuil d'alerte en % (défaut 85).
  ALERT_INTERVAL         Intervalle de vérification en secondes (défaut 300).
  ALERT_WEBHOOK_FORMAT   auto | discord | slack | json (défaut auto).
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

from .collectors import collect

WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
THRESHOLD = int(os.environ.get("ALERT_THRESHOLD", "85"))
INTERVAL = max(30, int(os.environ.get("ALERT_INTERVAL", "300")))
FORMAT = os.environ.get("ALERT_WEBHOOK_FORMAT", "auto").strip().lower()

_LOCK_PATH = "/tmp/storage-web-monitor.lock"


def enabled() -> bool:
    return bool(WEBHOOK_URL)


def config() -> dict:
    return {
        "enabled": enabled(),
        "threshold": THRESHOLD,
        "interval": INTERVAL,
        "format": _resolve_format(),
    }


def _resolve_format() -> str:
    if FORMAT in ("discord", "slack", "json"):
        return FORMAT
    url = WEBHOOK_URL.lower()
    if "discord" in url:
        return "discord"
    if "slack" in url or "hooks.slack.com" in url:
        return "slack"
    return "json"


def _build_payload(event: str, host: str, fs: dict, message: str) -> dict:
    """Construit le corps de la requête selon le format du webhook."""
    fmt = _resolve_format()
    if fmt == "discord":
        color = 0xEF4444 if event == "alert" else 0x22C55E
        title = "🚨 Alerte stockage" if event == "alert" else "✅ Retour à la normale"
        return {
            "embeds": [
                {
                    "title": title,
                    "description": message,
                    "color": color,
                    "fields": [
                        {"name": "Hôte", "value": host, "inline": True},
                        {"name": "Montage", "value": fs["mount"], "inline": True},
                        {"name": "Utilisation", "value": f"{fs['usePct']}%", "inline": True},
                        {"name": "Libre", "value": fs["avail"], "inline": True},
                        {"name": "Taille", "value": fs["size"], "inline": True},
                    ],
                }
            ]
        }
    if fmt == "slack":
        emoji = ":rotating_light:" if event == "alert" else ":white_check_mark:"
        return {"text": f"{emoji} {message}"}
    # Générique : JSON exploitable par n'importe quel service
    return {
        "event": event,
        "hostname": host,
        "filesystem": fs,
        "message": message,
    }


def _post(payload: dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "storage-web"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 — on log et on continue
        print(f"[alerts] échec d'envoi du webhook : {exc}", flush=True)
        return False


def _notify(event: str, fs: dict, host: str) -> None:
    if event == "alert":
        message = (
            f"**{host}** — le montage `{fs['mount']}` est à **{fs['usePct']}%** "
            f"({fs['avail']} restant sur {fs['size']})."
        )
    else:
        message = (
            f"**{host}** — le montage `{fs['mount']}` est repassé sous le seuil "
            f"({fs['usePct']}%, {fs['avail']} libre)."
        )
    ok = _post(_build_payload(event, host, fs, message))
    print(f"[alerts] {event} {fs['mount']} ({fs['usePct']}%) -> envoyé={ok}", flush=True)


def send_test() -> bool:
    """Envoie une notification de test (utilisée par l'endpoint /api/test-webhook)."""
    if not enabled():
        return False
    data = collect()
    host = data["hostname"]
    fs = (data["filesystems"] or [{"mount": "/", "usePct": 0, "avail": "—", "size": "—"}])[0]
    message = f"🔔 Test de notification depuis **{host}** — le webhook storage-web fonctionne."
    return _post(_build_payload("test", host, fs, message))


def _loop(lock_handle) -> None:
    """Boucle de surveillance : compare l'état courant à l'état précédent."""
    print(
        f"[alerts] surveillance active — seuil {THRESHOLD}%, "
        f"intervalle {INTERVAL}s, format {_resolve_format()}",
        flush=True,
    )
    in_alert: dict[str, dict] = {}  # mount -> dernier fs en alerte
    # Ancre pour éviter que le lock ne soit libéré par le GC
    _keep = lock_handle  # noqa: F841
    while True:
        try:
            data = collect()
            host = data["hostname"]
            current = {f["mount"]: f for f in data["filesystems"] if f["usePct"] >= THRESHOLD}
            # Nouvelles alertes (montage franchissant le seuil)
            for mount, fs in current.items():
                if mount not in in_alert:
                    _notify("alert", fs, host)
            # Alertes résolues (montage repassé sous le seuil)
            for mount, fs in list(in_alert.items()):
                if mount not in current:
                    resolved = next((f for f in data["filesystems"] if f["mount"] == mount), fs)
                    _notify("resolved", resolved, host)
            in_alert = current
        except Exception as exc:  # noqa: BLE001
            print(f"[alerts] erreur dans la boucle : {exc}", flush=True)
        time.sleep(INTERVAL)


def _acquire_singleton_lock():
    """
    Verrou inter-processus : garantit qu'un seul worker gunicorn lance la
    surveillance (sinon les webhooks seraient envoyés en double).
    Renvoie le descripteur de fichier verrouillé, ou None si déjà pris.
    """
    try:
        import fcntl

        fh = open(_LOCK_PATH, "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        return None
    except Exception:  # noqa: BLE001 — fcntl absent (non-Unix) : on tolère
        return object()


def start_monitor() -> None:
    """Démarre le thread de surveillance (idempotent, un seul worker actif)."""
    if not enabled():
        print("[alerts] aucun ALERT_WEBHOOK_URL défini — alertes désactivées", flush=True)
        return
    lock = _acquire_singleton_lock()
    if lock is None:
        # Un autre worker gère déjà la surveillance
        return
    threading.Thread(target=_loop, args=(lock,), daemon=True).start()
