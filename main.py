import logging
import time
import schedule
from datetime import datetime
from telegram_notifier import TelegramNotifier
from gensyn_data_collector import GensynDataCollector
from data_manager import DataManager
from config import Config

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('web3').setLevel(logging.WARNING)
logging.getLogger('schedule').setLevel(logging.WARNING)

class GensynMonitor:
    def __init__(self):
        self.telegram = TelegramNotifier(
            bot_token=Config.TELEGRAM_BOT_TOKEN,
            chat_id=Config.TELEGRAM_CHAT_ID
        )
        self.data_collector = GensynDataCollector()
        self.data_manager = DataManager()
    
    def run_monitoring_cycle(self):
        try:
            logger.info("🚀 Запуск цикла мониторинга...")
            
            start_message = f"🚀 <b>Запуск мониторинга Gensyn</b>\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            self.telegram.send_message(start_message)
            
            node_ids = self.data_collector.read_node_ids(Config.NODE_IDS_FILE)
            if not node_ids:
                error_message = f"❌ <b>ОШИБКА:</b> Не удалось прочитать ID нод из файла {Config.NODE_IDS_FILE}"
                self.telegram.send_message(error_message)
                logger.error("❌ Не удалось прочитать ID нод")
                return
            
            previous_data = self.data_manager.load_previous_data()
            
            current_data = self.data_collector.collect_node_data(node_ids)
            
            changes = self.data_manager.calculate_changes(current_data, previous_data)
            
            self.data_manager.print_console_report(current_data, changes)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            excel_filename = f"gensyn_monitor_{timestamp}.xlsx"
            excel_path = self.data_manager.save_excel_report(current_data, changes, excel_filename)
            
            self.telegram.send_monitoring_notifications(current_data, changes, excel_path)
            
            self.data_manager.save_current_data(current_data)
            self.data_manager.save_to_history(current_data)
            
            logger.info("✅ Цикл мониторинга завершен успешно!")
            
        except Exception as e:
            error_message = f"❌ <b>КРИТИЧЕСКАЯ ОШИБКА МОНИТОРИНГА:</b>\n<code>{str(e)}</code>"
            self.telegram.send_message(error_message)
            logger.error(f"❌ Ошибка в цикле мониторинга: {e}")
    
    def start_continuous_monitoring(self):
        print("🔄 GENSYN CONTINUOUS MONITOR WITH TELEGRAM")
        print("=" * 60)
        print(f"⏰ Мониторинг будет запускаться каждые {Config.MONITORING_INTERVAL_MINUTES} минут")
        print("📱 Отчеты отправляются в Telegram")
        print("🛑 Для остановки нажмите Ctrl+C")
        print("=" * 60)
        
        startup_message = (
            f"🤖 <b>GENSYN MONITOR ЗАПУЩЕН</b>\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏰ Интервал: каждые {Config.MONITORING_INTERVAL_MINUTES} минут\n"
            f"📱 Telegram уведомления: ВКЛ\n"
            f"🔄 Режим: Непрерывный мониторинг\n\n"
            f"ℹ️ Следующий отчет через {Config.MONITORING_INTERVAL_MINUTES} минут"
        )
        self.telegram.send_message(startup_message)
        
        schedule.every(Config.MONITORING_INTERVAL_MINUTES).minutes.do(self.run_monitoring_cycle)
        
        self.run_monitoring_cycle()
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            shutdown_message = (
                f"🛑 <b>МОНИТОРИНГ ОСТАНОВЛЕН</b>\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"👤 Остановлено пользователем"
            )
            self.telegram.send_message(shutdown_message)
            print("\n🛑 Мониторинг остановлен пользователем")
            logger.info("🛑 Мониторинг остановлен")

def main():
    print("=== GENSYN TELEGRAM MONITOR v4.0 ===")
    print("Требуемые библиотеки: pip install requests pandas openpyxl web3 schedule")
    print(f"🔄 Автоматический мониторинг каждые {Config.MONITORING_INTERVAL_MINUTES} минут")
    print("📊 Отслеживание динамики изменений")
    print("⚠️  Выделение проблемных нод (> 30 мин без TX)")
    print("📱 Telegram уведомления с детальными отчетами")
    print("🚨 Критические алерты при проблемах")
    print("=" * 70)
    
    monitor = GensynMonitor()
    
    test_message = "🧪 <b>ТЕСТ ПОДКЛЮЧЕНИЯ</b>\n✅ Gensyn Monitor готов к работе!"
    if monitor.telegram.send_message(test_message):
        print("✅ Telegram подключение работает!")
    else:
        print("❌ Проблема с Telegram подключением!")
        return
    
    print("\nВыберите режим работы:")
    print("1. Одиночный запуск (с отчетом в Telegram)")
    print("2. Непрерывный мониторинг (каждые {} минут)".format(Config.MONITORING_INTERVAL_MINUTES))
    
    try:
        choice = input("Введите номер (1 или 2): ").strip()
        
        if choice == "1":
            print("🚀 Запуск одиночного мониторинга...")
            monitor.run_monitoring_cycle()
        elif choice == "2":
            print("🔄 Запуск непрерывного мониторинга...")
            monitor.start_continuous_monitoring()
        else:
            print("❌ Неверный выбор. Запуск одиночного режима...")
            monitor.run_monitoring_cycle()
            
    except KeyboardInterrupt:
        shutdown_message = (
            f"🛑 <b>Программа остановлена</b>\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👤 Остановлено пользователем"
        )
        monitor.telegram.send_message(shutdown_message)
        print("\n🛑 Программа остановлена пользователем")

if __name__ == "__main__":
    main()