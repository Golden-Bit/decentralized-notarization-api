Di seguito è fornita una **documentazione dettagliata** dell’API di notarizzazione di documenti su blockchain, completa di descrizione dei **tre scenari**, schemi di input/output, endpoint disponibili, esempi di richieste e risposte. L’API è implementata in **FastAPI** e supporta attualmente soltanto la blockchain **Algorand** (indicata come `"algo"`). In caso di richieste per altre blockchain, viene restituito un errore di non implementazione.

---

## Indice dei Contenuti

1. [Introduzione e Scopi dell’API](#introduzione-e-scopi)
2. [Struttura del Codice e Funzionalità](#struttura-del-codice)
3. [Middleware e CORS](#cors)
4. [Modelli (Schemas)](#modelli-schemas)
5. [Endpoints](#endpoints)
    - [Health Check](#health-check)
    - [Scenario 1](#scenario-1)
        - [/scenario1/notarize (POST)](#scenario1notarize-post)
        - [/scenario1/query (POST)](#scenario1query-post)
    - [Scenario 2](#scenario-2)
        - [/scenario2/notarize (POST)](#scenario2notarize-post)
        - [/scenario2/query (POST)](#scenario2query-post)
    - [Scenario 3](#scenario-3)
        - [/scenario3/notarize (POST)](#scenario3notarize-post)
        - [/scenario3/query (POST)](#scenario3query-post)
6. [Esempi di Indirizzi Algorand](#esempi-di-indirizzi)
7. [Esecuzione e Testing](#esecuzione-e-testing)

---

## 1. Introduzione e Scopi

Questa API espone servizi per **notarizzare documenti su blockchain** tramite tre diversi scenari di interazione:

- **Scenario 1**: Solo l’azienda sviluppatrice effettua transazioni.  
- **Scenario 2**: Wallet multisig associato all’indirizzo aziendale (più indirizzi partecipano).  
- **Scenario 3**: Transazioni firmate esternamente da indirizzi non controllati dall’azienda.

A differenza di soluzioni che richiedono l’hash in ingresso, qui il client **invia il documento in Base64**. L’API:

1. Decodifica il Base64;
2. Salva il file nella directory `/DATA/<storage_id>/<file_name>`;
3. Calcola l’hash (SHA-256) del file;
4. Aggiorna i metadati (incluso l’hash) e li salva in `<file_name>-METADATA.JSON` nella stessa directory.

---

## 2. Struttura del Codice e Funzionalità

- **File Principale (API)**: Espone gli endpoint e coordina la logica di notarizzazione.
- **Schemas (Modelli Pydantic)**: Definiscono i formati di input e output.  
- **Funzioni Ausiliarie**:
  - `save_document_and_metadata(...)`: Decodifica il file, lo salva, calcola l’hash e aggiorna i metadati.
  - `validate_blockchains(...)`: Verifica che tutte le blockchain richieste siano `"algo"`.

### Archiviazione dei Metadati
Dopo aver decodificato il file e calcolato l’hash, i metadati vengono salvati in un file JSON nella stessa directory. Esempio di file JSON (`<file_name>-METADATA.JSON`):

```json
{
  "document_hash": "abc123...def",
  "storage_id": "stor001",
  "file_name": "contratto.pdf",
  "file_weight": 10500,
  "file_type": "pdf",
  "upload_date": "2025-02-12T16:30:00.000Z",
  "validations": [],
  "metadata": "Valore personalizzato se presente"
}
```

---

## 3. Middleware e CORS <a name="cors"></a>

L’API utilizza FastAPI e abilita **CORS** su tutte le origini, metodi e headers:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Questo permette a qualsiasi client (anche front-end web) di invocare gli endpoint senza restrizioni.

---

## 4. Modelli (Schemas) <a name="modelli-schemas"></a>

Il file `app/schemas.py` definisce i modelli Pydantic:

- **DocumentToNotarizeScenario1 / DocumentToNotarizeScenario2 / DocumentToNotarizeScenario3**:  
  Definiscono i campi in input per la chiamata di notarizzazione nei rispettivi scenari.  
  - `document_base64`: stringa in Base64 contenente il file.
  - `file_name`: nome del file con estensione.
  - `storage_id`: directory di storage.
  - `metadata`: dizionario facoltativo con metadati extra.
  - `selected_chain`: lista di blockchain (attualmente solo `"algo"` supportato).
  - (Scenario 2) `public_addresses`, `complete_multisig`, `partially_signed_tx`.
  - (Scenario 3) `user_public_address`, `signed_tx_json`.

- **QueryNotarizationScenario1 / QueryNotarizationScenario2 / QueryNotarizationScenario3**:  
  Definiscono i campi per la chiamata di query, ossia:
  - `storage_id`: directory di storage.
  - `file_name`: nome del file (con estensione).
  - `selected_chain`: lista di blockchain (solo `"algo"`).

- **NotarizationResponse**:  
  Definisce la risposta standard per le notarizzazioni:
  - `success`: indica l’esito dell’operazione (`true` / `false`).
  - `on_chain_validations`: lista di oggetti di validazione (vuota in questa implementazione base).
  - `file_weight`, `file_type`, `upload_date`: informazioni sul file caricato.
  - `message`: messaggio descrittivo.

---

## 5. Endpoints <a name="endpoints"></a>

### Health Check <a name="health-check"></a>

```
GET /
```
- **Descrizione**: Verifica lo stato di attivazione del servizio.
- **Risposta** (JSON):
  ```json
  {
    "message": "API di notarizzazione documenti attiva."
  }
  ```
- **Esempio di Chiamata**:
  ```
  curl http://localhost:8100/
  ```

---

### Scenario 1 <a name="scenario-1"></a>

#### /scenario1/notarize (POST) <a name="scenario1notarize-post"></a>

- **Descrizione**: Riceve un documento in Base64, salva il file e calcola l’hash.  
- **Request Body** (JSON):
  - `document_base64`: string (Base64)
  - `file_name`: string (es. `"contratto.pdf"`)
  - `storage_id`: string (es. `"stor001"`)
  - `metadata`: object (facoltativo)
  - `selected_chain`: array (es. `["algo"]`)
- **Esempio di Richiesta**:
  ```json
  {
    "document_base64": "SGVsbG8gV29ybGQh...",
    "file_name": "contratto.pdf",
    "storage_id": "stor001",
    "metadata": {"autore": "Mario Rossi"},
    "selected_chain": ["algo"]
  }
  ```
- **Risposta** (modello `NotarizationResponse`):
  ```json
  {
    "success": true,
    "on_chain_validations": [],
    "file_weight": 12345,
    "file_type": "pdf",
    "upload_date": "2025-02-12T12:00:00.000Z",
    "message": "Documento 'contratto.pdf' in attesa di validaizoni. Hash calcolato: ABC123..."
  }
  ```
- **Esempio di Chiamata**:
  ```
  POST http://localhost:8100/scenario1/notarize
  Content-Type: application/json
  {
    "document_base64": "SGVsbG8gV29ybGQh...",
    "file_name": "contratto.pdf",
    "storage_id": "stor001",
    "metadata": {"autore": "Mario Rossi"},
    "selected_chain": ["algo"]
  }
  ```

#### /scenario1/query (POST) <a name="scenario1query-post"></a>

- **Descrizione**: Recupera i metadati salvati (incluso l’hash) del documento.  
- **Request Body** (JSON):
  - `storage_id`: string (es. `"stor001"`)
  - `file_name`: string (es. `"contratto.pdf"`)
  - `selected_chain`: array (es. `["algo"]`)
- **Esempio di Richiesta**:
  ```json
  {
    "storage_id": "stor001",
    "file_name": "contratto.pdf",
    "selected_chain": ["algo"]
  }
  ```
- **Risposta** (JSON generico con tutti i campi del file `<file_name>-METADATA.JSON`):
  ```json
  {
    "document_hash": "abc123...",
    "storage_id": "stor001",
    "file_name": "contratto.pdf",
    "file_weight": 12345,
    "file_type": "pdf",
    "upload_date": "2025-02-12T12:00:00.000Z",
    "metadata": {
      "autore": "Mario Rossi"
    },
    "validations": []
  }
  ```
- **Esempio di Chiamata**:
  ```
  POST http://localhost:8100/scenario1/query
  Content-Type: application/json
  {
    "storage_id": "stor001",
    "file_name": "contratto.pdf",
    "selected_chain": ["algo"]
  }
  ```

---

### Scenario 2 <a name="scenario-2"></a>

#### /scenario2/notarize (POST) <a name="scenario2notarize-post"></a>

- **Descrizione**: Riceve un documento e i dati per il **wallet multisig** (lista di indirizzi, transazione parzialmente firmata, ecc.). Salva il file e calcola l’hash.  
- **Request Body** (JSON):
  - `document_base64`: string (Base64)
  - `file_name`: string
  - `storage_id`: string
  - `metadata`: object (facoltativo)
  - `selected_chain`: array (es. `["algo"]`)
  - `public_addresses`: array di string (indirizzi multisig)
  - `complete_multisig`: string (placeholder con dettagli multisig)
  - `partially_signed_tx`: string (json con transazione parzialmente firmata)
- **Esempio di Richiesta**:
  ```json
  {
    "document_base64": "U29tZSBCYXNlNjQgZGF0YQ==",
    "file_name": "documento.pdf",
    "storage_id": "stor002",
    "metadata": {"categoria": "riservato"},
    "selected_chain": ["algo"],
    "public_addresses": [
      "JZYEFRR2PSXVDJ24QTXJBO6PKW3TUNJKPHTK3JHVE5PDS7HTVPINXHADPU",
      "VUV7F7FPRTOO5XJ2RXL2HXWXMD6NB4YCNX5Q36EK3F5H6VLJGMNRQTOLMA"
    ],
    "complete_multisig": "DettagliCompletiMultisig",
    "partially_signed_tx": "{...JSON PARTIAL SIGNED...}"
  }
  ```
- **Risposta** (modello `NotarizationResponse`):
  ```json
  {
    "success": true,
    "on_chain_validations": [],
    "file_weight": 88888,
    "file_type": "pdf",
    "upload_date": "2025-02-12T12:30:00.000Z",
    "message": "Documento 'documento.pdf' notarizzato con successo in Scenario 2 (wallet multisig) sulla blockchain 'algo'. Hash calcolato: ABC123..."
  }
  ```

#### /scenario2/query (POST) <a name="scenario2query-post"></a>

- **Descrizione**: Recupera i metadati di un documento notarizzato con multisig.  
- **Request Body** (JSON):
  - `storage_id`: string
  - `file_name`: string
  - `selected_chain`: array (es. `["algo"]`)
- **Esempio di Richiesta**:
  ```json
  {
    "storage_id": "stor002",
    "file_name": "documento.pdf",
    "selected_chain": ["algo"]
  }
  ```
- **Risposta** (JSON con metadati completi):
  ```json
  {
    "document_hash": "abc123...",
    "storage_id": "stor002",
    "file_name": "documento.pdf",
    "file_weight": 88888,
    "file_type": "pdf",
    "upload_date": "2025-02-12T12:30:00.000Z",
    "metadata": {
      "categoria": "riservato"
    },
    "validations": []
  }
  ```

---

### Scenario 3 <a name="scenario-3"></a>

#### /scenario3/notarize (POST) <a name="scenario3notarize-post"></a>

- **Descrizione**: Riceve un documento firmato **esternamente** (transazione firmata da un utente). Salva il file, calcola l’hash e risponde con esito.  
- **Request Body** (JSON):
  - `document_base64`: string (Base64)
  - `file_name`: string
  - `storage_id`: string
  - `metadata`: object (facoltativo)
  - `selected_chain`: array (es. `["algo"]`)
  - `user_public_address`: string (es. "userAddr123")
  - `signed_tx_json`: string (json con transazione già firmata)
- **Esempio di Richiesta**:
  ```json
  {
    "document_base64": "QW5vdGhlciBEYXRh",
    "file_name": "memo.txt",
    "storage_id": "stor003",
    "metadata": {"categoria": "memo", "priorita": "alta"},
    "selected_chain": ["algo"],
    "user_public_address": "JZYEFRR2PSXVDJ24QTXJBO6PKW3TUNJKPHTK3JHVE5PDS7HTVPINXHADPU",
    "signed_tx_json": "{...JSON FULLY SIGNED...}"
  }
  ```
- **Risposta** (modello `NotarizationResponse`):
  ```json
  {
    "success": true,
    "on_chain_validations": [],
    "file_weight": 1024,
    "file_type": "txt",
    "upload_date": "2025-02-12T13:00:00.000Z",
    "message": "Documento 'memo.txt' notarizzato con successo in Scenario 3 (transazione firmata esternamente) sulla blockchain 'algo'. Hash calcolato: ABC123..."
  }
  ```

#### /scenario3/query (POST) <a name="scenario3query-post"></a>

- **Descrizione**: Recupera i metadati di un documento notarizzato con **transazione firmata esternamente**.  
- **Request Body** (JSON):
  - `storage_id`: string
  - `file_name`: string
  - `selected_chain`: array (es. `["algo"]`)
- **Esempio di Richiesta**:
  ```json
  {
    "storage_id": "stor003",
    "file_name": "memo.txt",
    "selected_chain": ["algo"]
  }
  ```
- **Risposta** (JSON con i metadati):
  ```json
  {
    "document_hash": "abc123...",
    "storage_id": "stor003",
    "file_name": "memo.txt",
    "file_weight": 1024,
    "file_type": "txt",
    "upload_date": "2025-02-12T13:00:00.000Z",
    "metadata": {
      "categoria": "memo",
      "priorita": "alta"
    },
    "validations": []
  }
  ```

---

## 6. Esempi di Indirizzi Algorand <a name="esempi-di-indirizzi"></a>

Nel caso di utilizzo di wallet multisig (Scenario 2) o di user esterno (Scenario 3), potete utilizzare indirizzi Algorand come i seguenti (solo a scopo dimostrativo):

- `JZYEFRR2PSXVDJ24QTXJBO6PKW3TUNJKPHTK3JHVE5PDS7HTVPINXHADPU`
- `VUV7F7FPRTOO5XJ2RXL2HXWXMD6NB4YCNX5Q36EK3F5H6VLJGMNRQTOLMA`

---

## 7. Esecuzione e Testing <a name="esecuzione-e-testing"></a>

### Avvio del Servizio

Assicurarsi di avere **FastAPI** e **Uvicorn** installati. Eseguire:

```
python main.py
```

Oppure:

```
uvicorn main:app --host 127.0.0.1 --port 8100
```

Per impostazione predefinita, l’API ascolterà su `http://127.0.0.1:8100`.

### Testing degli Endpoint

1. **Scenario 1 (notarize)**  
   ```bash
   curl -X POST http://localhost:8100/scenario1/notarize \
   -H "Content-Type: application/json" \
   -d '{
     "document_base64": "SGVsbG8gV29ybGQh...",
     "file_name": "test.pdf",
     "storage_id": "stor001",
     "metadata": {"author": "Test"},
     "selected_chain": ["algo"]
   }'
   ```
2. **Scenario 1 (query)**  
   ```bash
   curl -X POST http://localhost:8100/scenario1/query \
   -H "Content-Type: application/json" \
   -d '{
     "storage_id": "stor001",
     "file_name": "test.pdf",
     "selected_chain": ["algo"]
   }'
   ```

I medesimi endpoint possono essere testati anche attraverso la documentazione interattiva che FastAPI mette a disposizione su `http://localhost:8100/docs` (Swagger UI) o `http://localhost:8100/redoc`.
