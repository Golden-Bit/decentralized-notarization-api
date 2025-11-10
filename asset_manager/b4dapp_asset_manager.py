# -*- coding: utf-8 -*-
"""
b4dapp_asset_manager.py
-----------------------
Classe ad alto livello che usa B4DAppClient per:
  - fissare/creare automaticamente DApp e Wallet
  - salvare/leggere configurazione da JSON
  - finanziare automaticamente il wallet (dispenser) se il saldo è insufficiente
  - creare, vedere e cercare asset

Requisiti:
  - b4dapp_sdk.py raggiungibile come 'sdk.b4dapp_sdk'
  - requests installato

Config JSON (esempio):
{
  "base_url": "http://127.0.0.1:8080",
  "email": "luca@luca.com",
  "blockchain": "ALGO",
  "hsm_id": "hsm_test_0",
  "algod_id": "algod_client_test_0",
  "indexer_id": "indexer_client_test_0",
  "app_name": "dapp_123456789",
  "dapp_id": "xxxx-...",
  "secret_key": "xxxx-...",
  "address": "ALGO...",
  "label": "address_123456789",
  "updated_at": "2025-11-08T12:34:56+00:00"
}
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from asset_manager.sdk.b4dapp_sdk import B4DAppClient, ApiError


class B4AssetManager:
    """
    Bootstrap completo:
      - login
      - dapp (crea se assente e salva in config)
      - jwt bearer
      - wallet (crea se assente e salva in config)
      - funding automatico del wallet (dispenser) fino a soglia minima

    Metodi di alto livello:
      - ensure_funded()
      - create_asset()
      - view_asset()
      - search_assets()
      - list_addresses()
    """

    # default soglie in microAlgo
    DEFAULT_MIN_BALANCE = 5_000_000      # saldo minimo desiderato (5 ALGO)
    DEFAULT_TOPUP_AMOUNT = 10_000_000    # ricarica per singolo colpo di dispenser (10 ALGO)

    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        config_path: str = "b4dapp_config.json",
        # opzionali: se non forniti, saranno creati e salvati
        app_name: Optional[str] = None,
        wallet_label: Optional[str] = None,
        blockchain: str = "ALGO",
        hsm_id: str = "hsm_test_0",
        algod_id: str = "algod_client_test_0",
        indexer_id: str = "indexer_client_test_0",
        # funding params
        min_balance: int = DEFAULT_MIN_BALANCE,
        topup_amount: int = DEFAULT_TOPUP_AMOUNT,
    ) -> None:
        self.client = B4DAppClient(
            base_url=base_url, hsm_id=hsm_id, algod_id=algod_id, indexer_id=indexer_id
        )
        self.email = email
        self.password = password
        self.blockchain = blockchain
        self.config_path = config_path

        self.min_balance = int(min_balance)
        self.topup_amount = int(topup_amount)

        # Stato persistente
        self.state: Dict[str, Any] = {}

        # Setup completo
        self._load_config()                 # carica se esiste
        self._ensure_login()                # ottiene session_token
        self._ensure_dapp(app_name)         # crea o usa app esistente
        self._ensure_jwt()                  # ottiene access_token
        self._ensure_wallet(wallet_label)   # crea o usa wallet esistente
        # Finanziamo subito il wallet alla soglia minima
        self.ensure_funded(self.min_balance, self.topup_amount)

    # ------------- Persistenza -------------
    def _load_config(self) -> None:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    self.state = json.load(f)
                except Exception:
                    self.state = {}
        else:
            self.state = {}

    def _save_config(self) -> None:
        # Aggiorna/sincronizza info base
        self.state["base_url"] = self.client.base_url
        self.state["email"] = self.email
        self.state.setdefault("blockchain", self.blockchain)
        self.state.setdefault("hsm_id", getattr(self.client, "hsm_id", None))
        self.state.setdefault("algod_id", getattr(self.client, "algod_id", None))
        self.state.setdefault("indexer_id", getattr(self.client, "indexer_id", None))
        self.state["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    # ------------- Bootstrap: login/dapp/jwt/wallet -------------
    def _ensure_login(self) -> None:
        self.client.login(self.email, self.password)

    def _ensure_dapp(self, app_name_param: Optional[str]) -> None:
        # App in config o parametro?
        app_name = app_name_param or self.state.get("app_name")
        if not app_name:
            app_name = f"dapp_{random.randint(100000000, 999999999)}"
            self.client.create_dapp(app_name, self.blockchain)
            self.state["app_name"] = app_name

        # Recupera chiavi
        keys = self.client.get_dapp_keys(
            self.email, self.password, app_name_values=[app_name]
        ).get("keys", [])
        if not keys:
            # Se non trovata (race condition), crea e riprova
            self.client.create_dapp(app_name, self.blockchain)
            keys = self.client.get_dapp_keys(
                self.email, self.password, app_name_values=[app_name]
            ).get("keys", [])

        if not keys:
            raise ApiError("Impossibile recuperare le chiavi della DApp.")

        key = keys[0]
        self.state["app_name"] = key["app_info"]["app_name"]
        self.state["dapp_id"] = key["app_info"]["dapp_id"]
        self.state["secret_key"] = key["secret_key"]
        self.state["blockchain"] = key["app_info"]["blockchain"] or self.blockchain
        self._save_config()

    def _ensure_jwt(self) -> None:
        res = self.client.jwt_generation(
            self.state["app_name"],
            self.state["dapp_id"],
            self.state["secret_key"],
            self.state.get("blockchain", self.blockchain),
        )
        if "access_token" not in res:
            raise ApiError(f"jwt_generation fallita: {res}")

    def _ensure_wallet(self, wallet_label_param: Optional[str]) -> None:
        address = self.state.get("address")
        label = self.state.get("label")

        if address and label:
            # Verifica che l'indirizzo esista lato server
            rows = self.client.get_addresses_by_jwt().get("addresses", [])
            addrs = [r.get("address") for r in rows]
            if address in addrs:
                return  # wallet OK

        # Genera un nuovo wallet
        label = wallet_label_param or f"address_{random.randint(100000000, 999999999)}"
        res = self.client.algo_address_generation(label)
        # risposta: {'hsm_response': {...'address': ...}, 'db_response': ...}
        hsm_resp = res.get("hsm_response") or {}
        generated_address = hsm_resp.get("address")

        if not generated_address:
            # fallback: prendi l'ultimo dalla lista
            rows = self.client.get_addresses_by_jwt().get("addresses", [])
            if not rows:
                raise ApiError(f"Impossibile dedurre l'indirizzo creato: {res}")
            generated_address = rows[-1]["address"]

        self.state["address"] = generated_address
        self.state["label"] = label
        self._save_config()

    # ------------- Utility saldo/funding -------------
    def _extract_amount_from_account_info(self, acc_info: Dict[str, Any]) -> int:
        """
        Cerca di estrarre il saldo in microAlgo da varie forme di risposta dell'indexer.
        Atteso: {'account': {'amount': <int>, ...}}
        """
        if isinstance(acc_info, dict):
            if "account" in acc_info and isinstance(acc_info["account"], dict):
                amt = acc_info["account"].get("amount")
                if isinstance(amt, int):
                    return amt
            # fallback generici
            for k in ("amount", "balance"):
                if k in acc_info and isinstance(acc_info[k], int):
                    return acc_info[k]
        return 0

    def get_balance(self, address: Optional[str] = None) -> int:
        """Ritorna il saldo (microAlgo) usando l'indexer."""
        addr = address or self.creator_address
        try:
            info = self.client.blockchain_info("account", {"address": addr})
        except ApiError:
            return 0
        return self._extract_amount_from_account_info(info)

    def fund_wallet(self, amount: int, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Tenta di finanziare 'address' tramite dispenser per 'amount' microAlgo.
        Ritorna la risposta raw dell'endpoint.
        """
        addr = address or self.creator_address
        return self.client.algo_algos_dispenser(addr, int(amount))

    def ensure_funded(
        self,
        min_balance: Optional[int] = None,
        topup_amount: Optional[int] = None,
        max_attempts: int = 6,
        sleep_seconds_between_checks: float = 2.0,
    ) -> int:
        """
        Garantisce che il wallet abbia almeno 'min_balance' microAlgo.
        Se il saldo è inferiore, usa il dispenser a colpi di 'topup_amount' con retry.

        Ritorna il saldo finale (microAlgo).
        """
        min_bal = int(min_balance or self.min_balance)
        topup = int(topup_amount or self.topup_amount)

        attempts = 0
        while attempts < max_attempts:
            bal = self.get_balance()
            if bal >= min_bal:
                return bal

            # Ricarica
            resp = self.fund_wallet(topup)
            # Opzionale: logica di validazione soft della risposta
            # Ad es. 'operation_result' potrebbe contenere "committed in round ..."
            # In ogni caso, attendiamo l'indicizzazione e ricontrolliamo il saldo.
            time.sleep(sleep_seconds_between_checks)
            attempts += 1

        # Un ultimo check e ritorniamo comunque il saldo osservato
        return self.get_balance()

    # ------------- API di alto livello -------------
    @property
    def creator_address(self) -> str:
        return self.state["address"]

    @property
    def creator_label(self) -> str:
        return self.state["label"]

    @property
    def app_name(self) -> str:
        return self.state["app_name"]

    def show_config(self) -> Dict[str, Any]:
        """Ritorna lo stato corrente (quello persistito su JSON)."""
        return dict(self.state)

    # --- Asset operations ---
    def create_asset(
        self,
        unit_name: str,
        asset_name: str,
        total: int = 1,
        decimals: int = 0,
        default_frozen: bool = False,
        note: Optional[str] = None,
        metadata_url: Optional[str] = None,
        metadata: Optional[str] = None,
        # gestione dei ruoli:
        roles_mode: str = "self",  # "self" | "disabled" | "custom"
        manager_address: Optional[str] = None,
        reserve_address: Optional[str] = None,
        freeze_address: Optional[str] = None,
        clawback_address: Optional[str] = None,
        # funding thresholds (override opzionali)
        ensure_min_balance: Optional[int] = None,
        ensure_topup_amount: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Crea un ASA dal wallet configurato.

        roles_mode:
          - "self" (default): TUTTI i ruoli = creator_address (evita 400, strict=True)
          - "disabled": ruoli vuoti e strict=False (ruoli disabilitati)
          - "custom": usa i 4 indirizzi passati e strict=True

        Prima della transazione, assicura funding >= ensure_min_balance.
        """
        sender = self.creator_address

        # 1) Assicura funding adeguato prima della txn (fee + min balance ASA)
        self.ensure_funded(
            min_balance=ensure_min_balance or self.min_balance,
            topup_amount=ensure_topup_amount or self.topup_amount,
        )

        # 2) Prepara ruoli e strict
        if roles_mode not in {"self", "disabled", "custom"}:
            raise ValueError("roles_mode deve essere 'self', 'disabled' oppure 'custom'.")

        if roles_mode == "self":
            strict = True
            m = r = f = c = sender
        elif roles_mode == "disabled":
            strict = False
            m = r = f = c = ""
        else:  # custom
            strict = True
            required = [manager_address, reserve_address, freeze_address, clawback_address]
            if any(v is None for v in required):
                raise ValueError("Con roles_mode='custom' devi fornire tutti i 4 indirizzi di ruolo.")
            m, r, f, c = manager_address, reserve_address, freeze_address, clawback_address

        # 3) Esegue la transazione di creazione ASA
        res = self.client.asset_create_txn(
            sender_address=sender,
            total=total,
            strict_empty_address_check=strict,
            default_frozen=default_frozen,
            unit_name=unit_name,
            asset_name=asset_name,
            manager_address=m,
            reserve_address=r,
            freeze_address=f,
            clawback_address=c,
            metadata_url=metadata_url,
            metadata=metadata,
            decimals=decimals,
            note=note,
            label=self.creator_label,
        )
        return res

    def view_asset(self, asset_id: int) -> Dict[str, Any]:
        return self.client.blockchain_info("asset", {"asset_id": int(asset_id)})

    def search_assets(
        self,
        creator_address: Optional[str] = None,
        **filters: Any,
    ) -> Dict[str, Any]:
        """Cerca asset usando l'indexer. Default: creator = wallet corrente."""
        args = dict(filters)
        args.setdefault("creator", creator_address or self.creator_address)
        return self.client.search_on_blockchain("assets", args)

    # --- Utility ---
    def list_addresses(self) -> Dict[str, Any]:
        return self.client.get_addresses_by_jwt()
