# -*- coding: utf-8 -*-
"""
Test dettagliato dell'SDK B4DApp.

Esegue un flusso end-to-end simile al tuo script di test:
- login
- get_user_info
- create_dapp
- get_dapp_keys
- jwt_generation
- address_generation (5 wallet)
- get_addresses_by_jwt
- import_public_key, sign & verify
- algos_dispenser (finanzia i 5 wallet)
- payment_txn (address_1 -> address_0)
- asset_create_txn (NFT 1/1 intestato ad address_0)
- blockchain_info(asset) e search_on_blockchain(assets by creator)

Nota: Assicura che l'API FastAPI sia in esecuzione su http://127.0.0.1:8080
"""

import pprint
import random
from sdk.b4dapp_sdk import B4DAppClient, ApiError

pp = pprint.PrettyPrinter(indent=2, width=120, compact=False)

BASE_URL = "http://65.21.178.127:8080"
EMAIL = "luca@luca.com"
PASSWORD = "luca"

HSM_ID = "hsm_test_0"
ALGOD_ID = "algod_client_test_0"
INDEXER_ID = "indexer_client_test_0"

DISPENSE_AMOUNT = 1_000_000
PAYMENT_FUNDING = 500_000

def head(title: str):
    print("\n" + "="*120)
    print(title)
    print("="*120)

def main():
    client = B4DAppClient(BASE_URL, hsm_id=HSM_ID, algod_id=ALGOD_ID, indexer_id=INDEXER_ID)

    try:
        # 1) login
        head("1) LOGIN")
        res = client.login(EMAIL, PASSWORD)
        pp.pprint(res)

        # 2) user info
        head("2) GET USER INFO")
        res = client.get_user_info()
        pp.pprint(res)

        # 3) create dapp
        head("3) CREATE DAPP")
        app_name = f"dapp_{random.randint(100000000,999999999)}"
        res = client.create_dapp(app_name, "ETHEREUM")
        pp.pprint(res)

        # 4) dapp keys
        head("4) GET DAPP KEYS")
        res = client.get_dapp_keys(EMAIL, PASSWORD, app_name_values=[app_name])
        pp.pprint(res)
        keys = res["keys"]
        dapp_id = keys[0]["app_info"]["dapp_id"]
        secret_key = keys[0]["secret_key"]

        # 5) jwt
        head("5) JWT GENERATION")
        res = client.jwt_generation(app_name, dapp_id, secret_key, "ETHEREUM")
        pp.pprint(res)

        # 6) address generation x5
        head("6) ADDRESS GENERATION (x5)")
        labels = []
        for i in range(5):
            label = f"address_{random.randint(100000000,999999999)}"
            res = client.algo_address_generation(label)
            pp.pprint(res)
            labels.append(label)

        # 7) list addresses
        head("7) GET ADDRESSES BY JWT")
        res = client.get_addresses_by_jwt()
        pp.pprint(res)
        addresses_rows = res["addresses"]
        assert len(addresses_rows) >= 5, "Mi aspetto almeno 5 address"
        def pick(i):
            address = addresses_rows[i]["address"]
            label_plain = addresses_rows[i]["label"].split("-")[-1]
            return address, label_plain
        address_0, label_0 = pick(0)
        address_1, label_1 = pick(1)
        address_2, label_2 = pick(2)
        address_3, label_3 = pick(3)
        address_4, label_4 = pick(4)

        # 8) import public key + sign + verify
        head("8) IMPORT PUBLIC KEY + SIGN & VERIFY")
        res = client.algo_import_public_key(address_0)
        print("import_public_key:")
        pp.pprint(res)

        msg_b64 = client.b64encode_message("Hello World!")
        res = client.algo_sign(label_0, msg_b64)
        print("sign:")
        pp.pprint(res)
        sig = res["signature"]
        res = client.algo_verify(address_0, msg_b64, sig)
        print("verify:")
        pp.pprint(res)

        # 9) fund wallets
        head("9) FUND WALLETS (DISPENSER)")
        for i, a in enumerate([address_0, address_1, address_2, address_3, address_4]):
            res = client.algo_algos_dispenser(a, DISPENSE_AMOUNT)
            print(f"dispenser to [{i}] {a}:")
            pp.pprint(res)

        # 10) payment
        head("10) PAYMENT TXN (address_1 -> address_0)")
        res = client.payment_txn(address_0, PAYMENT_FUNDING, note="payment transaction test", sender_address=address_1, label=label_1)
        pp.pprint(res)

        # 11) create asset
        head("11) ASSET CREATE TXN (NFT 1/1)")
        res = client.asset_create_txn(
            sender_address=address_0,
            total=1,
            strict_empty_address_check=True,
            default_frozen=False,
            unit_name="nft_0",
            asset_name="NFT",
            manager_address=address_1,
            reserve_address=address_2,
            freeze_address=address_3,
            clawback_address=address_4,
            metadata_url="https://url_to/metadata.json",
            metadata="metadata content",
            decimals=0,
            note="asset create transaction test",
            label=label_0,
        )
        pp.pprint(res)
        # Asset id può essere in 'asset-index' o con altre chiavi; lo cerchiamo in modo robusto
        asset_id = None
        for k in ("asset-index", "asset_id"):
            if k in res:
                asset_id = int(res[k])
                break
        if not asset_id and "asset" in res and isinstance(res["asset"], dict) and "index" in res["asset"]:
            asset_id = int(res["asset"]["index"])
        assert asset_id is not None, f"Impossibile dedurre l'asset id dalla risposta: {res}"
        print(f">>> ASSET ID creato: {asset_id}")

        # 12) lookup asset on-chain
        head("12) LOOKUP ASSET ON-CHAIN (per id)")
        res = client.blockchain_info("asset", {"asset_id": asset_id})
        pp.pprint(res)

        head("13) SEARCH ASSETS ON-CHAIN (per creator)")
        res = client.search_on_blockchain("assets", {"creator": address_0})
        pp.pprint(res)

        head("FINE ✅")

    except ApiError as e:
        print(f"[ApiError] {e}")


if __name__ == "__main__":
    main()
