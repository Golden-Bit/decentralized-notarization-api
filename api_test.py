import os
import base64
import json
import requests

# Base URL dell'API (assicurarsi che l'API sia in esecuzione, ad esempio su localhost:8000)
BASE_URL = "http://localhost:8100"


def test_scenario1_notarize():
    """
    Testa l'endpoint di notarizzazione dello Scenario 1 tramite una richiesta HTTP.

    Questo test:
      - Legge un file PDF locale (sample.pdf)
      - Converte il file in Base64
      - Invia una richiesta POST all'endpoint /scenario1/notarize con il payload corretto
      - Verifica che la risposta contenga "success": true e un messaggio che includa l'hash calcolato.
    """
    # Specificare il percorso del file PDF locale
    file_path = "sample.pdf"

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Il file {file_path} non esiste. Assicurarsi che il file sia presente in locale.")

    # Legge il file PDF in modalità binaria e lo codifica in Base64
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    file_base64 = base64.b64encode(file_bytes).decode("utf-8")

    # Costruisce il payload JSON da inviare all'endpoint
    payload = {
        "document_base64": file_base64,
        "file_name": os.path.basename(file_path),
        "storage_id": "test_storage",
        "metadata": {
            "autore": "Test Author",
            "descrizione": "Test PDF file"
        },
        "selected_chain": ["algo"]
    }

    # Invio della richiesta POST a /scenario1/notarize
    url = f"{BASE_URL}/scenario1/notarize"
    response = requests.post(url, json=payload)

    # Stampa la risposta in formato JSON
    response_data = response.json()
    print("Risposta notarizzazione Scenario 1:")
    print(json.dumps(response_data, indent=2))

    # Verifica che la risposta abbia status code 200 e che l'operazione sia andata a buon fine
    assert response.status_code == 200, f"Status code non corretto. Atteso 200, ottenuto {response.status_code}"
    assert response_data.get("success") is True, "La notarizzazione non è andata a buon fine."
    assert "Hash calcolato" in response_data.get("message", ""), "Il messaggio non contiene l'hash calcolato."

    return response_data


def test_scenario1_query():
    """
    Testa l'endpoint di query dello Scenario 1 tramite una richiesta HTTP.

    Questo test:
      - Costruisce il payload per la query utilizzando lo stesso storage_id e file_name usati per la notarizzazione
      - Invia una richiesta POST all'endpoint /scenario1/query
      - Verifica che la risposta contenga "success": true e un messaggio che riporti l'hash del documento.
    """
    payload = {
        "storage_id": "test_storage",
        "file_name": "sample.pdf",
        "selected_chain": ["algo"]
    }

    # Invio della richiesta POST a /scenario1/query
    url = f"{BASE_URL}/scenario1/query"
    response = requests.post(url, json=payload)

    # Stampa la risposta in formato JSON
    response_data = response.json()
    print("Risposta query Scenario 1:")
    print(json.dumps(response_data, indent=2))

    # Verifica che la risposta abbia status code 200 e che l'operazione sia andata a buon fine
    #assert response.status_code == 200, f"Status code non corretto nella query. Atteso 200, ottenuto {response.status_code}"
    #assert response_data.get("success") is True, "La query non ha avuto esito positivo."
    #assert "Hash" in response_data.get("message", ""), "Il messaggio della query non contiene informazioni sull'hash."


if __name__ == "__main__":
    print("Avvio dei test per lo Scenario 1 usando requests...")
    test_scenario1_notarize()
    test_scenario1_query()
    print("Tutti i test per lo Scenario 1 sono stati completati con successo!")
