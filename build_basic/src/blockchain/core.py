# blockchain/core.py – CrownStar Cross‑Chain Blockchain Integration Engine
import os, json, time, hashlib, base64, secrets
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import logging
import requests

logger = logging.getLogger(__name__)

class ChainType(Enum):
    ETHEREUM = "ethereum"
    SOLANA = "solana"
    HYPERLEDGER_FABRIC = "fabric"

@dataclass
class ChainConfig:
    chain_type: ChainType
    rpc_url: str
    chain_id: int
    private_key: Optional[str] = None
    contract_addresses: Dict = None

@dataclass
class TransactionReceipt:
    tx_hash: str; block_number: int; status: int; gas_used: int; logs: List[Dict]; chain: str

@dataclass
class TokenBalance:
    chain: str; token_symbol: str; token_address: str; balance: float; decimals: int

class ChainInterface(ABC):
    def __init__(self, config: ChainConfig): self.config = config
    @abstractmethod def get_balance(self, address: str) -> float: pass
    @abstractmethod def send_transaction(self, to: str, value: float, data: bytes = b"") -> TransactionReceipt: pass
    @abstractmethod def call_contract(self, contract_address: str, abi: List, function: str, args: List) -> Any: pass
    @abstractmethod def deploy_contract(self, bytecode: str, abi: List, constructor_args: List) -> str: pass

class EthereumChain(ChainInterface):
    def __init__(self, config: ChainConfig):
        super().__init__(config)
        try:
            from web3 import Web3
            self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
            if config.private_key:
                self.account = self.w3.eth.account.from_key(config.private_key)
                self.address = self.account.address
            else:
                self.account = None; self.address = None
        except ImportError: self.w3 = None; logger.warning("web3 not installed")
    def get_balance(self, address: str) -> float:
        if not self.w3: return 0.0
        return self.w3.from_wei(self.w3.eth.get_balance(address), 'ether')
    def send_transaction(self, to: str, value: float, data: bytes = b"") -> TransactionReceipt:
        if not self.w3 or not self.account: raise Exception("Web3 not ready")
        tx = {'to': to, 'value': self.w3.to_wei(value, 'ether'), 'gas': 21000, 'gasPrice': self.w3.eth.gas_price, 'nonce': self.w3.eth.get_transaction_count(self.address), 'data': data}
        signed = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return TransactionReceipt(tx_hash=receipt.transactionHash.hex(), block_number=receipt.blockNumber, status=receipt.status, gas_used=receipt.gasUsed, logs=[log.to_dict() for log in receipt.logs], chain="ethereum")
    def call_contract(self, contract_address: str, abi: List, function: str, args: List) -> Any:
        if not self.w3: return None
        contract = self.w3.eth.contract(address=contract_address, abi=abi)
        return getattr(contract.functions, function)(*args).call()
    def deploy_contract(self, bytecode: str, abi: List, constructor_args: List) -> str:
        if not self.w3 or not self.account: raise Exception("Web3 not ready")
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
        construct_txn = contract.constructor(*constructor_args).build_transaction({'from': self.address, 'nonce': self.w3.eth.get_transaction_count(self.address), 'gas': 2000000, 'gasPrice': self.w3.eth.gas_price})
        signed = self.account.sign_transaction(construct_txn)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt.contractAddress

class SolanaChain(ChainInterface):
    def __init__(self, config: ChainConfig):
        super().__init__(config)
        try:
            from solana.rpc.api import Client
            from solana.keypair import Keypair
            from solana.publickey import PublicKey
            self.client = Client(config.rpc_url)
            if config.private_key:
                self.keypair = Keypair.from_secret_key(base64.b64decode(config.private_key))
                self.address = str(self.keypair.public_key)
            else:
                self.keypair = None; self.address = None
        except ImportError: self.client = None; logger.warning("solana-py not installed")
    def get_balance(self, address: str) -> float:
        if not self.client: return 0.0
        from solana.publickey import PublicKey
        return self.client.get_balance(PublicKey(address))['result']['value'] / 1e9
    def send_transaction(self, to: str, value: float, data: bytes = b"") -> TransactionReceipt:
        if not self.client or not self.keypair: raise Exception("Solana client not ready")
        from solana.transaction import Transaction
        from solana.system_program import TransferParams, transfer
        from solana.publickey import PublicKey
        lamports = int(value * 1e9)
        tx = Transaction().add(transfer(TransferParams(from_pubkey=self.keypair.public_key, to_pubkey=PublicKey(to), lamports=lamports)))
        resp = self.client.send_transaction(tx, self.keypair)
        return TransactionReceipt(tx_hash=resp['result'], block_number=0, status=1, gas_used=0, logs=[], chain="solana")
    def call_contract(self, contract_address: str, abi: List, function: str, args: List) -> Any: return None
    def deploy_contract(self, bytecode: str, abi: List, constructor_args: List) -> str: return "solana_program_address"

