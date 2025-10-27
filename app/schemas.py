from pydantic import BaseModel, Field
from typing import Optional, List, Dict


# =============================================================================
# SCENARIO 1
# =============================================================================
class DocumentToNotarizeScenario1(BaseModel):
    """
    Modello dei dati di input per la notarizzazione di un documento nello Scenario 1.

    **Campi**:
    - **document_base64**: Contenuto del documento in formato Base64.
    - **file_name**: Nome del file (con estensione) con cui salvare il documento.
    - **storage_id**: Identificativo della directory di storage.
    - **metadata**: Dizionario di metadati opzionali (es. informazioni aggiuntive).
      I campi aggiuntivi (document_hash, file_weight, file_type, upload_date) verranno integrati a questo dizionario.
    - **selected_chain**: Lista di blockchain su cui effettuare la validazione (es. ["algo"]).
    """
    document_base64: str = Field(
        ...,
        description="Contenuto del documento in formato Base64."
    )
    file_name: str = Field(
        ...,
        description="Nome del file (con estensione) con cui salvare il documento."
    )
    storage_id: str = Field(
        ...,
        description="Identificativo della directory in cui salvare il documento."
    )
    folder_path: str = Field(
        "",
        description="Percorso relativo dentro lo storage_id (es. 'abc/un altra cartella')"
    )
    metadata: Optional[Dict] = Field(
        None,
        description="Dizionario di metadati opzionali relativi al documento. Verranno aggiunti i campi: document_hash, file_weight, file_type, upload_date."
    )
    selected_chain: List[str] = Field(
        ...,
        description="Lista di blockchain su cui effettuare la validazione. Attualmente è abilitata solo 'algo'."
    )


class QueryNotarizationScenario1(BaseModel):
    """
    Modello dei dati di input per la verifica dello stato di un documento nello Scenario 1.

    **Campi**:
    - **storage_id**: Identificativo della directory in cui è stato salvato il documento.
    - **file_name**: Nome del file (con estensione) del documento.
    - **selected_chain**: Lista di blockchain da validare (es. ["algo"]).
    """
    storage_id: str = Field(
        ...,
        description="Identificativo della directory in cui è stato salvato il documento."
    )
    folder_path: str = Field(
        "",
        description="Percorso relativo dentro lo storage_id (es. 'abc/un altra cartella')"
    )
    file_name: str = Field(
        ...,
        description="Nome del file (con estensione) del documento da ricercare."
    )
    selected_chain: List[str] = Field(
        ...,
        description="Lista di blockchain su cui effettuare la validazione. Attualmente è abilitata solo 'algo'."
    )


# =============================================================================
# SCENARIO 2 (WALLET MULTISIG)
# =============================================================================
class DocumentToNotarizeScenario2(BaseModel):
    """
    Modello dei dati di input per la notarizzazione di un documento nello Scenario 2 (wallet multisig).

    **Campi**:
    - **document_base64**: Contenuto del documento in formato Base64.
    - **file_name**: Nome del file (con estensione).
    - **storage_id**: Identificativo della directory di storage.
    - **metadata**: Dizionario di metadati opzionali. Verranno integrati i campi aggiuntivi.
    - **selected_chain**: Lista di blockchain (es. ["algo"]).
    - **public_addresses**: Lista di indirizzi pubblici partecipanti al multisig.
    - **complete_multisig**: Dati completi del multisig (placeholder).
    - **partially_signed_tx**: Transazione parzialmente firmata (in formato JSON).
    """
    document_base64: str = Field(
        ...,
        description="Contenuto del documento in formato Base64."
    )
    file_name: str = Field(
        ...,
        description="Nome del file (con estensione) con cui salvare il documento."
    )
    storage_id: str = Field(
        ...,
        description="Identificativo della directory in cui salvare il documento."
    )
    metadata: Optional[Dict] = Field(
        None,
        description="Dizionario di metadati opzionali. Verranno aggiunti i campi: document_hash, file_weight, file_type, upload_date."
    )
    selected_chain: List[str] = Field(
        ...,
        description="Lista di blockchain su cui effettuare la validazione. Attualmente è abilitata solo 'algo'."
    )
    public_addresses: List[str] = Field(
        ...,
        description="Lista di indirizzi pubblici che partecipano al wallet multisig."
    )
    complete_multisig: str = Field(
        ...,
        description="Dati completi del multisig (placeholder)."
    )
    partially_signed_tx: str = Field(
        ...,
        description="Transazione parzialmente firmata (in formato JSON)."
    )


class QueryNotarizationScenario2(BaseModel):
    """
    Modello dei dati di input per la verifica dello stato di un documento nello Scenario 2.

    **Campi**:
    - **storage_id**: Identificativo della directory in cui è stato salvato il documento.
    - **file_name**: Nome del file del documento.
    - **selected_chain**: Lista di blockchain (es. ["algo"]).
    """
    storage_id: str = Field(
        ...,
        description="Identificativo della directory in cui è stato salvato il documento."
    )
    file_name: str = Field(
        ...,
        description="Nome del file (con estensione) del documento da ricercare."
    )
    selected_chain: List[str] = Field(
        ...,
        description="Lista di blockchain su cui effettuare la validazione. Attualmente è abilitata solo 'algo'."
    )


