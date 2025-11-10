import os
import base64
import json
import requests
from urllib.parse import quote

# Se usi root_path="/notarization-api", includilo qui:
BASE_URL = "http://localhost:8123/notarization-api"

SAVE_DOWNLOADED_COPY = True
DOWNLOAD_DIR = "_downloads"


def _build_rel(folder_path: str, file_name: str) -> str:
    folder_path = (folder_path or "").strip("/")
    return f"{folder_path}/{file_name}" if folder_path else file_name


def _build_std_metadata_url(base_url: str, storage_id: str, folder_path: str, file_name: str) -> str:
    rel = quote(_build_rel(folder_path, file_name), safe="/")
    base = base_url.rstrip("/")
    return f"{base}/storage/{storage_id}/metadata/{rel}"


def _build_onchain_metadata_url(base_url: str, storage_id: str, folder_path: str, file_name: str) -> str:
    rel = quote(_build_rel(folder_path, file_name), safe="/")
    base = base_url.rstrip("/")
    return f"{base}/storage/{storage_id}/metadata-onchain/{rel}"


def _build_file_url(base_url: str, storage_id: str, folder_path: str, file_name: str) -> str:
    rel = quote(_build_rel(folder_path, file_name), safe="/")
    base = base_url.rstrip("/")
    return f"{base}/storage/{storage_id}/download/{rel}"


def test_scenario1_notarize():
    file_path = "sample_6.pdf"
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Il file {file_path} non esiste.")

    with open(file_path, "rb") as f:
        file_bytes = f.read()
    file_base64 = base64.b64encode(file_bytes).decode("utf-8")

    storage_id = "test_storage"
    folder_path = ""  # es. "cartella/sub" se vuoi

    payload = {
        "document_base64": file_base64,
        "file_name": os.path.basename(file_path),
        "storage_id": storage_id,
        "folder_path": folder_path,
        "metadata": {"autore": "Test Author", "descrizione": "Test PDF file"},
        "selected_chain": ["algo"]
    }

    # POST notarize
    url = f"{BASE_URL}/scenario1/notarize"
    response = requests.post(url, json=payload)
    data = response.json()
    print("Risposta notarizzazione Scenario 1:")
    print(json.dumps(data, indent=2))

    assert response.status_code == 200
    assert data.get("success") is True

    # Costruzione URL
    file_name = os.path.basename(file_path)
    std_meta_url = _build_std_metadata_url(BASE_URL, storage_id, folder_path, file_name)
    onchain_meta_url = _build_onchain_metadata_url(BASE_URL, storage_id, folder_path, file_name)
    file_url = _build_file_url(BASE_URL, storage_id, folder_path, file_name)

    print("\nURL metadati STANDARD:", std_meta_url)
    print("URL metadati ON-CHAIN:", onchain_meta_url)
    print("URL FILE:", file_url)

    # GET metadati standard
    try:
        r1 = requests.get(std_meta_url)
        print("\n[STD-META] HTTP", r1.status_code)
        if r1.ok:
            print(json.dumps(r1.json(), indent=2))
    except Exception as e:
        print("Errore std metadata:", e)

    # GET metadati on-chain
    try:
        r2 = requests.get(onchain_meta_url)
        print("\n[ONCHAIN-META] HTTP", r2.status_code)
        if r2.ok:
            print(json.dumps(r2.json(), indent=2))
    except Exception as e:
        print("Errore on-chain metadata:", e)

    # GET file
    try:
        r3 = requests.get(file_url)
        print("\n[FILE] HTTP", r3.status_code)
        if r3.ok:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            out_path = os.path.join(DOWNLOAD_DIR, file_name)
            if SAVE_DOWNLOADED_COPY:
                with open(out_path, "wb") as out:
                    out.write(r3.content)
                print("File salvato in:", out_path)
    except Exception as e:
        print("Errore file download:", e)

    return data


if __name__ == "__main__":
    print("Avvio test Scenario 1 (requests)...")
    test_scenario1_notarize()
    print("Test completato.")
