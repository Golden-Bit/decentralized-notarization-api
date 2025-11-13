# -*- coding: utf-8 -*-
"""
utils.py (Scenario 1, notarizzazione reale)

Modifiche chiave (questa versione):
- Usa un singleton B4AssetManager per lo stesso wallet aziendale.
- simulate_transaction(...) ESEGUE la creazione ASA 1/1 (mint) su Algorand.
- NESSUN campo 'scenario' nei metadati (rimosso definitivamente).
- Aggiunti: metadata_url (link API per scaricare l'on-chain metadata JSON salvato a file),
  metadata_sha256_hex/b64, info on-chain (asset_id, round, fee, fv/lv, addresses ruoli, genesis,
  unit_name/asset_name, ecc.).
- Salvataggio su disco del JSON usato come 'metadata' su blockchain in: "<file>-ONCHAIN-METADATA.JSON".
- Campi legacy per retrocompatibilità (commentati in-line) popolati con valori derivati
  dall'operazione reale: es. 'txid' = str(asset_id), 'sender', 'receiver', 'note', 'round_time'.
- API invariata: firma di simulate_transaction() e le altre utility non cambiano.

Dipendenze:
- asset_manager/b4dapp_asset_manager.py
- sdk/b4dapp_sdk.py
"""

import os
import io
import json
import shutil
import zipfile
import base64
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from urllib.parse import quote

from fastapi import HTTPException

# === Asset Manager (singleton) ===============================================
from asset_manager.b4dapp_asset_manager import B4AssetManager, ApiError


# -----------------------------------------------------------------------------
# Configurazione del singleton per l'asset manager
# (parametri anche da variabili d'ambiente)
# -----------------------------------------------------------------------------
"""_MANAGER_SINGLETON: B4AssetManager | None = None


def _get_asset_manager() -> B4AssetManager:
    global _MANAGER_SINGLETON
    if _MANAGER_SINGLETON is not None:
        return _MANAGER_SINGLETON

    base_url = os.getenv("B4_BASE_URL", "http://65.21.178.127:8080")
    email = os.getenv("B4_EMAIL", "luca@luca.com")
    password = os.getenv("B4_PASSWORD", "luca")
    config_path = os.getenv("B4_CONFIG_PATH", "b4dapp_config.json")
    blockchain = os.getenv("B4_BLOCKCHAIN", "ALGO")
    hsm_id = os.getenv("B4_HSM_ID", "hsm_test_0")
    algod_id = os.getenv("B4_ALGOD_ID", "algod_client_test_0")
    indexer_id = os.getenv("B4_INDEXER_ID", "indexer_client_test_0")

    from asset_manager.b4dapp_asset_manager import B4AssetManager as _B4
    min_balance = int(os.getenv("B4_MIN_BALANCE", _B4.DEFAULT_MIN_BALANCE))
    topup_amount = int(os.getenv("B4_TOPUP_AMOUNT", _B4.DEFAULT_TOPUP_AMOUNT))

    _MANAGER_SINGLETON = B4AssetManager(
        base_url=base_url,
        email=email,
        password=password,
        config_path=config_path,
        app_name=None,
        wallet_label=None,
        blockchain=blockchain,
        hsm_id=hsm_id,
        algod_id=algod_id,
        indexer_id=indexer_id,
        min_balance=min_balance,
        topup_amount=topup_amount,
    )
    return _MANAGER_SINGLETON
"""

def _get_asset_manager() -> B4AssetManager:
    base_url = os.getenv("B4_BASE_URL", "http://65.21.178.127:8080")
    email = os.getenv("B4_EMAIL", "luca@luca.com")
    password = os.getenv("B4_PASSWORD", "luca")
    config_path = os.getenv("B4_CONFIG_PATH", "b4dapp_config.json")
    blockchain = os.getenv("B4_BLOCKCHAIN", "ALGO")
    hsm_id = os.getenv("B4_HSM_ID", "hsm_test_0")
    algod_id = os.getenv("B4_ALGOD_ID", "algod_client_test_0")
    indexer_id = os.getenv("B4_INDEXER_ID", "indexer_client_test_0")

    from asset_manager.b4dapp_asset_manager import B4AssetManager as _B4
    min_balance = int(os.getenv("B4_MIN_BALANCE", _B4.DEFAULT_MIN_BALANCE))
    topup_amount = int(os.getenv("B4_TOPUP_AMOUNT", _B4.DEFAULT_TOPUP_AMOUNT))

    # NIENTE singleton: ogni volta un manager nuovo
    return B4AssetManager(
        base_url=base_url,
        email=email,
        password=password,
        config_path=config_path,
        app_name=None,
        wallet_label=None,
        blockchain=blockchain,
        hsm_id=hsm_id,
        algod_id=algod_id,
        indexer_id=indexer_id,
        min_balance=min_balance,
        topup_amount=topup_amount,
    )

