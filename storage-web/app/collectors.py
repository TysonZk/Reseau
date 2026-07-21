"""
Collecte des informations de stockage de l'hôte.

Équivalent Python de storage-info.sh : df, lsblk, docker, périphériques loop.

En conteneur, on entre dans les namespaces de l'hôte (PID 1) via `nsenter`
pour que df/lsblk/docker reflètent l'hôte et non le conteneur. Activé avec
la variable d'environnement HOST_NSENTER=1 (posée par docker-compose).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime, timezone

# Préfixe nsenter pour exécuter les commandes dans les namespaces de l'hôte
_USE_NSENTER = os.environ.get("HOST_NSENTER", "").strip().lower() in ("1", "true", "yes")
_NSENTER_PREFIX = ["nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "--"]

# Unités pour convertir « 7.8T », « 63B »… en octets (tri / calculs éventuels)
_UNITS = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15, "E": 1e18}


def _exec(cmd: list[str], timeout: int) -> tuple[int, str]:
    """Exécute une commande, renvoie (returncode, stdout). -1 si échec de lancement."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return out.returncode, out.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return -1, ""


def _run(cmd: list[str], timeout: int = 15) -> str:
    """
    Exécute une commande et renvoie stdout (ou '' en cas d'échec).

    En conteneur (HOST_NSENTER=1), tente d'abord via nsenter pour cibler
    l'hôte ; si nsenter échoue (namespaces restreints sur la VM, binaire
    absent…), bascule automatiquement sur une exécution directe. Rend l'outil
    portable sur n'importe quelle VM Linux, avec ou sans privilèges hôte.
    """
    if _USE_NSENTER:
        code, out = _exec(_NSENTER_PREFIX + cmd, timeout)
        if code == 0:
            return out
        # nsenter indisponible/refusé → repli sur exécution directe
    code, out = _exec(cmd, timeout)
    return out if code == 0 else ""


def to_bytes(size: str) -> float:
    """Convertit une taille lisible ('7.8T', '81G', '63B') en octets."""
    if not size:
        return 0
    m = re.match(r"^([\d.]+)\s*([KMGTPE]?)i?B?$", str(size).strip(), re.IGNORECASE)
    if not m:
        return 0
    return float(m.group(1)) * _UNITS.get(m.group(2).upper(), 1)


def get_filesystems() -> list[dict]:
    out = _run(["df", "-h", "-x", "tmpfs", "-x", "overlay", "-x", "devtmpfs"])
    rows = []
    for line in out.strip().splitlines()[1:]:
        p = line.split()
        if len(p) < 6:
            continue
        pct = re.sub(r"\D", "", p[4]) or "0"
        rows.append(
            {
                "fs": p[0],
                "size": p[1],
                "used": p[2],
                "avail": p[3],
                "usePct": int(pct),
                "mount": p[5],
            }
        )
    return rows


def get_disks() -> list[dict]:
    out = _run(["lsblk", "-d", "-e", "7", "-o", "NAME,SIZE,TYPE,MODEL"])
    rows = []
    for line in out.strip().splitlines()[1:]:
        m = re.match(r"^(\S+)\s+(\S+)\s+(\S+)\s*(.*)$", line)
        if not m:
            continue
        rows.append(
            {
                "name": m.group(1),
                "size": m.group(2),
                "type": m.group(3),
                "model": (m.group(4) or "").strip() or "—",
            }
        )
    return rows


def get_loops() -> list[dict]:
    out = _run(["lsblk", "-o", "NAME,SIZE,MOUNTPOINTS"])
    rows = []
    for line in out.strip().splitlines():
        if not line.startswith("loop"):
            continue
        p = line.split()
        rows.append(
            {
                "name": p[0],
                "size": p[1] if len(p) > 1 else "—",
                "mount": p[2] if len(p) > 2 else "(non monté)",
            }
        )
    return rows


def get_docker() -> list[dict] | None:
    if not _USE_NSENTER and not shutil.which("docker"):
        return None
    out = _run(["docker", "system", "df"])
    if not out:
        return None
    rows = []
    for line in out.strip().splitlines()[1:]:
        m = re.match(r"^(.+?)\s{2,}(\d+)\s+(\d+)\s+(\S+)\s+(.*)$", line)
        if not m:
            continue
        rows.append(
            {
                "type": m.group(1).strip(),
                "total": m.group(2),
                "active": m.group(3),
                "size": m.group(4),
                "reclaimable": m.group(5).strip(),
            }
        )
    return rows or None


def get_hostname() -> str:
    out = _run(["hostname"]).strip()
    return out or os.uname().nodename


def collect() -> dict:
    """Rassemble toutes les données de stockage en un dictionnaire JSON-able."""
    filesystems = get_filesystems()
    return {
        "hostname": get_hostname(),
        "generated": datetime.now(timezone.utc).isoformat(),
        "filesystems": filesystems,
        "alerts": [f for f in filesystems if f["usePct"] >= 85],
        "disks": get_disks(),
        "loops": get_loops(),
        "docker": get_docker(),
    }
