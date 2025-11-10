# -*- coding: utf-8 -*-
"""
B4DApp Python SDK
=================

SDK ad alto livello per interagire con le API definite in 'algorand_api.py'.

Copre TUTTI gli endpoint esposti, con gestione sessione (session_token) e Bearer JWT (access_token)
per le rotte protette. Ogni metodo restituisce il JSON decodificato (dict) oppure solleva ApiError
in caso di HTTP error / problemi di parsing.

Uso tipico:
-----------
from b4dapp_sdk import B4DAppClient

client = B4DAppClient(base_url="http://127.0.0.1:8080", hsm_id="hsm_test_0", algod_id="algod_client_test_0", indexer_id="indexer_client_test_0")
client.login("luca@luca.com", "luca")
client.create_dapp("dapp_123", "ETHEREUM")
...

Note:
- Per le chiamate protette (Depends(JWTBearer())), è necessario aver generato l'access_token con /jwt_generation.
- I metodi *_txn accettano gli argomenti come nello schema FastAPI (anche liste).

Licenza: MIT
"""

from __future__ import annotations

import json
import base64
from typing import Any, Dict, List, Optional, Union

import requests


class ApiError(RuntimeError):
    """Errore generico per chiamate API fallite."""


class B4DAppClient:
    def __init__(
        self,
        base_url: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        indexer_id: Optional[str] = None,
        timeout: Optional[float] = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.hsm_id = hsm_id
        self.algod_id = algod_id
        self.indexer_id = indexer_id
        self.timeout = timeout

        self.session_token: Optional[str] = None
        self.access_token: Optional[str] = None

    # --------------------------
    # Helpers
    # --------------------------
    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _post(
        self,
        path: str,
        data: Dict[str, Any],
        needs_bearer: bool = False,
        raise_for_status: bool = True,
    ) -> Dict[str, Any]:
        headers: Dict[str, str] = {}
        if needs_bearer:
            if not self.access_token:
                raise ApiError("Questa chiamata richiede Authorization Bearer. Esegui prima jwt_generation.")
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            resp = requests.post(self._url(path), data=data, headers=headers, timeout=self.timeout)
        except Exception as e:
            raise ApiError(f"Errore di connessione verso {self._url(path)}: {e}") from e

        if raise_for_status and not resp.ok:
            raise ApiError(f"HTTP {resp.status_code} su {path}: {resp.text}")

        try:
            return resp.json()
        except Exception as e:
            raise ApiError(f"Impossibile decodificare JSON da {path}: {resp.text}") from e

    @staticmethod
    def b64encode_message(msg: Union[str, bytes]) -> str:
        if isinstance(msg, str):
            msg = msg.encode("utf-8")
        return base64.b64encode(msg).decode("utf-8")

    # --------------------------
    # Auth & User
    # --------------------------
    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        email = email or self.email
        password = password or self.password
        if not email or not password:
            raise ApiError("login richiede email e password.")
        payload = {"email": email, "password": password}
        res = self._post("/login", payload)
        self.session_token = res.get("sessionToken")
        return res

    def sign_up(self, email: str, password: str) -> Dict[str, Any]:
        return self._post("/sign_up", {"email": email, "password": password})

    def email_verification(self, email: str) -> Dict[str, Any]:
        return self._post("/email_verification", {"email": email})

    def reset_password(self, email: str) -> Dict[str, Any]:
        return self._post("/reset_password", {"email": email})

    def get_user_info(self) -> Dict[str, Any]:
        if not self.session_token:
            raise ApiError("get_user_info richiede session_token. Effettua prima login.")
        return self._post("/get_user_info", {"session_token": self.session_token})

    def update_user_info(self, updated_params: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
        if not self.session_token:
            raise ApiError("update_user_info richiede session_token. Effettua prima login.")
        return self._post("/update_user_info", {"updated_params": updated_params, "session_token": self.session_token})

    # --------------------------
    # DApp & JWT
    # --------------------------
    def get_dapp_keys(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        app_name_values: Optional[List[str]] = None,
        dapp_id_values: Optional[List[str]] = None,
        blockchain_values: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "email": email or self.email,
            "password": password or self.password,
            "app_name_values": app_name_values or [],
            "dapp_id_values": dapp_id_values or [],
            "blockchain_values": blockchain_values or [],
        }
        return self._post("/get_dapp_keys", payload)

    def create_dapp(self, app_name: str, blockchain: str) -> Dict[str, Any]:
        if not self.session_token:
            raise ApiError("create_dapp richiede session_token. Effettua prima login.")
        return self._post("/create_dapp", {"app_name": app_name, "blockchain": blockchain, "session_token": self.session_token})

    def jwt_generation(self, app_name: str, dapp_id: str, secret_key: str, blockchain: str) -> Dict[str, Any]:
        if not self.session_token:
            raise ApiError("jwt_generation richiede session_token. Effettua prima login.")
        res = self._post(
            "/jwt_generation",
            {"app_name": app_name, "dapp_id": dapp_id, "secret_key": secret_key, "blockchain": blockchain, "session_token": self.session_token},
        )
        self.access_token = res.get("access_token")
        return res

    def get_addresses_by_jwt(self) -> Dict[str, Any]:
        return self._post("/get_addresses_by_jwt", {}, needs_bearer=True)

    # --------------------------
    # Algo: sign/verify/import key, address generation, dispenser
    # --------------------------
    def algo_sign(self, label: Optional[str], message_b64: str, hsm_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"label": label, "message": message_b64, "hsm_id": hsm_id or self.hsm_id}
        return self._post("/algo/sign", payload, needs_bearer=True)

    def algo_verify(self, address: str, message_b64: str, sig: str, hsm_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"address": address, "message": message_b64, "sig": sig, "hsm_id": hsm_id or self.hsm_id}
        return self._post("/algo/verify", payload)

    def algo_import_public_key(self, address: str, hsm_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"address": address, "hsm_id": hsm_id or self.hsm_id}
        return self._post("/algo/import_public_key", payload)

    def algo_address_generation(self, label: Optional[str], hsm_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"label": label, "hsm_id": hsm_id or self.hsm_id}
        return self._post("/algo/address_generation", payload, needs_bearer=True)

    def algo_algos_dispenser(self, address: str, amount: int) -> Dict[str, Any]:
        payload = {"address": address, "amount": amount}
        return self._post("/algo/algos_dispenser", payload, needs_bearer=True)

    # --------------------------
    # Algo: Asset ops
    # --------------------------
    def asset_create_txn(
        self,
        sender_address: Optional[str] = None,
        total: int = 1,
        strict_empty_address_check: bool = True,
        default_frozen: bool = False,
        unit_name: str = "",
        asset_name: str = "",
        manager_address: str = "",
        reserve_address: str = "",
        freeze_address: str = "",
        clawback_address: str = "",
        metadata_url: Optional[str] = None,
        metadata: Optional[str] = None,
        decimals: int = 0,
        note: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "sender_address": sender_address,
            "total": total,
            "strict_empty_address_check": strict_empty_address_check,
            "default_frozen": default_frozen,
            "unit_name": unit_name,
            "asset_name": asset_name,
            "manager_address": manager_address,
            "reserve_address": reserve_address,
            "freeze_address": freeze_address,
            "clawback_address": clawback_address,
            "metadata_url": metadata_url,
            "metadata": metadata,
            "decimals": decimals,
            "note": note,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/asset_create_txn", payload, needs_bearer=True)

    def sbt_create_txn(
        self,
        sender_address: Optional[str] = None,
        total: int = 1,
        strict_empty_address_check: bool = True,
        unit_name: str = "",
        asset_name: str = "",
        reserve_address: str = "",
        metadata_url: Optional[str] = None,
        metadata: Optional[str] = None,
        decimals: int = 0,
        note: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "sender_address": sender_address,
            "total": total,
            "strict_empty_address_check": strict_empty_address_check,
            "unit_name": unit_name,
            "asset_name": asset_name,
            "reserve_address": reserve_address,
            "metadata_url": metadata_url,
            "metadata": metadata,
            "decimals": decimals,
            "note": note,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/sbt_create_txn", payload, needs_bearer=True)

    def asset_freeze_txn(
        self,
        asset_id: int,
        freeze_from_address: str,
        new_freeze_state: bool = True,
        note: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "asset_id": asset_id,
            "freeze_from_address": freeze_from_address,
            "new_freeze_state": new_freeze_state,
            "note": note,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/asset_freeze_txn", payload, needs_bearer=True)

    def asset_receive_txn(
        self,
        receiver_address: Optional[str],
        asset_index: int,
        note: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "receiver_address": receiver_address,
            "asset_index": asset_index,
            "note": note,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/asset_receive_txn", payload, needs_bearer=True)

    def asset_remove_txn(
        self,
        asset_id: int,
        note: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "asset_id": asset_id,
            "note": note,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/asset_remove_txn", payload, needs_bearer=True)

    def asset_revoke_txn(
        self,
        receiver_address: str,
        amount: int,
        asset_id: int,
        revoke_from_address: str,
        note: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "receiver_address": receiver_address,
            "amount": amount,
            "asset_id": asset_id,
            "revoke_from_address": revoke_from_address,
            "note": note,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/asset_revoke_txn", payload, needs_bearer=True)

    def asset_transfer_txn(
        self,
        receiver_address: str,
        amount: int,
        asset_id: int,
        note: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # N.B. nell'API receiver_address è tipizzato erroneamente come bool.
        payload: Dict[str, Any] = {
            "receiver_address": receiver_address,
            "amount": amount,
            "asset_id": asset_id,
            "note": note,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/asset_transfer_txn", payload, needs_bearer=True)

    def asset_update_txn(
        self,
        asset_id: int,
        strict_empty_address_check: bool = True,
        manager_address: str = "",
        clawback_address: str = "",
        freeze_address: str = "",
        reserve_address: str = "",
        note: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "asset_id": asset_id,
            "strict_empty_address_check": strict_empty_address_check,
            "manager_address": manager_address,
            "clawback_address": clawback_address,
            "freeze_address": freeze_address,
            "reserve_address": reserve_address,
            "note": note,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/asset_update_txn", payload, needs_bearer=True)

    # --------------------------
    # Algo: Payment
    # --------------------------
    def payment_txn(
        self,
        receiver_address: str,
        amount: int,
        note: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "receiver_address": receiver_address,
            "amount": amount,
            "note": note,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/payment_txn", payload, needs_bearer=True)

    # --------------------------
    # Algo: Application / Smart Contracts
    # --------------------------
    def application_create_txn(
        self,
        approval_program: str,
        clear_program: str,
        global_ints: int = 0,
        global_bytes: int = 0,
        local_ints: int = 0,
        local_bytes: int = 0,
        app_args: Optional[List[Any]] = None,
        app_args_types: Optional[List[str]] = None,
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        creator_private_key: Optional[str] = None,
        creator_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "approval_program": approval_program,
            "clear_program": clear_program,
            "global_ints": global_ints,
            "global_bytes": global_bytes,
            "local_ints": local_ints,
            "local_bytes": local_bytes,
            "app_args": app_args,
            "app_args_types": app_args_types,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "creator_private_key": creator_private_key,
            "creator_address": creator_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/application_create_txn", payload, needs_bearer=True)

    def application_update_txn(
        self,
        smart_contract_index: int,
        approval_program: Union[str, bytes],
        clear_program: Union[str, bytes],
        app_args: Optional[List[Any]] = None,
        app_args_types: Optional[List[str]] = None,
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        updater_private_key: Optional[str] = None,
        updater_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "smart_contract_index": smart_contract_index,
            "approval_program": approval_program,
            "clear_program": clear_program,
            "app_args": app_args,
            "app_args_types": app_args_types,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "updater_private_key": updater_private_key,
            "updater_address": updater_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/application_update_txn", payload, needs_bearer=True)

    def application_delete_txn(
        self,
        smart_contract_index: int,
        app_args: Optional[List[Any]] = None,
        app_args_types: Optional[List[str]] = None,
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        deleter_private_key: Optional[str] = None,
        deleter_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "smart_contract_index": smart_contract_index,
            "app_args": app_args,
            "app_args_types": app_args_types,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "deleter_private_key": deleter_private_key,
            "deleter_address": deleter_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/application_delete_txn", payload, needs_bearer=True)

    def application_opt_in_txn(
        self,
        smart_contract_index: int,
        app_args: Optional[List[Any]] = None,
        app_args_types: Optional[List[str]] = None,
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        sender_private_key: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "smart_contract_index": smart_contract_index,
            "app_args": app_args,
            "app_args_types": app_args_types,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "sender_private_key": sender_private_key,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/application_opt_in_txn", payload, needs_bearer=True)

    def application_close_out_txn(
        self,
        smart_contract_index: int,
        app_args: Optional[List[Any]] = None,
        app_args_types: Optional[List[str]] = None,
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        sender_private_key: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "smart_contract_index": smart_contract_index,
            "app_args": app_args,
            "app_args_types": app_args_types,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "sender_private_key": sender_private_key,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/application_close_out_txn", payload, needs_bearer=True)

    def application_clear_state_txn(
        self,
        smart_contract_index: int,
        app_args: Optional[List[Any]] = None,
        app_args_types: Optional[List[str]] = None,
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        sender_private_key: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "smart_contract_index": smart_contract_index,
            "app_args": app_args,
            "app_args_types": app_args_types,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "sender_private_key": sender_private_key,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/application_clear_state_txn", payload, needs_bearer=True)

    def application_call_txn(
        self,
        smart_contract_index: int,
        app_args: Optional[List[Any]] = None,
        app_args_types: Optional[List[str]] = None,
        on_complete_type: str = "NoOpOC",
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        sender_private_key: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "smart_contract_index": smart_contract_index,
            "app_args": app_args,
            "app_args_types": app_args_types,
            "on_complete_type": on_complete_type,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "sender_private_key": sender_private_key,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/application_call_txn", payload, needs_bearer=True)

    def method_call_txn(
        self,
        smart_contract_index: int,
        contract_json: str,
        method_name: str,
        method_args: Optional[List[Any]] = None,
        method_args_types: Optional[List[str]] = None,
        on_complete_type: str = "NoOpOC",
        accounts: Optional[List[str]] = None,
        foreign_apps: Optional[List[int]] = None,
        foreign_assets: Optional[List[int]] = None,
        note: Optional[str] = None,
        lease: Optional[str] = None,
        rekey_to: Optional[str] = None,
        box_key_values: Optional[List[str]] = None,
        box_budget_values: Optional[List[int]] = None,
        sender_private_key: Optional[str] = None,
        sender_address: Optional[str] = None,
        label: Optional[str] = None,
        hsm_id: Optional[str] = None,
        algod_id: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "smart_contract_index": smart_contract_index,
            "contract_json": contract_json,
            "method_name": method_name,
            "method_args": method_args,
            "method_args_types": method_args_types,
            "on_complete_type": on_complete_type,
            "accounts": accounts,
            "foreign_apps": foreign_apps,
            "foreign_assets": foreign_assets,
            "note": note,
            "lease": lease,
            "rekey_to": rekey_to,
            "box_key_values": box_key_values,
            "box_budget_values": box_budget_values,
            "sender_private_key": sender_private_key,
            "sender_address": sender_address,
            "label": label,
            "hsm_id": hsm_id or self.hsm_id,
            "algod_id": algod_id or self.algod_id,
            "id": id,
        }
        return self._post("/algo/method_call_txn", payload, needs_bearer=True)

    # --------------------------
    # Indexer: blockchain_info & search_on_blockchain
    # --------------------------
    def blockchain_info(self, subject: str, arguments: Dict[str, Any], indexer_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"subject": subject, "arguments": json.dumps(arguments), "indexer_id": indexer_id or self.indexer_id}
        return self._post("/algo/blockchain_info", payload)

    def search_on_blockchain(self, subject: str, arguments: Dict[str, Any], indexer_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {"subject": subject, "arguments": json.dumps(arguments), "indexer_id": indexer_id or self.indexer_id}
        return self._post("/algo/search_on_blockchain", payload)
