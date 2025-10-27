import os
import base64
import hashlib
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks

# Import degli schemi aggiornati
from app.schemas import (
    DocumentToNotarizeScenario1, QueryNotarizationScenario1,
    DocumentToNotarizeScenario2, QueryNotarizationScenario2,
    DocumentToNotarizeScenario3, QueryNotarizationScenario3,
    NotarizationResponse
)
from app.utils import simulate_transaction, list_files_with_metadata, _zip_directory_to_bytes, _safe_target, \
    refresh_metadata_paths
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import RenameRequest, MoveRequest, DeleteRequest
from app.utils   import rename_item, move_item, delete_item

from fastapi.responses import FileResponse, StreamingResponse


app = FastAPI(
    title="Document Notarization API",
    description="""
Questa API consente di notarizzare documenti su blockchain secondo tre scenari differenti.
Invece di ricevere l'hash del documento, l'API riceve il file in formato Base64, il nome del file e un identificativo di storage (storage_id). 
Il file verrà salvato nella directory `/DATA/<storage_id>/<file_name>`, da cui verrà calcolato l'hash (SHA-256). 
I metadati, compresi l'hash, il peso del file, il tipo (estensione) e la data di caricamento, 
verranno integrati in un dizionario (il quale, se fornito in input, viene aggiornato) e salvati come file JSON nella stessa directory 
(con nome: `<file_name>-METADATA.JSON`).

È possibile indicare una lista di blockchain sulle quali effettuare le validazioni (in ordine di priorità). 
Attualmente è abilitata solo la blockchain **algo**; se viene richiesta anche una blockchain diversa, 
l'API restituisce un errore di non implementazione.
    """,
    version="1.0.0",
    root_path="/notarization-api"
)

# Configurazione CORS per permettere tutte le origini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permetti tutte le origini
    allow_credentials=True,
    allow_methods=["*"],  # Permetti tutti i metodi (GET, POST, OPTIONS, ecc.)
    allow_headers=["*"],  # Permetti tutti gli headers
)

@app.get("/", tags=["Health Check"])
def root():
    """
    **Health Check**

    Verifica che il servizio sia attivo.

    **Risposta**:
    - `message`: Messaggio di conferma.

    **Esempio di risposta**:
    ```json
    {
      "message": "API di notarizzazione documenti attiva."
    }
    ```
    """
    return {"message": "API di notarizzazione documenti attiva."}


# ----------------------------------------------------------------------------
# FUNZIONE AUSILIARIA: SALVATAGGIO DEL FILE E CREAZIONE DEI METADATI
# ----------------------------------------------------------------------------
from pathlib import Path                                       # NEW ✔

def save_document_and_metadata(
        document_base64: str,
        file_name: str,
        storage_id: str,
        folder_path: str,                                      # NEW ✔
        metadata: Optional[dict]
) -> dict:
    file_bytes = base64.b64decode(document_base64)

    # 1. Costruzione sicura del path  ───────────────────────────────────
    root_dir   = Path("DATA") / storage_id
    target_dir = (root_dir / Path(folder_path)).resolve()      # canonical
    if root_dir.resolve() not in target_dir.parents \
       and root_dir.resolve() != target_dir:                   # traversal guard
        raise HTTPException(400, "Percorso non ammesso")       # :contentReference[oaicite:1]{index=1}

    target_dir.mkdir(parents=True, exist_ok=True)              # :contentReference[oaicite:2]{index=2}

    # 2. Salvataggio file e metadati  ───────────────────────────────────
    file_path = target_dir / file_name
    file_path.write_bytes(file_bytes)

    file_hash   = hashlib.sha256(file_bytes).hexdigest()       # :contentReference[oaicite:3]{index=3}
    file_weight = len(file_bytes)
    file_type   = file_path.suffix.lstrip(".") or "unknown"
    upload_date = datetime.utcnow().isoformat()

    metadata = metadata or {}
    metadata.update({
        "document_hash": file_hash,
        "storage_id":    storage_id,
        "folder_path":   folder_path,                          # NEW ✔
        "file_name":     file_name,
        "file_weight":   file_weight,
        "file_type":     file_type,
        "upload_date":   upload_date,
        "validations":   []
    })

    (target_dir / f"{file_name}-METADATA.JSON").write_text(
        json.dumps(metadata, indent=4)                         # :contentReference[oaicite:4]{index=4}
    )

    return {
        "file_hash":   file_hash,
        "file_weight": file_weight,
        "file_type":   file_type,
        "upload_date": upload_date
    }

