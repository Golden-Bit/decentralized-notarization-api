import json
import random
import time
import string
import os
from datetime import datetime
from pathlib import Path
import io, zipfile              # già aggiunti in precedenza
import json
from fastapi import HTTPException
from pathlib import Path
import shutil, json
from fastapi import HTTPException
import io, zipfile

# Assicurarsi che "datetime" e "json" siano già importati nel file

def simulate_transaction(storage_id: str, file_name: str):
    """
    Funzione di background che simula l'output di una transazione Algorand
    in cui un sender fisso (il proprietario) invia una transazione verso uno smart contract.

    La funzione attende un tempo casuale (tra 5 e 10 secondi), genera un output simulato
    con valori plausibili e lo aggiunge al campo "validations" del file dei metadati.

    **Dettagli della transazione simulata:**
    - **txid**: Un identificativo simulato della transazione.
    - **confirmed_round**: Il round in cui la transazione è stata confermata.
    - **fee**: La commissione in microalgos (valore tipico, es. 1000).
    - **first_valid**: Il round in cui la transazione diventa valida.
    - **last_valid**: Il round in cui la transazione non è più valida.
    - **round_time**: L'orario del round in formato ISO 8601.
    - **sender**: Un valore fisso, rappresentante il proprietario (es. "OWNER_ADDRESS_ABCDEF").
    - **receiver**: Un indirizzo fisso dello smart contract (es. "SMART_CONTRACT_ADDRESS_123456").
    - **note**: Una nota esplicativa della simulazione.

    Dopo il ritardo, la funzione legge il file dei metadati, aggiunge il risultato simulato alla
    chiave "validations" e riscrive il file aggiornato.
    """
    # Attende un tempo casuale tra 5 e 10 secondi
    delay = random.uniform(10, 20)
    time.sleep(delay)

    # Genera un ID transazione simulato
    txid = "SIM_" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    confirmed_round = random.randint(100000, 200000)
    fee = 1000  # valore tipico in microalgos
    first_valid = random.randint(100000, confirmed_round - 100)
    last_valid = confirmed_round + random.randint(100, 1000)
    round_time = datetime.now().isoformat()

    # Fissa il sender (proprietario) e il receiver (smart contract)
    sender = "JZYEFRR2PSXVDJ24QTXJBO6PKW3TUNJKPHTK3JHVE5PDS7HTVPINXHADPU"  # indirizzo fisso del proprietario
    receiver = "VUV7F7FPRTOO5XJ2RXL2HXWXMD6NB4YCNX5Q36EK3F5H6VLJGMNRQTOLMA"  # indirizzo fisso dello smart contract

    simulated_tx = {
        "txid": txid,
        "confirmed_round": confirmed_round,
        "fee": fee,
        "first_valid": first_valid,
        "last_valid": last_valid,
        "round_time": round_time,
        "sender": sender,
        "receiver": receiver,
        "note": "Notarization transaction from owner to smart contract"
    }

    # Percorso del file dei metadati
    directory = os.path.join("DATA", storage_id)
    metadata_file_path = os.path.join(directory, f"{file_name}-METADATA.JSON")

    try:
        with open(metadata_file_path, "r") as mf:
            metadata = json.load(mf)
    except Exception as e:
        # Se non riesce a leggere il file, termina il task
        return

    # Se la chiave "validations" non esiste, inizializzala come lista
    if "validations" not in metadata:
        metadata["validations"] = []

    # Aggiunge la transazione simulata alla lista delle validazioni
    metadata["validations"].append(simulated_tx)

    # Scrive nuovamente il file dei metadati aggiornato
    with open(metadata_file_path, "w") as mf:
        json.dump(metadata, mf, indent=4)


# ----------------------------------------------------------------------------
# ENUMERAZIONE COMPLETA DI UNO STORAGE
# ----------------------------------------------------------------------------
def list_files_with_metadata(storage_id: str) -> dict:
    """
    Scorre ricorsivamente DATA/<storage_id> e raccoglie tutti i file
    metadata (*.METADATA.JSON); la chiave è il percorso relativo del file
    originale (cartella/…/nome.ext), il valore è il dizionario dei metadati.
    """
    root_dir = Path("DATA") / storage_id
    if not root_dir.exists():
        raise HTTPException(404, "Storage ID inesistente")

    result: dict = {}

    # rglob su tutti i METADATA (sicuro perché il root è fisso)
    for meta_path in root_dir.rglob("*-METADATA.JSON"):        # NEW ✔
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            # se un file è corrotto, continua ma lo segnala
            result[str(meta_path.relative_to(root_dir))] = \
                {"error": "metadata file unreadable"}
            continue

        # ricava il percorso del file originale (rimuove il suffisso -METADATA.JSON)
        relative_file = meta_path.relative_to(root_dir)         \
                               .as_posix()                      \
                               .removesuffix("-METADATA.JSON")
        result[relative_file] = meta

    return result


