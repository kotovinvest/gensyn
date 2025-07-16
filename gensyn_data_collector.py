import requests
import json
import logging
import time
from typing import Dict, List, Optional
from web3 import Web3
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class GensynDataCollector:
    def __init__(self):
        self.peer_api_url = Config.GENSYN_PEER_API_URL
        self.rpc_url = Config.GENSYN_RPC_URL
        self.contract_address = Config.GENSYN_CONTRACT_ADDRESS
        self.chain_id = Config.GENSYN_CHAIN_ID
        
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        try:
            if self.w3.is_connected():
                logger.info(f"✓ Подключение к Gensyn Testnet (Chain ID: {self.chain_id})")
            else:
                logger.error("✗ Не удалось подключиться к Gensyn Testnet")
        except Exception as e:
            logger.error(f"✗ Ошибка подключения к Web3: {e}")
        
        self.contract_abi = [
            {
                "inputs": [{"internalType": "string[]", "name": "peerIds", "type": "string[]"}],
                "name": "getEoa",
                "outputs": [{"internalType": "address[]", "name": "", "type": "address[]"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        try:
            self.contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )
            logger.info(f"✓ Контракт инициализирован: {self.contract_address}")
        except Exception as e:
            logger.error(f"✗ Ошибка инициализации контракта: {e}")
            self.contract = None
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def read_node_ids(self, filename: str) -> List[str]:
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                node_ids = [line.strip() for line in file if line.strip()]
            logger.info(f"📋 Прочитано {len(node_ids)} ID нод из файла {filename}")
            return node_ids
        except FileNotFoundError:
            logger.error(f"❌ Файл {filename} не найден")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка при чтении файла {filename}: {e}")
            return []
    
    def get_peer_info(self, node_id: str) -> Optional[Dict]:
        try:
            params = {'id': node_id}
            response = self.session.get(self.peer_api_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"✓ Peer info для {node_id}: {data.get('peerName', 'Unknown')}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка при запросе информации о ноде {node_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON для ноды {node_id}: {e}")
            return None
    
    def get_eoa_addresses_batch(self, node_ids: List[str]) -> Dict[str, str]:
        try:
            if not self.contract:
                logger.error("❌ Контракт не инициализирован")
                return {}
            
            logger.info(f"🔗 Получаем EOA адреса для {len(node_ids)} нод...")
            
            eoa_addresses = self.contract.functions.getEoa(node_ids).call()
            
            result = {}
            for i in range(len(node_ids)):
                node_id = node_ids[i]
                
                if i < len(eoa_addresses):
                    eoa_address = eoa_addresses[i]
                    if eoa_address != "0x0000000000000000000000000000000000000000":
                        result[node_id] = eoa_address
                    else:
                        result[node_id] = None
                else:
                    result[node_id] = None
            
            valid_addresses = sum(1 for addr in result.values() if addr is not None)
            logger.info(f"✓ Получено {valid_addresses}/{len(node_ids)} валидных EOA адресов")
            return result
                
        except Exception as e:
            logger.error(f"❌ Ошибка при получении EOA адресов: {e}")
            return {node_id: None for node_id in node_ids}
    
    def get_last_internal_tx_time(self, eoa_address: str) -> Optional[int]:
        try:
            if not eoa_address or eoa_address == "0x0000000000000000000000000000000000000000":
                return None
            
            api_endpoints = [
                f"https://gensyn-testnet.explorer.alchemy.com/api/v2/addresses/{eoa_address}/internal-transactions",
                f"https://gensyn-testnet.explorer.alchemy.com/api/v1/addresses/{eoa_address}/internal-transactions",
                f"https://gensyn-testnet.explorer.alchemy.com/api/addresses/{eoa_address}/internal-transactions",
                f"https://gensyn-testnet.explorer.alchemy.com/api/v2/addresses/{eoa_address}/internal_transactions", 
                f"https://gensyn-testnet.explorer.alchemy.com/api/v1/addresses/{eoa_address}/internal_transactions",
                f"https://gensyn-testnet.explorer.alchemy.com/api/v2/addresses/{eoa_address}/transactions?filter=internal",
            ]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': f'https://gensyn-testnet.explorer.alchemy.com/address/{eoa_address}?tab=internal_txns',
                'Origin': 'https://gensyn-testnet.explorer.alchemy.com'
            }
            
            for endpoint in api_endpoints:
                try:
                    response = self.session.get(endpoint, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            
                            transactions = []
                            if isinstance(data, list):
                                transactions = data
                            elif isinstance(data, dict):
                                possible_keys = ['items', 'transactions', 'data', 'result', 'internal_transactions']
                                for key in possible_keys:
                                    if key in data and isinstance(data[key], list):
                                        transactions = data[key]
                                        break
                            
                            if transactions:
                                latest_timestamp = None
                                for tx in transactions:
                                    timestamp_fields = ['timestamp', 'block_timestamp', 'created_at', 'time', 'block_time']
                                    
                                    for field in timestamp_fields:
                                        if field in tx and tx[field]:
                                            timestamp_str = str(tx[field])
                                            try:
                                                if timestamp_str.isdigit():
                                                    timestamp = int(timestamp_str)
                                                    if timestamp > 1000000000000:
                                                        timestamp = timestamp / 1000
                                                else:
                                                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                                    timestamp = dt.timestamp()
                                                
                                                if latest_timestamp is None or timestamp > latest_timestamp:
                                                    latest_timestamp = timestamp
                                                    
                                                break
                                            except:
                                                continue
                                
                                if latest_timestamp:
                                    current_time = time.time()
                                    minutes_ago = int((current_time - latest_timestamp) / 60)
                                    return minutes_ago
                                    
                        except json.JSONDecodeError:
                            continue
                        
                except requests.exceptions.RequestException:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка получения tx времени для {eoa_address}: {e}")
            return None
    
    def collect_node_data(self, node_ids: List[str]) -> List[Dict]:
        logger.info(f"🔄 Начинаем сбор данных для {len(node_ids)} нод...")
        
        results = []
        eoa_addresses = self.get_eoa_addresses_batch(node_ids)
        
        for i, node_id in enumerate(node_ids):
            logger.info(f"  📊 Обработка ноды {i+1}/{len(node_ids)}: {node_id}")
            
            peer_info = self.get_peer_info(node_id)
            if not peer_info:
                logger.warning(f"  ⚠️  Не удалось получить peer info для {node_id}")
                result = {
                    'id': node_id,
                    'name': 'UNKNOWN',
                    'address': eoa_addresses.get(node_id),
                    'reward': 0,  # Wins
                    'score': 0,   # Rewards
                    'online': False,
                    'last_tx_minutes_ago': None,
                    'timestamp': datetime.now().isoformat()
                }
                results.append(result)
                continue
            
            eoa_address = eoa_addresses.get(node_id)
            last_tx_minutes = None
            
            if eoa_address:
                last_tx_minutes = self.get_last_internal_tx_time(eoa_address)
            
            # ИСПРАВЛЕНО: правильная привязка значений
            result = {
                'id': node_id,
                'name': peer_info.get('peerName', 'Unknown'),
                'address': eoa_address,
                'reward': peer_info.get('score', 0),      # score из API = Wins
                'score': peer_info.get('reward', 0),     # reward из API = Rewards
                'online': peer_info.get('online', False),
                'last_tx_minutes_ago': last_tx_minutes,
                'timestamp': datetime.now().isoformat()
            }
            
            results.append(result)
            
            status = "🟢"
            if last_tx_minutes is None:
                status = "⚫"
            elif last_tx_minutes > 30:
                status = "🔴"
            elif last_tx_minutes > 15:
                status = "🟡"
                
            logger.info(f"    {status} {result['name']} | TX: {last_tx_minutes}м | Wins: {result['reward']} | Rewards: {result['score']}")
            
            time.sleep(1)
        
        logger.info(f"✅ Сбор данных завершен!")
        return results