# -----------------------------------------------------------------------------
# Utility locali
# -----------------------------------------------------------------------------
def _safe_target(root: Path, relative: str) -> Path:
    """Costruisce un path canonico ed evita traversal (`..`)."""
    p = (root / Path(relative)).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise HTTPException(400, "Percorso non ammesso")
    return p


def _read_metadata(meta_path: Path) -> Dict[str, Any]:
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata non trovato: {meta_path}")
    try:
        return json.loads(meta_path.read_text())
    except Exception as e:
        raise RuntimeError(f"Errore lettura metadata: {meta_path} -> {e}")


def _write_metadata(meta_path: Path, data: Dict[str, Any]) -> None:
    meta_path.write_text(json.dumps(data, indent=4))


def _sanitize_unit_name(s: str) -> str:
    """
    Unit name ASA: max 8 char, preferibilmente [A-Za-z0-9_].
    Strategia: uppercase, sostituisci non-alfanumerici con '_', tronca a 8.
    """
    s = "".join(ch if ch.isalnum() else "_" for ch in s.upper())
    return s[:8] if len(s) > 8 else s


def _sanitize_asset_name(s: str) -> str:
    """
    Asset name ASA: ~32 char pratici.
    Strategia: trim, sostituzione caratteri non stampabili, tronca a 32.
    """
    s = s.strip()
    s = "".join(ch if ch.isprintable() else "?" for ch in s)
    return s[:32] if len(s) > 32 else s


def _extract_asset_id(resp: Dict[str, Any]) -> int:
    for k in ("asset-index", "asset_id"):
        if k in resp:
            return int(resp[k])
    if "asset" in resp and isinstance(resp["asset"], dict) and "index" in resp["asset"]:
        return int(resp["asset"]["index"])
    raise RuntimeError(f"Impossibile ricavare asset_id dalla risposta: {resp}")


def _build_onchain_metadata_url(storage_id: str, relative_path: str) -> str:
    """
    Costruisce l'URL pubblico per scaricare il JSON di on-chain metadata salvato a file.
    Usa env NOTARIZATION_PUBLIC_BASE_URL (default http://127.0.0.1:8077/notarization-api)
    Endpoint: /storage/{storage_id}/metadata-onchain/{relative_path}
    """

    base = os.getenv("NOTARIZATION_PUBLIC_BASE_URL", "http://34.13.153.241:8666/notarization-api").rstrip("/")
    base = os.getenv("NOTARIZATION_PUBLIC_BASE_URL", "http://65.109.230.229:8666/notarization-api").rstrip("/")
    encoded_rel = quote(relative_path.strip("/"), safe="/")
    return f"{base}/storage/{storage_id}/metadata-onchain/{encoded_rel}"


def _build_content_download_url(storage_id: str, relative_path: str) -> str:
    """
    URL pubblico per scaricare il FILE originale.
    Endpoint: /storage/{storage_id}/download/{relative_path}
    """
    base = os.getenv("NOTARIZATION_PUBLIC_BASE_URL", "http://34.13.153.241:8666/notarization-api").rstrip("/")
    base = os.getenv("NOTARIZATION_PUBLIC_BASE_URL", "http://65.109.230.229:8666/notarization-api").rstrip("/")
    encoded_rel = quote(relative_path.strip("/"), safe="/")
    return f"{base}/storage/{storage_id}/download/{encoded_rel}"