def save_document_and_metadata_(document_base64: str, file_name: str, storage_id: str, metadata: Optional[dict]) -> dict:
    """
    Decodifica il documento in Base64, lo salva in `/DATA/<storage_id>/<file_name>`,
    calcola l'hash (SHA-256) del file e integra i metadati forniti in input (se presenti) con le seguenti informazioni:
      - **document_hash**: Hash calcolato (SHA-256).
      - **storage_id**: L'identificativo della directory di storage.
      - **file_name**: Il nome del file.
      - **file_weight**: Il peso del file in byte.
      - **file_type**: L'estensione del file.
      - **upload_date**: La data e ora di caricamento (formato ISO 8601).

    I metadati completi vengono poi salvati in un file JSON denominato `<file_name>-METADATA.JSON` nella stessa directory.

    **Parametri**:
    - **document_base64**: Il documento codificato in Base64.
    - **file_name**: Il nome del file (con estensione) con cui salvare il documento.
    - **storage_id**: L'identificativo della directory di storage.
    - **metadata**: Un dizionario di metadati opzionali (se fornito), che verrà aggiornato con le informazioni aggiuntive.

    **Ritorna**: Un dizionario contenente:
      - `file_hash`: L'hash calcolato (SHA-256).
      - `file_weight`: Il peso del file in byte.
      - `file_type`: L'estensione del file.
      - `upload_date`: La data e ora di caricamento (ISO 8601).
    """
    try:
        file_bytes = base64.b64decode(document_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Il contenuto Base64 non è valido.")

    # Crea la directory di storage se non esiste
    directory = os.path.join("DATA", storage_id)
    os.makedirs(directory, exist_ok=True)

    # Salva il file nella directory specificata
    file_path = os.path.join(directory, file_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Calcola l'hash del file (SHA-256)
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Ottieni il peso del file in byte
    file_weight = len(file_bytes)

    # Estrai l'estensione dal nome del file
    _, ext = os.path.splitext(file_name)
    file_type = ext.lstrip(".") if ext else "unknown"

    # Data e ora di caricamento (ISO 8601)
    upload_date = datetime.now().isoformat()

    # Se il dizionario di metadata non è fornito, inizializza un dizionario vuoto
    if metadata is None:
        metadata = {}
    # In alternativa, se viene fornito, assicurati che sia un dizionario
    elif not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="Il campo 'metadata' deve essere un dizionario.")

    # Aggiunge o aggiorna i campi nel dizionario dei metadata
    metadata["document_hash"] = file_hash
    metadata["storage_id"] = storage_id
    metadata["file_name"] = file_name
    metadata["file_weight"] = file_weight
    metadata["file_type"] = file_type
    metadata["upload_date"] = upload_date
    metadata["validations"] = []

    # Scrive il dizionario dei metadata come file JSON nella stessa directory
    metadata_file_path = os.path.join(directory, f"{file_name}-METADATA.JSON")
    with open(metadata_file_path, "w") as mf:
        json.dump(metadata, mf, indent=4)

    return {
        "file_hash": file_hash,
        "file_weight": file_weight,
        "file_type": file_type,
        "upload_date": upload_date
    }


# ----------------------------------------------------------------------------
# VALIDAZIONE DELLE BLOCKCHAIN RICHIESTE
# ----------------------------------------------------------------------------
def validate_blockchains(selected_chains: list):
    """
    Verifica che tutte le blockchain richieste siano implementate.
    Attualmente è abilitata solo la blockchain "algo" (case insensitive).

    **Parametri**:
    - **selected_chains**: Lista di blockchain (stringhe).

    **Solleva**:
    - HTTPException 400 se viene richiesta una blockchain diversa da "algo".
    """
    for chain in selected_chains:
        if chain.lower() != "algo":
            raise HTTPException(
                status_code=400,
                detail=f"La blockchain '{chain}' non è implementata attualmente. Attualmente è abilitata solo 'algo'."
            )


# ----------------------------------------------------------------------------
# SCENARIO 1: SOLO L'AZIENDA SVILUPPATRICE EFFETTUA TRANSAZIONI
# ----------------------------------------------------------------------------
@app.post("/scenario1/notarize", response_model=NotarizationResponse, tags=["Scenario 1"])
def scenario1_notarize_document(doc: DocumentToNotarizeScenario1, background_tasks: BackgroundTasks):
    """
    **Notarizzazione Scenario 1**

    Notarizza un documento ricevuto in Base64 salvandolo nella directory `/DATA/<storage_id>/<file_name>`.
    Il documento verrà elaborato per calcolare l'hash, il peso, il tipo (estensione) e la data di caricamento.
    Il dizionario di metadata fornito in input (se presente) verrà aggiornato con tali informazioni.
    Inoltre, viene effettuata la validazione delle blockchain richieste: _solo "algo"_ è attualmente abilitata.

    **Parametri di input** (JSON):
    - **document_base64**: Contenuto del documento in formato Base64.
    - **file_name**: Nome del file (con estensione) con cui salvare il documento.
    - **storage_id**: Identificativo della directory di storage.
    - **metadata**: Dizionario di metadati opzionali. Verranno aggiunti i campi: document_hash, file_weight, file_type, upload_date.
    - **selected_chain**: Lista di blockchain (es. `["algo"]`).

    **Risposta**:
    - **success**: `true` se l'operazione è andata a buon fine.
    - **on_chain_validations**: Lista di validazioni on-chain eseguite (inizialmente vuota).
    - **file_weight**: Peso del file (in byte).
    - **file_type**: Estensione del file.
    - **upload_date**: Data e ora di caricamento (ISO 8601).
    - **message**: Messaggio descrittivo contenente l'hash calcolato.

    **Esempio di richiesta**:
    ```json
    {
      "document_base64": "SGVsbG8gV29ybGQh...",
      "file_name": "contratto.pdf",
      "storage_id": "stor001",
      "metadata": {"autore": "Mario Rossi", "descrizione": "Contratto di locazione"},
      "selected_chain": ["algo"]
    }
    ```
    """
    validate_blockchains(doc.selected_chain)

    info = save_document_and_metadata(doc.document_base64,
                                      doc.file_name,
                                      doc.storage_id,
                                      doc.folder_path,     # NEW ✔
                                      doc.metadata)

    # filename con path per il task di simulazione
    background_tasks.add_task(
        simulate_transaction,
        doc.storage_id,
        f"{doc.folder_path}/{doc.file_name}".lstrip("/")
    )                                                         # :contentReference[oaicite:5]{index=5}

    return NotarizationResponse(
        success=True,
        on_chain_validations=[],
        file_weight=info["file_weight"],
        file_type=info["file_type"],
        upload_date=info["upload_date"],
        message=f"Documento '{doc.file_name}' salvato in '{doc.folder_path}' – hash {info['file_hash']}"
    )


@app.post("/scenario1/query", response_model=dict, tags=["Scenario 1"])
def scenario1_query_document_status(query: QueryNotarizationScenario1):
    """
    **Query Scenario 1**

    Verifica lo stato di notarizzazione di un documento recuperando il file dei metadati da
    `/DATA/<storage_id>/<file_name>-METADATA.JSON`. Viene inoltre eseguita la validazione delle blockchain richieste.

    **Parametri di input** (JSON):
    - **storage_id**: Identificativo della directory in cui è stato salvato il documento.
    - **file_name**: Nome del file del documento.
    - **selected_chain**: Lista di blockchain (es. `["algo"]`).

    **Risposta**:
    Restituisce un dizionario contenente tutti i metadati effettivi del documento, come ad esempio:
      - `document_hash`: L'hash calcolato (SHA-256) del file.
      - `storage_id`: L'identificativo della directory di storage.
      - `file_name`: Il nome del file.
      - `file_weight`: Il peso del file in byte.
      - `file_type`: L'estensione del file.
      - `upload_date`: La data e ora di caricamento in formato ISO 8601.
      - `validations`:
      - eventuali altri metadati forniti in input.

    **Esempio di richiesta**:
    ```json
    {
      "storage_id": "stor001",
      "file_name": "contratto.pdf",
      "selected_chain": ["algo"]
    }
    ```
    """
    validate_blockchains(query.selected_chain)

    root_dir   = Path("DATA") / query.storage_id
    target_dir = (root_dir / Path(query.folder_path)).resolve()
    if root_dir.resolve() not in target_dir.parents \
       and root_dir.resolve() != target_dir:
        raise HTTPException(400, "Percorso non ammesso")       # :contentReference[oaicite:6]{index=6}

    meta_path = target_dir / f"{query.file_name}-METADATA.JSON"
    if not meta_path.exists():
        raise HTTPException(404, "Metadati non trovati")

    return json.loads(meta_path.read_text())

# ----------------------------------------------------------------------------
# STORAGE BROWSER ENDPOINT
# ----------------------------------------------------------------------------
@app.get(
    "/storage/{storage_id}/list",
    response_model=dict,
    tags=["Utility"]
)
def storage_list_all(storage_id: str):
    """
    Ritorna l'elenco completo dei file presenti nello *storage_id* con i
    relativi metadati.

    **Output** esempio
    ```json
    {
      "cartellaX/fileA.pdf": { "...": "..." },
      "fileB.png":           { "...": "..." }
    }
    ```
    """
    return list_files_with_metadata(storage_id)


# ---------------------------------------------------------------------
#  RINOMINA
# ---------------------------------------------------------------------
@app.post("/storage/rename", tags=["Utility"])
def storage_rename(req: RenameRequest):
    """
    Rinomina un file o una cartella all’interno dello *storage* indicato.
    """
    rename_item(req.storage_id, req.path, req.new_name)
    refresh_metadata_paths(req.storage_id)
    return {"ok": True, "message": f"Rinominato in {req.new_name}"}

# ---------------------------------------------------------------------
#  SPOSTA
# ---------------------------------------------------------------------
@app.post("/storage/move", tags=["Utility"])
def storage_move(req: MoveRequest):
    """
    Sposta un file o una cartella in un’altra cartella dello stesso *storage*.
    """
    move_item(req.storage_id, req.path, req.destination)
    refresh_metadata_paths(req.storage_id)
    return {"ok": True, "message": f"Spostato in {req.destination}"}

# ---------------------------------------------------------------------
#  ELIMINA
# ---------------------------------------------------------------------
@app.post("/storage/delete", tags=["Utility"])
def storage_delete(req: DeleteRequest):
    """
    Elimina file o cartella.
    Se `recursive=true` e il path è una cartella, la elimina con tutto il contenuto.
    """
    delete_item(req.storage_id, req.path, req.recursive)
    return {"ok": True, "message": "Eliminazione completata"}



# ----------------------------------------------------------------------------
# SCENARIO 2: WALLET MULTISIG ASSOCIATO ALL'INDIRIZZO AZIENDALE
# ----------------------------------------------------------------------------
@app.post("/scenario2/notarize", response_model=NotarizationResponse, tags=["Scenario 2"])
def scenario2_notarize_document(doc: DocumentToNotarizeScenario2):
    """
    **Notarizzazione Scenario 2 (Wallet Multisig)**

    Notarizza un documento ricevuto in Base64. Il file viene salvato in `/DATA/<storage_id>/<file_name>`
    e verranno calcolati l'hash, il peso, il tipo (estensione) e la data di caricamento.
    Il dizionario di metadata fornito (se presente) verrà aggiornato con tali informazioni.
    Inoltre, vengono richieste le informazioni per la gestione del wallet multisig.
    La validazione delle blockchain viene eseguita: _solo "algo"_ è attualmente abilitata.

    **Parametri di input** (JSON):
    - **document_base64**: Contenuto del documento in formato Base64.
    - **file_name**: Nome del file (con estensione).
    - **storage_id**: Identificativo della directory di storage.
    - **metadata**: Dizionario di metadati opzionali. Verranno aggiunti i campi: document_hash, file_weight, file_type, upload_date.
    - **selected_chain**: Lista di blockchain (es. `["algo"]`).
    - **public_addresses**: Lista di indirizzi pubblici per il multisig.
    - **complete_multisig**: Dati completi del multisig (placeholder).
    - **partially_signed_tx**: Transazione parzialmente firmata (in formato JSON).

    **Risposta**:
    - **success**: `true` se l'operazione è andata a buon fine.
    - **on_chain_validations**: Lista di validazioni on-chain eseguite (inizialmente vuota).
    - **file_weight**: Peso del file (in byte).
    - **file_type**: Estensione del file.
    - **upload_date**: Data e ora di caricamento (ISO 8601).
    - **message**: Messaggio contenente l'hash calcolato.

    **Esempio di richiesta**:
    ```json
    {
      "document_base64": "U29tZSBCYXNlNjQgZGF0YQ==",
      "file_name": "documento.pdf",
      "storage_id": "stor002",
      "metadata": {"categoria": "riservato"},
      "selected_chain": ["algo"],
      "public_addresses": ["addr1", "addr2"],
      "complete_multisig": "DettagliCompletiMultisig",
      "partially_signed_tx": "{...JSON PARTIAL SIGNED...}"
    }
    ```
    """
    validate_blockchains(doc.selected_chain)

    file_info = save_document_and_metadata(
        document_base64=doc.document_base64,
        file_name=doc.file_name,
        storage_id=doc.storage_id,
        metadata=doc.metadata
    )

    return NotarizationResponse(
        success=True,
        on_chain_validations=[],
        file_weight=file_info["file_weight"],
        file_type=file_info["file_type"],
        upload_date=file_info["upload_date"],
        message=(
            f"Documento '{doc.file_name}' notarizzato con successo in Scenario 2 (wallet multisig) sulla blockchain 'algo'. "
            f"Hash calcolato: {file_info['file_hash']}"
        )
    )


@app.post("/scenario2/query", response_model=dict, tags=["Scenario 2"])
def scenario2_query_document_status(query: QueryNotarizationScenario2):
    """
    **Query Scenario 2**

    Recupera tutti i metadati di notarizzazione di un documento gestito tramite multisig.
    L'endpoint legge il file dei metadati salvato in `/DATA/<storage_id>/<file_name>-METADATA.JSON`
    e restituisce l'intero dizionario dei metadati. Viene inoltre eseguita la validazione delle blockchain richieste,
    attualmente abilitata solo per "algo".

    **Parametri di input** (JSON):
    - **storage_id**: Identificativo della directory in cui è stato salvato il documento.
    - **file_name**: Nome del file (con estensione) del documento da ricercare.
    - **selected_chain**: Lista di blockchain da validare (es. `["algo"]`).

    **Risposta**:
    Restituisce un dizionario contenente tutti i metadati salvati nel file, che possono includere i seguenti campi:
      - `document_hash`: L'hash calcolato (SHA-256) del file.
      - `storage_id`: L'identificativo della directory di storage.
      - `file_name`: Il nome del file.
      - `file_weight`: Il peso del file in byte.
      - `file_type`: L'estensione del file.
      - `upload_date`: La data e ora di caricamento in formato ISO 8601.
      - `validations`:
      - Eventuali altri metadati eventualmente forniti in input.

    **Esempio di richiesta**:
    ```json
    {
      "storage_id": "stor002",
      "file_name": "documento.pdf",
      "selected_chain": ["algo"]
    }
    ```
    """
    # Verifica che la blockchain richiesta sia implementata (solo "algo" è abilitato)
    validate_blockchains(query.selected_chain)

    # Costruisce il percorso del file dei metadati
    directory = os.path.join("DATA", query.storage_id)
    metadata_file_path = os.path.join(directory, f"{query.file_name}-METADATA.JSON")

    # Se il file dei metadati non esiste, restituisce un errore 404
    if not os.path.exists(metadata_file_path):
        raise HTTPException(status_code=404, detail="Metadati non trovati per il documento specificato.")

    # Legge e carica il file dei metadati in un dizionario
    with open(metadata_file_path, "r") as mf:
        metadata_dict = json.load(mf)

    # Restituisce il dizionario completo dei metadati
    return metadata_dict


# ----------------------------------------------------------------------------
# SCENARIO 3: TRANSAZIONI FIRMANDE DA INDIRIZZI ESTERNI
# ----------------------------------------------------------------------------
@app.post("/scenario3/notarize", response_model=NotarizationResponse, tags=["Scenario 3"])
def scenario3_notarize_document(doc: DocumentToNotarizeScenario3):
    """
    **Notarizzazione Scenario 3 (Transazione firmata esternamente)**

    Notarizza un documento ricevuto in Base64 inviato con transazione firmata dall'utente.
    Il file viene salvato in `/DATA/<storage_id>/<file_name>` e verranno calcolati l'hash, il peso, il tipo (estensione) e la data di caricamento.
    Il dizionario di metadata fornito (se presente) verrà aggiornato con tali informazioni.
    Viene eseguita la validazione delle blockchain richieste: _solo "algo"_ è abilitata.

    **Parametri di input** (JSON):
    - **document_base64**: Contenuto del documento in formato Base64.
    - **file_name**: Nome del file (con estensione).
    - **storage_id**: Identificativo della directory di storage.
    - **metadata**: Dizionario di metadati opzionali. Verranno aggiunti i campi: document_hash, file_weight, file_type, upload_date.
    - **selected_chain**: Lista di blockchain (es. `["algo"]`).
    - **user_public_address**: Indirizzo pubblico dell'utente.
    - **signed_tx_json**: Transazione firmata in formato JSON.

    **Risposta**:
    - **success**: `true` se l'operazione è andata a buon fine.
    - **on_chain_validations**: Lista di validazioni on-chain eseguite (inizialmente vuota).
    - **file_weight**: Peso del file (in byte).
    - **file_type**: Estensione del file.
    - **upload_date**: Data e ora di caricamento (ISO 8601).
    - **message**: Messaggio contenente l'hash calcolato.

    **Esempio di richiesta**:
    ```json
    {
      "document_base64": "QW5vdGhlciBEYXRh",
      "file_name": "memo.txt",
      "storage_id": "stor003",
      "metadata": {"categoria": "memo", "priorita": "alta"},
      "selected_chain": ["algo"],
      "user_public_address": "userAddr123",
      "signed_tx_json": "{...JSON FULLY SIGNED...}"
    }
    ```
    """
    validate_blockchains(doc.selected_chain)

    file_info = save_document_and_metadata(
        document_base64=doc.document_base64,
        file_name=doc.file_name,
        storage_id=doc.storage_id,
        metadata=doc.metadata
    )

    return NotarizationResponse(
        success=True,
        on_chain_validations=[],
        file_weight=file_info["file_weight"],
        file_type=file_info["file_type"],
        upload_date=file_info["upload_date"],
        message=(
            f"Documento '{doc.file_name}' notarizzato con successo in Scenario 3 (transazione firmata esternamente) "
            f"sulla blockchain 'algo'. Hash calcolato: {file_info['file_hash']}"
        )
    )


@app.post("/scenario3/query", response_model=dict, tags=["Scenario 3"])
def scenario3_query_document_status(query: QueryNotarizationScenario3):
    """
    **Query Scenario 3**

    Recupera tutti i metadati di notarizzazione di un documento per il quale è stata inviata una transazione firmata esternamente.
    L'endpoint legge il file dei metadati salvato in `/DATA/<storage_id>/<file_name>-METADATA.JSON` e restituisce
    l'intero dizionario dei metadati, senza alcun campo "message". Viene inoltre eseguita la validazione delle blockchain richieste,
    attualmente abilitata solo per "algo".

    **Parametri di input** (JSON):
    - **storage_id**: Identificativo della directory in cui è stato salvato il documento.
    - **file_name**: Nome del file (con estensione) del documento da ricercare.
    - **selected_chain**: Lista di blockchain da validare (es. `["algo"]`).

    **Risposta**:
    Restituisce un dizionario contenente tutti i metadati salvati nel file, che possono includere i seguenti campi:
      - `document_hash`: L'hash calcolato (SHA-256) del file.
      - `storage_id`: L'identificativo della directory di storage.
      - `file_name`: Il nome del file.
      - `file_weight`: Il peso del file in byte.
      - `file_type`: L'estensione del file.
      - `upload_date`: La data e ora di caricamento in formato ISO 8601.
      - `validations`:
      - Eventuali altri metadati eventualmente forniti in input.

    **Esempio di richiesta**:
    ```json
    {
      "storage_id": "stor003",
      "file_name": "memo.txt",
      "selected_chain": ["algo"]
    }
    ```
    """
    # Verifica che la blockchain richiesta sia implementata (solo "algo" è abilitato)
    validate_blockchains(query.selected_chain)

    # Costruisce il percorso del file dei metadati
    directory = os.path.join("DATA", query.storage_id)
    metadata_file_path = os.path.join(directory, f"{query.file_name}-METADATA.JSON")

    # Se il file dei metadati non esiste, restituisce un errore 404
    if not os.path.exists(metadata_file_path):
        raise HTTPException(status_code=404, detail="Metadati non trovati per il documento specificato.")

    # Legge e carica il file dei metadati in un dizionario
    with open(metadata_file_path, "r") as mf:
        metadata_dict = json.load(mf)

    # Restituisce il dizionario completo dei metadati
    return metadata_dict

@app.get("/storage/{storage_id}/download/{relative_path:path}",
            summary="Download di file o cartelle (ZIP)", tags=["utility"])
def download_item(storage_id: str, relative_path: str):
    """
    Restituisce:
    • FileResponse se `relative_path` è un file normale
    • StreamingResponse (zip) se è una cartella
    • 404 se il percorso non esiste
    """
    root = Path("DATA") / storage_id
    target = _safe_target(root, relative_path)

    if target.is_file():
        # invia il file così com’è
        return FileResponse(
            target,
            filename=target.name,
            media_type="application/octet-stream"
        )

    if target.is_dir():
        # zip in-memory e stream
        zip_buffer = _zip_directory_to_bytes(target)
        zip_name = f"{target.name}.zip"
        headers = {"Content-Disposition": f'attachment; filename="{zip_name}"'}
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers=headers
        )

    # se non è né file né cartella
    raise HTTPException(status_code=404, detail="Percorso non trovato")



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8077)