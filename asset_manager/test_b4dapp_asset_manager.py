# -*- coding: utf-8 -*-
"""
test_b4dapp_asset_manager.py
----------------------------
Esempio d'uso di B4AssetManager:
  - bootstrap automatico (login, dapp se mancante, wallet se mancante, salvataggio config)
  - funding automatico del wallet alla soglia minima
  - creazione asset (ruoli = self per evitare 400)
  - visualizzazione asset per id
  - ricerca asset per creator

Assicurati che l'API sia raggiungibile.
"""
import pprint
from asset_manager.b4dapp_asset_manager import B4AssetManager, ApiError

pp = pprint.PrettyPrinter(indent=2, width=120, compact=False)

# Endpoint del tuo server FastAPI
BASE_URL = "http://65.21.178.127:8080"
EMAIL = "luca@luca.com"
PASSWORD = "luca"

CONFIG_PATH = "b4dapp_config.json"  # verrà creato/aggiornato automaticamente

# Soglie di funding (microAlgo)
MIN_BALANCE = 5_000_000      # saldo minimo desiderato (5 ALGO)
TOPUP_AMOUNT = 10_000_000    # importo per singola ricarica dispenser (10 ALGO)

def head(title: str):
    print("\n" + "="*120)
    print(title)
    print("="*120)

def extract_asset_id(obj: dict) -> int:
    # Estrazione robusta dell'asset id da varie forme di risposta
    for k in ("asset-index", "asset_id"):
        if k in obj:
            return int(obj[k])
    if "asset" in obj and isinstance(obj["asset"], dict) and "index" in obj["asset"]:
        return int(obj["asset"]["index"])
    raise RuntimeError(f"Impossibile ricavare l'asset id dalla risposta: {obj}")

def main():
    try:
        head("BOOTSTRAP MANAGER + FUNDING AUTOMATICO")
        mgr = B4AssetManager(
            base_url=BASE_URL,
            email=EMAIL,
            password=PASSWORD,
            config_path=CONFIG_PATH,
            # opzionali: se li ometti, verranno creati e salvati automaticamente
            app_name=None,
            wallet_label=None,
            blockchain="ALGO",         # coerente con gli endpoint Algorand
            hsm_id="hsm_test_0",
            algod_id="algod_client_test_0",
            indexer_id="indexer_client_test_0",
            # funding params per bootstrap
            min_balance=MIN_BALANCE,
            topup_amount=TOPUP_AMOUNT,
        )
        print("CONFIG CORRENTE:")
        pp.pprint(mgr.show_config())

        head("CHECK SALDO E (SE NECESSARIO) FUNDING AGGIUNTIVO")
        final_balance = mgr.ensure_funded(MIN_BALANCE, TOPUP_AMOUNT)
        print(f"Saldo finale (microAlgo): {final_balance}")

        head("CREAZIONE ASSET (NFT 1/1) — roles_mode='self' + funding pre-txn")
        create_res = mgr.create_asset(
            unit_name="nft_unit",
            asset_name="MyNFT",
            total=1,
            decimals=0,
            default_frozen=False,
            note="asset creato da B4AssetManager (roles=self)",
            metadata_url="https://example.com/meta.json",
            metadata="{}",
            roles_mode="self",  # <-- tutti i ruoli = wallet creatore (niente 400)
            ensure_min_balance=MIN_BALANCE,
            ensure_topup_amount=TOPUP_AMOUNT,
        )
        pp.pprint(create_res)

        asset_id = extract_asset_id(create_res)
        print(f">>> ASSET_ID creato: {asset_id}")

        head("VISUALIZZA ASSET PER ID (INDEXER)")
        view_res = mgr.view_asset(asset_id)
        pp.pprint(view_res)

        head("CERCA ASSET PER CREATOR (INDEXER)")
        search_res = mgr.search_assets()  # per default creator = wallet corrente
        pp.pprint(search_res)

        head("FINE ✅")

    except ApiError as e:
        print(f"[ApiError] {e}")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    main()