# -----------------------------------------------------------------------------
# SCENARIO 1: notarizzazione reale (mint ASA 1/1) — SENZA campo 'scenario'
# -----------------------------------------------------------------------------
def simulate_transaction(storage_id: str, relative_path: str):
    """
    Firma invariata per compatibilità con l'API.

    Passi:
      1) Legge i metadati del documento.
      2) Inizializza il wallet condiviso (singleton).
      3) Prepara campi ASA: unit_name (<=8), asset_name (<=32), note, metadata JSON.
      4) Calcola hash del metadata JSON (hex + base64) e costruisce metadata_url pubblico.
      5) Salva su disco l'on-chain metadata JSON in "<file>-ONCHAIN-METADATA.JSON".
      6) Crea ASA 1/1 (roles=self).
      7) Aggiorna i metadati del documento in 'validations' con info on-chain.
         - NB: nessun campo 'scenario'. Campi legacy mantenuti (txid/sender/receiver/note/round_time).
    """
    # Localizza file e metadata
    root = Path("DATA") / storage_id
    content_path = _safe_target(root, relative_path)
    meta_path = content_path.parent / f"{content_path.name}-METADATA.JSON"
    onchain_meta_path = content_path.parent / f"{content_path.name}-ONCHAIN-METADATA.JSON"

    try:
        meta = _read_metadata(meta_path)
    except Exception:
        return  # non interrompe l'app

    # Hash del documento (già calcolato da save_document_and_metadata)
    doc_hash = meta.get("document_hash")
    if not doc_hash:
        try:
            file_bytes = content_path.read_bytes()
            doc_hash = hashlib.sha256(file_bytes).hexdigest()
            meta["document_hash"] = doc_hash
            _write_metadata(meta_path, meta)
        except Exception:
            return

    # Manager condiviso
    try:
        mgr = _get_asset_manager()
    except Exception:
        return

    # Prepara campi ASA
    unit_name_seed = f"DOC{doc_hash[:6]}".upper()
    unit_name = _sanitize_unit_name(unit_name_seed)
    asset_name = _sanitize_asset_name(content_path.stem)
    note = f"notarization {storage_id}/{relative_path}"

    # Metadata on-chain (JSON) — SALVATO ANCHE A FILE
    onchain_meta = {
        "hash": doc_hash,          # sha256 del FILE notarizzato (hex)
        "storage_id": storage_id,
        "path": relative_path,     # percorso relativo nello storage
        "file": content_path.name,
    }
    onchain_meta_str = json.dumps(onchain_meta, ensure_ascii=False)
    onchain_meta_bytes = onchain_meta_str.encode("utf-8")
    metadata_sha256_hex = hashlib.sha256(onchain_meta_bytes).hexdigest()  # hash dei byte del JSON on-chain
    metadata_sha256_b64 = base64.b64encode(bytes.fromhex(metadata_sha256_hex)).decode("ascii")
    metadata_len = len(onchain_meta_bytes)

    # Scrive il JSON on-chain su disco accanto al METADATA standard
    try:
        onchain_meta_path.write_text(json.dumps(onchain_meta, ensure_ascii=False, indent=4))
    except Exception:
        # non blocca la notarizzazione; semplicemente non avremo il file scaricabile
        pass

    # URL pubblici (serviranno nella validazione e nell'ASA url)
    metadata_url = _build_onchain_metadata_url(storage_id, relative_path)   # punta al *JSON on-chain salvato*
    content_download_url = _build_content_download_url(storage_id, relative_path)

    # Mint effettivo (con funding automatico nel manager)
    try:
        create_res = mgr.create_asset(
            unit_name=unit_name,
            asset_name=asset_name,
            total=1,
            decimals=0,
            default_frozen=False,
            note=metadata_url,#note,
            metadata_url="$note",#metadata_url,          # URL esposto dall'API → on-chain metadata file
            metadata=onchain_meta_str,          # JSON on-chain (il cui SHA-256 è metadata_sha256_*)
            roles_mode="self",
            ensure_min_balance=None,
            ensure_topup_amount=None,
        )
        asset_id = _extract_asset_id(create_res)

        # Estrazione dettagli dalla risposta txn (se presenti)
        txn_obj = create_res.get("txn", {}).get("txn", {}) if isinstance(create_res.get("txn"), dict) else {}
        apar = txn_obj.get("apar", {}) if isinstance(txn_obj, dict) else {}

        confirmed_round = create_res.get("confirmed-round")
        fee = txn_obj.get("fee")
        first_valid = txn_obj.get("fv")
        last_valid = txn_obj.get("lv")
        genesis_id = txn_obj.get("gen")
        genesis_hash_b64 = txn_obj.get("gh")

        # addresses di ruolo (presenti in 'apar')
        role_manager = apar.get("m")
        role_reserve = apar.get("r")
        role_freeze = apar.get("f")
        role_clawback = apar.get("c")

        # Entry di validazione (SENZA 'scenario')
        validation_entry = {
            "network": "algo",
            "type": "asa_mint",
            "timestamp": datetime.utcnow().isoformat(),

            # Identificativi asset
            "asset_id": asset_id,
            "unit_name": unit_name,
            "asset_name": asset_name,

            # Indirizzi ruoli (per policy & audit)
            "addresses": {
                "creator": mgr.creator_address,
                "manager": role_manager,
                "reserve": role_reserve,
                "freeze": role_freeze,
                "clawback": role_clawback,
            },

            # Contesto rete / block params
            "confirmed_round": confirmed_round,
            "fee": fee,
            "first_valid": first_valid,
            "last_valid": last_valid,
            "genesis_id": genesis_id,
            "genesis_hash_b64": genesis_hash_b64,

            # Metadata commitment e URL
            "metadata_url": metadata_url,                     # URL pubblico dell'on-chain JSON salvato
            "metadata_sha256_hex": metadata_sha256_hex,       # sha256( byte(JSON on-chain) )
            "metadata_sha256_b64": metadata_sha256_b64,
            "metadata_len": metadata_len,
            "onchain_metadata_file": onchain_meta_path.name,  # nome file locale salvato

            # Extra utili per le UI
            "content_download_url": content_download_url,

            # Risposta raw (utile per troubleshooting)
            "raw": create_res,
        }

        # ----------------------------
        # Campi LEGACY (retrocompat) |
        # ----------------------------
        # NB: mantenuti per vecchie interfacce. Da deprecare in futuro.
        validation_entry["txid"] = str(asset_id)                  # legacy: mappato all'asset_id
        validation_entry["sender"] = mgr.creator_address          # legacy: per UI che mostrano 'sender'
        validation_entry["receiver"] = mgr.creator_address        # legacy: non esiste in acfg; usiamo creator
        validation_entry["note"] = note                           # legacy: nota testuale
        validation_entry["round_time"] = datetime.utcnow().isoformat()  # legacy: timestamp approssimato

        if "validations" not in meta or not isinstance(meta.get("validations"), list):
            meta["validations"] = []
        meta["validations"].append(validation_entry)
        _write_metadata(meta_path, meta)

    except ApiError as e:
        err_entry = {
            "network": "algo",
            "type": "asa_mint_error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            # --- LEGACY: mantenuti per vecchie UI (valori neutri) ---
            "txid": None,
            "sender": None,
            "receiver": None,
            "note": None,
            "round_time": datetime.utcnow().isoformat(),
        }
        if "validations" not in meta or not isinstance(meta.get("validations"), list):
            meta["validations"] = []
        meta["validations"].append(err_entry)
        try:
            _write_metadata(meta_path, meta)
        except Exception:
            pass
        return
    except Exception as e:
        err_entry = {
            "network": "algo",
            "type": "unexpected_error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            # --- LEGACY: mantenuti per vecchie UI (valori neutri) ---
            "txid": None,
            "sender": None,
            "receiver": None,
            "note": None,
            "round_time": datetime.utcnow().isoformat(),
        }
        if "validations" not in meta or not isinstance(meta.get("validations"), list):
            meta["validations"] = []
        meta["validations"].append(err_entry)
        try:
            _write_metadata(meta_path, meta)
        except Exception:
            pass
        return