def _safe_target(root: Path, relative: str) -> Path:
    """Costruisce un path canonico ed evita traversal (`..`)."""
    p = (root / Path(relative)).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise HTTPException(400, "Percorso non ammesso")
    return p

def rename_item(storage_id: str, path: str, new_name: str):
    root = Path("DATA") / storage_id
    target = _safe_target(root, path)
    new_path = target.with_name(new_name)
    target.rename(new_path)                                   # pathlib rename :contentReference[oaicite:0]{index=0}

    # se è un file di contenuto, rinomina anche il JSON dei metadati
    if new_path.is_file():
        meta_old = target.parent / f"{target.name}-METADATA.JSON"
        meta_new = new_path.parent / f"{new_path.name}-METADATA.JSON"
        if meta_old.exists():
            meta_old.rename(meta_new)

        # aggiorna `file_name` all’interno del JSON
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
    shutil.move(str(source), str(new_path))                   # shutil.move :contentReference[oaicite:1]{index=1}

    # spostamento file di metadati (se file)
    if new_path.is_file():
        meta_old = source.parent / f"{source.name}-METADATA.JSON"
        meta_new = new_path.parent / f"{new_path.name}-METADATA.JSON"
        if meta_old.exists():
            shutil.move(str(meta_old), str(meta_new))

        # aggiorna `folder_path` nel JSON
        if meta_new.exists():
            data = json.loads(meta_new.read_text())
            data["folder_path"] = str(dst_folder)
            meta_new.write_text(json.dumps(data, indent=4))

def delete_item(storage_id: str, path: str, recursive: bool = False):
    root = Path("DATA") / storage_id
    target = _safe_target(root, path)

    if target.is_dir():
        if recursive:
            shutil.rmtree(target)                             # shutil.rmtree :contentReference[oaicite:2]{index=2}
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
                # scrive il file con il percorso relativo alla cartella radice zippata
                zf.write(item, item.relative_to(dir_path.parent))
    buffer.seek(0)
    return buffer
              # <-- assicurati sia importato

# ────────────────────────────────────────────────────────────────
# NUOVA FUNZIONE: refresh_metadata_paths
# ────────────────────────────────────────────────────────────────

def refresh_metadata_paths(storage_id: str) -> None:
    """
    Scansiona ricorsivamente `DATA/<storage_id>` e allinea il valore
    di `folder_path` (e `file_name`, nel caso di rinomina file) dentro
    *ogni* file `*-METADATA.JSON` al percorso reale sul disco.

    Viene chiamata dopo `rename_item` e `move_item` per garantire
    coerenza dei metadati anche quando si rinomina/sposta una cartella
    contenente molti file.
    """
    root = Path("DATA") / storage_id
    if not root.exists():
        return

    for meta_path in root.rglob("*-METADATA.JSON"):
        try:
            data = json.loads(meta_path.read_text())
        except Exception:
            # file corrotto: lo saltiamo, ma potresti loggare l'evento
            continue

        # Percorso effettivo del file a cui si riferisce il metadata
        content_path = meta_path.with_name(
            meta_path.name.replace("-METADATA.JSON", "")
        )
        if not content_path.exists():
            # il file originale non esiste più → skip
            continue

        # Cartella relativa rispetto a <storage_id>
        folder_rel = content_path.parent.relative_to(root).as_posix()
        folder_rel = "" if folder_rel == "." else folder_rel

        updated = False
        if data.get("folder_path") != folder_rel:
            data["folder_path"] = folder_rel
            updated = True

        # Copertura – se è cambiato anche il nome del file
        if data.get("file_name") != content_path.name:
            data["file_name"] = content_path.name
            updated = True

        if updated:
            meta_path.write_text(json.dumps(data, indent=4))