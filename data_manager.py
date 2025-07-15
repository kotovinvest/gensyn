import json
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        self.history_dir = Path(Config.HISTORY_DIR)
        self.history_dir.mkdir(exist_ok=True)
        self.results_dir = Path(Config.RESULTS_DIR)
        self.results_dir.mkdir(exist_ok=True)
        self.current_data_file = self.history_dir / "current_data.json"
        self.history_file = self.history_dir / "history.json"
    
    def load_previous_data(self) -> Optional[List[Dict]]:
        try:
            if self.current_data_file.exists():
                with open(self.current_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"📂 Загружены предыдущие данные ({len(data)} нод)")
                return data
        except Exception as e:
            logger.warning(f"⚠️  Не удалось загрузить предыдущие данные: {e}")
        return None
    
    def save_current_data(self, data: List[Dict]):
        try:
            with open(self.current_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Текущие данные сохранены")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения текущих данных: {e}")
    
    def save_to_history(self, data: List[Dict]):
        try:
            history = []
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            history_entry = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            history.append(history_entry)
            
            if len(history) > 100:
                history = history[-100:]
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                
            logger.info(f"📚 Данные добавлены в историю (записей: {len(history)})")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в историю: {e}")
    
    def calculate_changes(self, current_data: List[Dict], previous_data: Optional[List[Dict]]) -> Dict:
        if not previous_data:
            return {}
        
        changes = {}
        prev_dict = {item['id']: item for item in previous_data}
        
        for current in current_data:
            node_id = current['id']
            if node_id in prev_dict:
                prev = prev_dict[node_id]
                changes[node_id] = {
                    'reward_change': current['reward'] - prev['reward'],
                    'score_change': current['score'] - prev['score'],
                    'online_change': current['online'] != prev['online'],
                    'tx_time_change': None
                }
                
                if current['last_tx_minutes_ago'] is not None and prev['last_tx_minutes_ago'] is not None:
                    changes[node_id]['tx_time_change'] = current['last_tx_minutes_ago'] - prev['last_tx_minutes_ago']
        
        return changes
    
    def get_status_text(self, tx_minutes: Optional[int]) -> str:
        if tx_minutes is None:
            return "Нет данных"
        elif tx_minutes < 10:
            return "Очень активна"
        elif tx_minutes < 30:
            return "Активна"
        elif tx_minutes < 60:
            return "⚠️ Предупреждение"
        else:
            return "🔴 ПРОБЛЕМА"
    
    def save_excel_report(self, data: List[Dict], changes: Dict, filename: str):
        try:
            excel_data = []
            for node in data:
                node_id = node['id']
                change = changes.get(node_id, {})
                
                excel_row = {
                    'ID': node['id'],
                    'Имя': node['name'],
                    'Адрес': node['address'],
                    'Онлайн': '✓' if node['online'] else '✗',
                    'Wins': node['reward'],
                    'Изм. Wins': change.get('reward_change', 0),
                    'Rewards': node['score'], 
                    'Изм. Rewards': change.get('score_change', 0),
                    'Последняя TX (мин)': node['last_tx_minutes_ago'],
                    'Статус': self.get_status_text(node['last_tx_minutes_ago']),
                    'Время обновления': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                excel_data.append(excel_row)
            
            df = pd.DataFrame(excel_data)
            
            excel_path = self.results_dir / filename
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Monitor Report', index=False)
                
                worksheet = writer.sheets['Monitor Report']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"📊 Excel отчет сохранен: {excel_path}")
            return str(excel_path)
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения Excel отчета: {e}")
            return None
    
    def print_console_report(self, data: List[Dict], changes: Dict):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "="*80)
        print(f"🔍 GENSYN NODES MONITOR REPORT - {current_time}")
        print("="*80)
        
        online_nodes = sum(1 for node in data if node.get('online', False))
        nodes_with_address = sum(1 for node in data if node.get('address'))
        total_reward = sum(node.get('reward', 0) for node in data)
        avg_score = sum(node.get('score', 0) for node in data) / len(data) if data else 0
        
        very_active = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and node['last_tx_minutes_ago'] < 10)
        active = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and 10 <= node['last_tx_minutes_ago'] < 30)
        warning = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and 30 <= node['last_tx_minutes_ago'] < 60)
        problem = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and node['last_tx_minutes_ago'] >= 60)
        no_data = sum(1 for node in data if node.get('last_tx_minutes_ago') is None)
        
        print(f"📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего нод: {len(data)}")
        print(f"   Онлайн: {online_nodes} ({online_nodes/len(data)*100:.1f}%)")
        print(f"   С EOA адресами: {nodes_with_address} ({nodes_with_address/len(data)*100:.1f}%)")
        print(f"   Общие Wins: {total_reward}")
        
        print(f"\n🚦 АКТИВНОСТЬ ТРАНЗАКЦИЙ:")
        print(f"   🟢 Очень активные (< 10 мин): {very_active}")
        print(f"   🟢 Активные (10-30 мин): {active}")
        print(f"   🟡 Предупреждение (30-60 мин): {warning}")
        print(f"   🔴 ПРОБЛЕМЫ (> 60 мин): {problem}")
        print(f"   ⚫ Нет данных: {no_data}")
        
        if warning > 0 or problem > 0:
            print(f"\n⚠️  ТРЕБУЮТ ВНИМАНИЯ:")
            for node in data:
                tx_time = node.get('last_tx_minutes_ago')
                if tx_time is not None and tx_time >= 30:
                    status = "🟡 ПРЕДУПРЕЖДЕНИЕ" if tx_time < 60 else "🔴 ПРОБЛЕМА"
                    print(f"   {status} {node['name']} | {tx_time} мин назад | {node['id'][:16]}...")
        
        if changes:
            print(f"\n📈 ИЗМЕНЕНИЯ С ПРЕДЫДУЩЕГО ЗАПУСКА:")
            significant_changes = []
            
            for node_id, change in changes.items():
                node = next((n for n in data if n['id'] == node_id), None)
                if not node:
                    continue
                    
                change_desc = []
                if change['reward_change'] != 0:
                    change_desc.append(f"Wins: {change['reward_change']:+d}")
                if change['score_change'] != 0:
                    change_desc.append(f"Rewards: {change['score_change']:+d}")
                if change['online_change']:
                    status = "🟢 ОНЛАЙН" if node['online'] else "🔴 ОФФЛАЙН"
                    change_desc.append(f"Статус: {status}")
                
                if change_desc:
                    significant_changes.append(f"   {node['name']}: {', '.join(change_desc)}")
            
            if significant_changes:
                for change in significant_changes[:10]:
                    print(change)
                if len(significant_changes) > 10:
                    print(f"   ... и еще {len(significant_changes) - 10} изменений")
            else:
                print("   Значительных изменений не обнаружено")
        
        print("="*80)