# -----------------------------------------------------------------------------
# ENUMERAZIONE COMPLETA DI UNO STORAGE (unchanged)
# -----------------------------------------------------------------------------
def list_files_with_metadata(storage_id: str) -> dict:
    """
    Scorre ricorsivamente DATA/<storage_id> e raccoglie tutti i file
    metadata (*-METADATA.JSON); la chiave è il percorso relativo del file
    originale (cartella/…/nome.ext), il valore è il dizionario dei metadati.
    """
    root_dir = Path("DATA") / storage_id
    if not root_dir.exists():
        raise HTTPException(404, "Storage ID inesistente")

    result: dict = {}

    # 👇 resta il pattern *-METADATA.JSON ma filtriamo gli ONCHAIN
    for meta_path in root_dir.rglob("*-METADATA.JSON"):
        # Salta i file on-chain: …-ONCHAIN-METADATA.JSON
        if meta_path.name.endswith("-ONCHAIN-METADATA.JSON"):
            continue

        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            result[str(meta_path.relative_to(root_dir))] = {"error": "metadata file unreadable"}
            continue

        # rimuove suffisso -METADATA.JSON per ottenere il path del contenuto
        relative_file = (
            meta_path
            .relative_to(root_dir)
            .as_posix()
            .removesuffix("-METADATA.JSON")
        )
        result[relative_file] = meta

    return result