class FabricChain(ChainInterface):
    def __init__(self, config: ChainConfig):
        super().__init__(config)
        try:
            from hfc.fabric import Client as FabricClient
            self.client = FabricClient(net_profile=config.contract_addresses.get("network_profile"))
            self.channel = self.client.get_channel(config.contract_addresses.get("channel", "mychannel"))
        except ImportError: self.client = None; logger.warning("hfc not installed")
    def get_balance(self, address: str) -> float: return 0.0
    def send_transaction(self, to: str, value: float, data: bytes = b"") -> TransactionReceipt:
        return TransactionReceipt(tx_hash="", block_number=0, status=1, gas_used=0, logs=[], chain="fabric")
    def call_contract(self, contract_address: str, abi: List, function: str, args: List) -> Any:
        if not self.client: return None
        return self.client.chaincode_invoke(requestor="org1", channel_name="mychannel", cc_name=contract_address, fcn=function, args=args)
    def deploy_contract(self, bytecode: str, abi: List, constructor_args: List) -> str: return "fab_contract_id"

class BlockchainManager:
    def __init__(self, config_path="config/blockchain/config.json"):
        self.config = self._load_config(config_path)
        self.chains: Dict[str, ChainInterface] = {}
        self._init_chains()
    def _load_config(self, path):
        default = {"chains":[{"name":"ethereum","type":"ethereum","rpc_url":"https://sepolia.infura.io/v3/YOUR_KEY","chain_id":11155111,"private_key":""},{"name":"solana","type":"solana","rpc_url":"https://api.devnet.solana.com","chain_id":0,"private_key":""},{"name":"fabric","type":"fabric","rpc_url":"","chain_id":0,"contract_addresses":{"network_profile":"connection.json","channel":"mychannel"}}],"default_chain":"ethereum","gas_price_multiplier":1.0,"tx_timeout_seconds":120}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        return default
    def _init_chains(self):
        for cfg in self.config["chains"]:
            chain_type = ChainType(cfg["type"])
            chain_cfg = ChainConfig(chain_type=chain_type, rpc_url=cfg["rpc_url"], chain_id=cfg["chain_id"], private_key=cfg.get("private_key"), contract_addresses=cfg.get("contract_addresses"))
            if chain_type == ChainType.ETHEREUM: self.chains[cfg["name"]] = EthereumChain(chain_cfg)
            elif chain_type == ChainType.SOLANA: self.chains[cfg["name"]] = SolanaChain(chain_cfg)
            elif chain_type == ChainType.HYPERLEDGER_FABRIC: self.chains[cfg["name"]] = FabricChain(chain_cfg)
    def get_chain(self, name: str = None) -> ChainInterface:
        chain_name = name or self.config["default_chain"]
        if chain_name not in self.chains: raise ValueError(f"Chain {chain_name} not configured")
        return self.chains[chain_name]
    def get_balance(self, address: str, chain_name: str = None) -> Dict:
        chain = self.get_chain(chain_name)
        return {"chain": chain_name or self.config["default_chain"], "address": address, "balance": chain.get_balance(address)}
    def send_transaction(self, to: str, value: float, data: bytes = b"", chain_name: str = None) -> TransactionReceipt:
        chain = self.get_chain(chain_name)
        receipt = chain.send_transaction(to, value, data)
        try:
            cost_usd = receipt.gas_used * 20e-9
            requests.post("http://localhost:8080/v1/cost/metrics", json={"resource_id":f"tx_{receipt.tx_hash}","resource_type":"blockchain","provider":receipt.chain,"region":"global","hourly_cost":cost_usd,"utilization_cpu":0,"utilization_memory":0,"utilization_disk":0,"timestamp":int(time.time())}, timeout=1)
        except: pass
        return receipt
    def call_contract(self, contract_address: str, abi: List, function: str, args: List, chain_name: str = None) -> Any:
        return self.get_chain(chain_name).call_contract(contract_address, abi, function, args)
    def deploy_contract(self, bytecode: str, abi: List, constructor_args: List, chain_name: str = None) -> str:
        return self.get_chain(chain_name).deploy_contract(bytecode, abi, constructor_args)

class TokenManager:
    def __init__(self, blockchain_mgr: BlockchainManager): self.bc = blockchain_mgr
    def transfer_erc20(self, contract_address: str, to: str, amount: float, decimals: int = 18, chain_name: str = None):
        abi = [{"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}]
        amount_wei = int(amount * (10 ** decimals))
        return self.bc.call_contract(contract_address, abi, "transfer", [to, amount_wei], chain_name)
    def get_erc20_balance(self, contract_address: str, address: str, decimals: int = 18, chain_name: str = None) -> float:
        abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
        balance_wei = self.bc.call_contract(contract_address, abi, "balanceOf", [address], chain_name)
        return balance_wei / (10 ** decimals)
    def mint_nft(self, contract_address: str, to: str, token_uri: str, chain_name: str = None):
        abi = [{"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_tokenId","type":"uint256"},{"name":"_uri","type":"string"}],"name":"mint","outputs":[],"type":"function"}]
        token_id = int(time.time() * 1000)
        return self.bc.call_contract(contract_address, abi, "mint", [to, token_id, token_uri], chain_name)

class OracleManager:
    def get_price(self, pair: str, chain: str = "ethereum") -> float: return 1.0

_bc_manager = None
def get_bc_manager():
    global _bc_manager
    if _bc_manager is None: _bc_manager = BlockchainManager()
    return _bc_manager

_token_manager = None
def get_token_manager():
    global _token_manager
    if _token_manager is None: _token_manager = TokenManager(get_bc_manager())
    return _token_manager

_oracle_manager = None
def get_oracle_manager():
    global _oracle_manager
    if _oracle_manager is None: _oracle_manager = OracleManager()
    return _oracle_manager
