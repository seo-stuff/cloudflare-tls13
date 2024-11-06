import asyncio
import aiohttp
import os
from datetime import datetime
from typing import List, Dict, Optional

class CloudflareManager:
    def __init__(self, api_token: str, tls_action: str):
        self.api_token = api_token
        self.tls_action = tls_action
        self.base_url = "https://api.cloudflare.com/client/v4/zones"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.domains = []
        self.results = []

    async def fetch_page(self, session: aiohttp.ClientSession, page: int, per_page: int = 50) -> Optional[Dict]:
        try:
            url = f"{self.base_url}?page={page}&per_page={per_page}"
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Ошибка получения страницы {page}: {response.status}")
                    return None
        except Exception as e:
            print(f"Ошибка при получении страницы {page}: {str(e)}")
            return None

    async def update_tls_for_domain(self, session: aiohttp.ClientSession, domain: Dict) -> Dict:
        domain_id = domain['id']
        domain_name = domain['name']
        url = f"{self.base_url}/{domain_id}/settings/tls_1_3"
        
        tls_value = "on" if self.tls_action == "enable" else "off"
        action_text = "включен" if self.tls_action == "enable" else "отключен"
        
        try:
            async with session.patch(url, headers=self.headers, json={"value": tls_value}) as response:
                result = await response.json()
                status = response.status
                
                success = status == 200 and result.get('success', False)
                result_data = {
                    'domain_id': domain_id,
                    'domain_name': domain_name,
                    'success': success,
                    'status_code': status,
                }
                
                status_mark = "✓" if success else "✗"
                print(f"{status_mark} {domain_name}: {'TLS 1.3 ' + action_text if success else 'Ошибка'}")
                
                return result_data
        except Exception as e:
            print(f"✗ {domain_name}: Ошибка - {str(e)}")
            return {
                'domain_id': domain_id,
                'domain_name': domain_name,
                'success': False,
                'status_code': 0,
            }

    async def list_domains(self):
        async with aiohttp.ClientSession() as session:
            initial_data = await self.fetch_page(session, 1)
            if not initial_data or not initial_data.get('success'):
                raise Exception("Ошибка получения данных")

            total_pages = initial_data['result_info']['total_pages']
            total_domains = initial_data['result_info']['total_count']
            domains = initial_data['result']

            if total_pages > 1:
                tasks = [
                    self.fetch_page(session, page) 
                    for page in range(2, total_pages + 1)
                ]
                results = await asyncio.gather(*tasks)

                for result in results:
                    if result and result.get('success'):
                        domains.extend(result['result'])
            
            print("\nСписок доменов в аккаунте:")
            print("-" * 50)
            for domain in domains:
                print(f"{domain['name']}")
            print("-" * 50)
            print(f"Всего доменов: {total_domains}\n")

            return domains

    async def process_all_domains(self) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            initial_data = await self.fetch_page(session, 1)
            if not initial_data or not initial_data.get('success'):
                raise Exception("Ошибка получения данных")

            total_pages = initial_data['result_info']['total_pages']
            total_domains = initial_data['result_info']['total_count']
            print(f"Найдено {total_domains} доменов на {total_pages} страницах")

            self.domains.extend(initial_data['result'])

            if total_pages > 1:
                tasks = [
                    self.fetch_page(session, page) 
                    for page in range(2, total_pages + 1)
                ]
                results = await asyncio.gather(*tasks)

                for result in results:
                    if result and result.get('success'):
                        self.domains.extend(result['result'])

            action_text = "включения" if self.tls_action == "enable" else "отключения"
            print(f"\nНачинаем процесс {action_text} TLS 1.3 для {len(self.domains)} доменов...")
            
            tasks = [
                self.update_tls_for_domain(session, domain)
                for domain in self.domains
            ]
            self.results = await asyncio.gather(*tasks)

        return self.results

async def main():
    api_token = "ВСТАВИТЬ КЛЮЧ API"

    temp_manager = CloudflareManager(api_token, "")
    await temp_manager.list_domains()

    while True:
        print("\nВыберите действие:")
        print("1. Включить TLS 1.3 для всех доменов")
        print("2. Отключить TLS 1.3 для всех доменов")
        choice = input("Введите номер (1 или 2): ").strip()
        
        if choice in ['1', '2']:
            break
        print("Неверный выбор. Пожалуйста, введите 1 или 2.")

    tls_action = "enable" if choice == "1" else "disable"
    
    manager = CloudflareManager(api_token, tls_action)
    
    action_text = "включения" if tls_action == "enable" else "отключения"
    print(f"\nНачинаем процесс {action_text} TLS 1.3...")
    start_time = datetime.now()
    
    try:
        results = await manager.process_all_domains()
        
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        print(f"\nИтоги:")
        print(f"Всего обработано доменов: {len(results)}")
        print(f"Успешно: {successful}")
        print(f"С ошибками: {failed}")
        
    except Exception as e:
        print(f"Ошибка: {str(e)}")
    
    duration = datetime.now() - start_time
    print(f"\nВремя выполнения: {duration.total_seconds():.2f} секунд")
    input("\nНажмите Enter для завершения...")

if __name__ == "__main__":
    asyncio.run(main())