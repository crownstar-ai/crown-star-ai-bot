# blockchain/api.py – REST API for blockchain operations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dataclasses import asdict
from .core import get_bc_manager, get_token_manager, get_oracle_manager
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/blockchain", tags=["Blockchain"])

class BalanceRequest(BaseModel):
    address: str; chain: Optional[str] = None

class SendTransactionRequest(BaseModel):
    to: str; value: float; data: Optional[str] = None; chain: Optional[str] = None

class ContractCallRequest(BaseModel):
    contract_address: str; abi: List; function: str; args: List; chain: Optional[str] = None

class DeployContractRequest(BaseModel):
    bytecode: str; abi: List; constructor_args: List; chain: Optional[str] = None

class TransferERC20Request(BaseModel):
    contract_address: str; to: str; amount: float; decimals: int = 18; chain: Optional[str] = None

class MintNFTRequest(BaseModel):
    contract_address: str; to: str; token_uri: str; chain: Optional[str] = None

@router.get("/balance")
async def get_balance(req: BalanceRequest, user=Depends(require_permission("admin"))):
    mgr = get_bc_manager(); result = mgr.get_balance(req.address, req.chain); return result

@router.post("/transaction")
async def send_transaction(req: SendTransactionRequest, user=Depends(require_permission("admin"))):
    mgr = get_bc_manager(); data = bytes.fromhex(req.data) if req.data else b""
    receipt = mgr.send_transaction(req.to, req.value, data, req.chain)
    return {"tx_hash": receipt.tx_hash, "status": receipt.status, "gas_used": receipt.gas_used}

@router.post("/contract/call")
async def call_contract(req: ContractCallRequest, user=Depends(require_permission("admin"))):
    mgr = get_bc_manager(); result = mgr.call_contract(req.contract_address, req.abi, req.function, req.args, req.chain)
    return {"result": result}

@router.post("/contract/deploy")
async def deploy_contract(req: DeployContractRequest, user=Depends(require_permission("admin"))):
    mgr = get_bc_manager(); address = mgr.deploy_contract(req.bytecode, req.abi, req.constructor_args, req.chain)
    return {"contract_address": address}

@router.post("/token/erc20/transfer")
async def transfer_erc20(req: TransferERC20Request, user=Depends(require_permission("admin"))):
    mgr = get_token_manager(); result = mgr.transfer_erc20(req.contract_address, req.to, req.amount, req.decimals, req.chain)
    return {"status": "sent", "tx": result}

@router.get("/token/erc20/balance")
async def erc20_balance(contract_address: str, address: str, decimals: int = 18, chain: Optional[str] = None, user=Depends(require_permission("admin"))):
    mgr = get_token_manager(); balance = mgr.get_erc20_balance(contract_address, address, decimals, chain)
    return {"balance": balance}

@router.post("/token/nft/mint")
async def mint_nft(req: MintNFTRequest, user=Depends(require_permission("admin"))):
    mgr = get_token_manager(); result = mgr.mint_nft(req.contract_address, req.to, req.token_uri, req.chain)
    return {"result": result}

@router.get("/oracle/price/{pair}")
async def get_price(pair: str, chain: str = "ethereum", user=Depends(require_permission("admin"))):
    mgr = get_oracle_manager(); price = mgr.get_price(pair, chain)
    return {"pair": pair, "price": price}