# =============================================================================
# SCENARIO 3 (TRANSAZIONI FIRMANDE DA INDIRIZZI ESTERNI)
# =============================================================================
class DocumentToNotarizeScenario3(BaseModel):
    """
    Modello dei dati di input per la notarizzazione di un documento nello Scenario 3,
    in cui il wallet aziendale riceve transazioni firmate da indirizzi esterni.

    **Campi**:
    - **document_base64**: Contenuto del documento in formato Base64.
    - **file_name**: Nome del file (con estensione).
    - **storage_id**: Identificativo della directory in cui salvare il documento.
    - **metadata**: Dizionario di metadati opzionali. Verranno integrati i campi aggiuntivi.
    - **selected_chain**: Lista di blockchain (es. ["algo"]).
    - **user_public_address**: Indirizzo pubblico dell'utente che invia la transazione firmata.
    - **signed_tx_json**: Transazione firmata in formato JSON.
    """
    document_base64: str = Field(
        ...,
        description="Contenuto del documento in formato Base64."
    )
    file_name: str = Field(
        ...,
        description="Nome del file (con estensione) con cui salvare il documento."
    )
    storage_id: str = Field(
        ...,
        description="Identificativo della directory in cui salvare il documento."
    )
    metadata: Optional[Dict] = Field(
        None,
        description="Dizionario di metadati opzionali. Verranno aggiunti i campi: document_hash, file_weight, file_type, upload_date."
    )
    selected_chain: List[str] = Field(
        ...,
        description="Lista di blockchain su cui effettuare la validazione. Attualmente è abilitata solo 'algo'."
    )
    user_public_address: str = Field(
        ...,
        description="Indirizzo pubblico dell'utente che invia la transazione firmata."
    )
    signed_tx_json: str = Field(
        ...,
        description="Transazione firmata in formato JSON."
    )


class QueryNotarizationScenario3(BaseModel):
    """
    Modello dei dati di input per la verifica dello stato di un documento nello Scenario 3.

    **Campi**:
    - **storage_id**: Identificativo della directory in cui è stato salvato il documento.
    - **file_name**: Nome del file del documento.
    - **selected_chain**: Lista di blockchain (es. ["algo"]).
    """
    storage_id: str = Field(
        ...,
        description="Identificativo della directory in cui è stato salvato il documento."
    )
    file_name: str = Field(
        ...,
        description="Nome del file (con estensione) del documento da ricercare."
    )
    selected_chain: List[str] = Field(
        ...,
        description="Lista di blockchain su cui effettuare la validazione. Attualmente è abilitata solo 'algo'."
    )


# =============================================================================
# MODELLO DI RISPOSTA COMUNE
# =============================================================================
class NotarizationResponse(BaseModel):
    """
    Modello di risposta per le operazioni di notarizzazione e le query.

    **Campi**:
    - **success**: Booleano che indica se l'operazione è andata a buon fine.
    - **on_chain_validations**: Lista di validazioni on-chain (inizialmente vuota).
    - **file_weight**: Peso del file (in byte). (Presente solo nelle risposte di notarizzazione.)
    - **file_type**: Tipo del file (estensione). (Presente solo nelle risposte di notarizzazione.)
    - **upload_date**: Data e ora di caricamento (ISO 8601). (Presente solo nelle risposte di notarizzazione.)
    - **message**: Messaggio descrittivo dell'esito della richiesta.
    """
    success: bool = Field(
        ...,
        description="Indica se l'operazione ha avuto successo."
    )
    on_chain_validations: List[dict] = Field(
        default_factory=[],
        description="Lista di validazioni on-chain eseguite (inizialmente vuota)."
    )
    file_weight: Optional[int] = Field(
        None,
        description="Peso del file in byte."
    )
    file_type: Optional[str] = Field(
        None,
        description="Tipo del file (estensione)."
    )
    upload_date: Optional[str] = Field(
        None,
        description="Data e ora di caricamento del file in formato ISO 8601."
    )
    message: Optional[str] = Field(
        None,
        description="Messaggio descrittivo dell'esito della richiesta."
    )


# -------------------------------------------------------------------------
#  UTILITY – gestione struttura file-system
# -------------------------------------------------------------------------
from pydantic import BaseModel, Field

class PathInStorage(BaseModel):
    storage_id: str       = Field(..., description="Radice dello storage")
    path:       str       = Field(..., description="Percorso relativo (file o cartella)")

class RenameRequest(PathInStorage):
    new_name: str         = Field(..., description="Nuovo nome (solo basename)")

class MoveRequest(PathInStorage):
    destination: str      = Field(..., description="Destinazione (cartella relativa)")

class DeleteRequest(PathInStorage):
    recursive: bool = Field(
        False,
        description="Se True e path è una cartella, la cancella ricorsivamente"
    )
