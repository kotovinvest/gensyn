import requests
import time
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        try:
            if len(message) > 4000:
                parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for i, part in enumerate(parts):
                    if i > 0:
                        time.sleep(1)
                    self._send_single_message(part, parse_mode)
                return True
            else:
                return self._send_single_message(message, parse_mode)
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram сообщения: {e}")
            return False
    
    def _send_single_message(self, message: str, parse_mode: str = "HTML") -> bool:
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.info("📱 Telegram сообщение отправлено")
                return True
            else:
                logger.error(f"❌ Telegram API ошибка: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram сообщения: {e}")
            return False
    
    def send_document(self, file_path: str, caption: str = "") -> bool:
        try:
            url = f"{self.base_url}/sendDocument"
            
            with open(file_path, 'rb') as file:
                files = {'document': file}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                
                response = requests.post(url, data=data, files=files, timeout=30)
                
                if response.status_code == 200:
                    logger.info(f"📎 Telegram документ отправлен: {file_path}")
                    return True
                else:
                    logger.error(f"❌ Ошибка отправки документа: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Ошибка отправки документа: {e}")
            return False

    def create_main_report(self, data: List[Dict], changes: Dict) -> str:
        current_time = datetime.now().strftime("%H:%M:%S")
        
        online_nodes = sum(1 for node in data if node.get('online', False))
        nodes_with_address = sum(1 for node in data if node.get('address'))
        total_reward = sum(node.get('reward', 0) for node in data)
        avg_score = sum(node.get('score', 0) for node in data) / len(data) if data else 0
        
        very_active = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and node['last_tx_minutes_ago'] < 10)
        active = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and 10 <= node['last_tx_minutes_ago'] < 30)
        warning = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and 30 <= node['last_tx_minutes_ago'] < 60)
        problem = sum(1 for node in data if node.get('last_tx_minutes_ago') is not None and node['last_tx_minutes_ago'] >= 60)
        no_data = sum(1 for node in data if node.get('last_tx_minutes_ago') is None)
        
        message = f"🔍 <b>GENSYN MONITOR REPORT</b>\n"
        message += f"⏰ {current_time}\n\n"
        
        message += f"📊 <b>ОБЩАЯ СТАТИСТИКА:</b>\n"
        message += f"• Всего нод: <b>{len(data)}</b>\n"
        message += f"• Онлайн: <b>{online_nodes}</b> ({online_nodes/len(data)*100:.1f}%)\n"
        message += f"• С EOA адресами: <b>{nodes_with_address}</b> ({nodes_with_address/len(data)*100:.1f}%)\n"
        message += f"• Общие Wins: <b>{total_reward}</b>\n\n"
        
        message += f"🚦 <b>АКТИВНОСТЬ ТРАНЗАКЦИЙ:</b>\n"
        message += f"🟢 Очень активные (&lt;10м): <b>{very_active}</b>\n"
        message += f"🟢 Активные (10-30м): <b>{active}</b>\n"
        message += f"🟡 Предупреждение (30-60м): <b>{warning}</b>\n"
        message += f"🔴 ПРОБЛЕМЫ (&gt;60м): <b>{problem}</b>\n"
        message += f"⚫ Нет данных: <b>{no_data}</b>\n"
        
        if warning > 0 or problem > 0:
            message += f"\n⚠️ <b>ТРЕБУЮТ ВНИМАНИЯ:</b>\n"
            problem_nodes = []
            for node in data:
                tx_time = node.get('last_tx_minutes_ago')
                if tx_time is not None and tx_time >= 30:
                    status_icon = "🟡" if tx_time < 60 else "🔴"
                    problem_nodes.append(f"{status_icon} {node['name']} - {tx_time}м")
            
            for i, node_info in enumerate(problem_nodes[:5]):
                message += f"• {node_info}\n"
            if len(problem_nodes) > 5:
                message += f"• ... и еще {len(problem_nodes) - 5} нод\n"
        
        if changes:
            message += f"\n📈 <b>ИЗМЕНЕНИЯ:</b>\n"
            significant_changes = []
            
            for node_id, change in changes.items():
                node = next((n for n in data if n['id'] == node_id), None)
                if not node:
                    continue
                    
                change_parts = []
                if change['reward_change'] != 0:
                    icon = "🏆" if change['reward_change'] > 0 else "📉"
                    change_parts.append(f"Wins {icon}{change['reward_change']:+d}")
                if change['score_change'] != 0:
                    icon = "💰" if change['score_change'] > 0 else "📉"
                    change_parts.append(f"Rewards {icon}{change['score_change']:+d}")
                if change['online_change']:
                    status_icon = "🟢" if node['online'] else "🔴"
                    change_parts.append(f"Статус {status_icon}")
                
                if change_parts:
                    change_text = ", ".join(change_parts)
                    significant_changes.append(f"• <code>{node['name']}</code>: {change_text}")
            
            if significant_changes:
                for change in significant_changes[:8]:
                    message += f"{change}\n"
                if len(significant_changes) > 8:
                    message += f"• ... и еще {len(significant_changes) - 8} изменений\n"
            else:
                message += "• Значительных изменений не обнаружено\n"
        else:
            message += f"\n📊 <b>Первый запуск мониторинга</b>\n"
        
        return message
    
    def create_detailed_report(self, data: List[Dict]) -> str:
        message = "📋 <b>ДЕТАЛЬНЫЙ ОТЧЕТ ВСЕХ НОД:</b>\n\n"
        
        for i, node in enumerate(data, 1):
            tx_time = node.get('last_tx_minutes_ago')
            
            if tx_time is None:
                status = "⚫ Нет данных"
                last_tx_date = "Нет данных"
            elif tx_time < 10:
                status = "🟢 Очень активна"
                last_tx_date = f"{tx_time} мин назад"
            elif tx_time < 30:
                status = "🟢 Активна"
                last_tx_date = f"{tx_time} мин назад"
            elif tx_time < 60:
                status = "🟡 Предупреждение"
                last_tx_date = f"{tx_time} мин назад"
            else:
                status = "🔴 ПРОБЛЕМА"
                hours = tx_time // 60
                minutes = tx_time % 60
                last_tx_date = f"{hours}ч {minutes}м назад" if hours > 0 else f"{minutes} мин назад"
            
            online_status = "🟢 Онлайн" if node.get('online', False) else "🔴 Оффлайн"
            
            message += f"<b>ID:</b> <code>{node['id']}</code>\n"
            message += f"<b>Имя:</b> {node['name']}\n"
            message += f"<b>Адрес:</b> <code>{node.get('address', 'Нет адреса')}</code>\n"
            message += f"<b>Статус:</b> {online_status}\n"
            message += f"<b>Wins:</b> {node['reward']}\n"
            message += f"<b>Rewards:</b> {node['score']}\n"
            message += f"<b>Активность:</b> {status}\n"
            message += f"<b>Последняя TX:</b> {last_tx_date}\n"
            message += "=" * 30 + "\n\n"
            
            if len(message) > 3000:
                remaining = len(data) - i
                if remaining > 0:
                    message += f"... и еще {remaining} нод\n"
                break
                
        return message
    
    def create_critical_alert(self, critical_nodes: List[Dict]) -> str:
        alert_message = f"🚨 <b>КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ!</b>\n\n"
        alert_message += f"Обнаружено <b>{len(critical_nodes)}</b> нод без транзакций более часа!\n\n"
        
        for node in critical_nodes[:3]:
            tx_time = node['last_tx_minutes_ago']
            hours = tx_time // 60
            minutes = tx_time % 60
            time_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м"
            alert_message += f"🔴 <code>{node['name']}</code> - {time_str}\n"
        
        if len(critical_nodes) > 3:
            alert_message += f"... и еще {len(critical_nodes) - 3} нод\n"
        
        alert_message += f"\n⚡ Требуется немедленная проверка!"
        return alert_message

    def send_monitoring_notifications(self, data: List[Dict], changes: Dict, excel_file: Optional[str] = None):
        try:
            main_report = self.create_main_report(data, changes)
            success = self.send_message(main_report)
            
            if not success:
                logger.error("❌ Не удалось отправить основной отчет в Telegram")
                return
            
            critical_nodes = [node for node in data if 
                node.get('last_tx_minutes_ago') is not None and 
                node['last_tx_minutes_ago'] >= 60]
            
            if critical_nodes:
                time.sleep(1)
                alert_message = self.create_critical_alert(critical_nodes)
                self.send_message(alert_message)
            
            if excel_file and os.path.exists(excel_file):
                time.sleep(2)
                caption = f"📊 Детальный отчет мониторинга\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                self.send_document(excel_file, caption)
            
            if len(data) <= 15:
                time.sleep(2)
                detailed_report = self.create_detailed_report(data)
                self.send_message(detailed_report)
            
            logger.info("📱 Telegram уведомления отправлены успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки Telegram уведомлений: {e}")