# -----------------------------------------------------------------------------
# Operazioni file system (unchanged)
# -----------------------------------------------------------------------------
def rename_item(storage_id: str, path: str, new_name: str):
    root = Path("DATA") / storage_id
    target = _safe_target(root, path)
    new_path = target.with_name(new_name)
    target.rename(new_path)

    if new_path.is_file():
        meta_old = target.parent / f"{target.name}-METADATA.JSON"
        meta_new = new_path.parent / f"{new_path.name}-METADATA.JSON"
        if meta_old.exists():
            meta_old.rename(meta_new)

        # 🔽🔽🔽  NUOVO: rinomina anche l'on-chain metadata, se presente
        onchain_old = target.parent / f"{target.name}-ONCHAIN-METADATA.JSON"
        onchain_new = new_path.parent / f"{new_path.name}-ONCHAIN-METADATA.JSON"
        if onchain_old.exists():
            onchain_old.rename(onchain_new)
        # 🔼🔼🔼

        if meta_new.exists():
            data = json.loads(meta_new.read_text())
            data["file_name"] = new_path.name
            meta_new.write_text(json.dumps(data, indent=4))


def move_item(storage_id: str, src: str, dst_folder: str):
    root = Path("DATA") / storage_id
    source = _safe_target(root, src)
    destination_dir = _safe_target(root, dst_folder)
    destination_dir.mkdir(parents=True, exist_ok=True)

    new_path = destination_dir / source.name
    shutil.move(str(source), str(new_path))

    if new_path.is_file():
        meta_old = source.parent / f"{source.name}-METADATA.JSON"
        meta_new = new_path.parent / f"{new_path.name}-METADATA.JSON"
        if meta_old.exists():
            shutil.move(str(meta_old), str(meta_new))

        # 🔽🔽🔽  NUOVO: sposta anche l'on-chain metadata, se presente
        onchain_old = source.parent / f"{source.name}-ONCHAIN-METADATA.JSON"
        onchain_new = new_path.parent / f"{new_path.name}-ONCHAIN-METADATA.JSON"
        if onchain_old.exists():
            shutil.move(str(onchain_old), str(onchain_new))
        # 🔼🔼🔼

        if meta_new.exists():
            data = json.loads(meta_new.read_text())
            data["folder_path"] = str(dst_folder)
            data["file_name"] = new_path.name
            meta_new.write_text(json.dumps(data, indent=4))


def delete_item(storage_id: str, path: str, recursive: bool = False):
    root = Path("DATA") / storage_id
    target = _safe_target(root, path)

    if target.is_dir():
        if recursive:
            shutil.rmtree(target)
        else:
            try:
                target.rmdir()
            except OSError:
                raise HTTPException(400, "Cartella non vuota")
    elif target.is_file():
        target.unlink()
        meta = target.parent / f"{target.name}-METADATA.JSON"
        if meta.exists():
            meta.unlink()
        onchain_meta = target.parent / f"{target.name}-ONCHAIN-METADATA.JSON"
        if onchain_meta.exists():
            onchain_meta.unlink()
    else:
        raise HTTPException(404, "Percorso non trovato")


def _zip_directory_to_bytes(dir_path: Path) -> io.BytesIO:
    """
    Crea uno ZIP in-memory con tutto il contenuto di `dir_path`
    (mantiene la struttura interna) e restituisce il buffer pronto
    per essere inviato in streaming.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in dir_path.rglob("*"):
            if item.is_file():
                zf.write(item, item.relative_to(dir_path.parent))
    buffer.seek(0)
    return buffer


# -----------------------------------------------------------------------------
# Refresh metadati dopo rename/move (unchanged)
# -----------------------------------------------------------------------------
def refresh_metadata_paths(storage_id: str) -> None:
    """
    Allinea `folder_path` (e `file_name`) dentro ogni `*-METADATA.JSON`
    al percorso reale su disco, ricorsivamente.
    """
    root = Path("DATA") / storage_id
    if not root.exists():
        return

    for meta_path in root.rglob("*-METADATA.JSON"):
        # ❌ non toccare gli on-chain metadata
        if meta_path.name.endswith("-ONCHAIN-METADATA.JSON"):
            continue

        try:
            data = json.loads(meta_path.read_text())
        except Exception:
            continue

        content_path = meta_path.with_name(meta_path.name.replace("-METADATA.JSON", ""))
        if not content_path.exists():
            continue

        folder_rel = content_path.parent.relative_to(root).as_posix()
        folder_rel = "" if folder_rel == "." else folder_rel

        updated = False
        if data.get("folder_path") != folder_rel:
            data["folder_path"] = folder_rel
            updated = True

        if data.get("file_name") != content_path.name:
            data["file_name"] = content_path.name
            updated = True

        if updated:
            meta_path.write_text(json.dumps(data, indent=4))
