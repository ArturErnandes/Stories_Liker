import  json
import asyncio
import sys
from colorama import Fore, init
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon import functions, types
import random

CONFIG_FILE = "wind_inf.json"

def load_proxy_settings():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        with open(CONFIG_FILE, 'r', encoding="utf-8-sig") as f:
            data = json.load(f)
            if 'proxy' in data:
                proxy = (
                    data['proxy']['type'],
                    data['proxy']['host'],
                    data['proxy']['port'],
                    True,
                    data['proxy']['username'],
                    data['proxy']['password']
                )
                print(f"{Fore.GREEN} [SUCCESS] {Fore.RESET} Прокси успешно загружено: {Fore.WHITE} {proxy}")
            else:
                print(f"{Fore.WHITE} [INFO] {Fore.RESET} Прокси отсутствует")
                proxy = None
            return proxy
    except Exception as e:
        print(f"Ошибка загрузки прокси: {e}")
        proxy = None
        return proxy


async def json_input(filename: str, proxy):
    try:
        with open(filename, 'r', encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        warning = f"Файл {filename} не найден!"
        print(warning)
        return None

    client = TelegramClient(
        session=data['session_file'],
        api_id=data['app_id'],
        api_hash=data['app_hash'],
        device_model=data['device'],
        app_version=data['app_version'],
        system_version=data['sdk'],
        proxy=proxy
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("Требуется авторизация")
            await client.send_code_request(data['phone'])
            try:
                code = input('Введите код из Telegram: ')
                await client.sign_in(data['phone'], code=code)
            except SessionPasswordNeededError:
                await client.sign_in(password=data['twoFA'])
            print("Успешный вход!")
        else:
            print("Сессия уже активна!")

        me = await client.get_me()
        info = f"Аккаунт {me.phone} авторизован"
        print(info)
        return client
    except Exception as e:
        warning = f"Ошибка: {e}"
        print(warning)
        return None


async def get_group_users_by_messages(client, name, group_link: str, max_batches: int = 5):

    try:
        entity = await client.get_entity(group_link)

        print(f"{Fore.WHITE}[INFO]{Fore.RESET} {name} Парсю участников по сообщениям из: {Fore.LIGHTBLUE_EX}{group_link}")
        all_users = {}
        offset_id = 0
        limit = 100

        for batch in range(max_batches):

            history = await client(functions.messages.GetHistoryRequest(
                peer=entity,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=0,
                hash=0
            ))
            messages = history.messages
            users = history.users

            if not messages:
                print(f"{Fore.YELLOW}[END]{Fore.RESET} История закончилась.")
                break
            for u in users:
                all_users[u.id] = u
            offset_id = messages[-1].id

            print(
                f"{Fore.WHITE}[BATCH]{Fore.RESET} {name} — пакет #{batch+1}: "
                f"получено {Fore.LIGHTBLUE_EX}{len(messages)}{Fore.RESET} сообщений, "
                f"{Fore.LIGHTBLUE_EX}{len(users)}{Fore.RESET} пользователей"
            )
            if len(messages) < limit:
                break
        result = list(all_users.values())
        print(f"{Fore.GREEN}[SUCCESS]{Fore.RESET} Всего найдено уникальных участников по сообщениям: {Fore.LIGHTBLUE_EX}{len(result)}{Fore.RESET}")
        return result
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Fore.RESET} Ошибка при парсинге по сообщениям: {e}")
        return []



async def get_group_users(client, name, group_link: str, max_batches: int = 10):
    try:
        entity = await client.get_entity(group_link)
        print(f"{Fore.WHITE}[INFO]{Fore.RESET} {name} Получаю участников из: {Fore.LIGHTBLUE_EX}{group_link}")
        all_users_by_id = {}
        offset = 0
        limit = 200
        for batch in range(max_batches):
            result = await client(functions.channels.GetParticipantsRequest(
                channel=entity,
                filter=types.ChannelParticipantsRecent(),  # как у тебя
                offset=offset,
                limit=limit,
                hash=0
            ))
            users_batch = result.users
            participants_batch = result.participants
            if not users_batch:
                break
            for u in users_batch:
                all_users_by_id[u.id] = u
            print(
                f"{Fore.WHITE}[BATCH]{Fore.RESET} {name} — пакет #{batch + 1}: "
                f"получено {Fore.LIGHTBLUE_EX}{len(users_batch)}{Fore.RESET} пользователей "
                f"(offset={offset})"
            )
            if len(participants_batch) < limit:
                break
            offset += limit

        users = list(all_users_by_id.values())
        print(f"{Fore.GREEN}[SUCCESS]{Fore.RESET} Итогово загружено пользователей: {Fore.LIGHTBLUE_EX}{len(users)}{Fore.RESET}")
        return users
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Fore.RESET} Не удалось получить участников: {e}")
        return []




def filter_premium_users(users_list):
    premium_users = []
    for user in users_list:
        if getattr(user, "premium", False):
            premium_users.append(user)
    print(f"{Fore.GREEN}[FILTER]{Fore.RESET} Премиум-пользователей отсортировано: {Fore.LIGHTBLUE_EX}{len(premium_users)}{Fore.RESET}")
    return premium_users



async def filter_users_with_stories(client, name, premium_users):
    print(f"{Fore.WHITE}[CHECK]{Fore.RESET} Аккаунт: {Fore.GREEN}{name}{Fore.RESET} — проверяю сторис у премиум-пользователей (точная проверка)...")

    good_users = []
    stories_count = 0
    bad_users = len(premium_users)
    iterat = 0

    for user in premium_users:
        try:
            iterat += 1
            result = await client(functions.stories.GetPeerStoriesRequest(
                peer=user.id
            ))

            if result.stories and result.stories.stories:
                good_users.append(user)
                stories_count += 1
                print(f"{iterat}. {Fore.LIGHTBLUE_EX}[{stories_count}]{Fore.RESET} Пользователь: {Fore.LIGHTBLUE_EX}@{user.username}{Fore.RESET} Осталось пользователей: {Fore.LIGHTBLUE_EX}{bad_users - iterat}")
            else:
                print(f"{iterat}. {Fore.WHITE}Аккаунт без истории{Fore.RESET} Осталось пользователей: {Fore.LIGHTBLUE_EX}{bad_users - iterat}")

        except FloodWaitError as e:
            print(
                f"{Fore.YELLOW}[FLOOD]{Fore.RESET} Аккаунт: {Fore.YELLOW}{name}{Fore.RESET} — "
                f"FloodWait на {e.seconds} секунд при проверке {user.id}"
            )
            await asyncio.sleep(e.seconds)
            continue

        except Exception as e:
            print(
                f"{Fore.LIGHTRED_EX}[WARN]{Fore.RESET} Аккаунт: {Fore.LIGHTRED_EX}{name}{Fore.RESET} — "
                f"ошибка при проверке сторис у {user.id}: {e}"
            )

        # Случайная задержка 3–5 секунд между запросами
        await asyncio.sleep(random.randint(3, 5))

    print(
        f"{Fore.GREEN}[SUCCESS]{Fore.RESET} Аккаунт: {Fore.GREEN}{name}{Fore.RESET} — "
        f"премиум-пользователей со сторис найдено: {Fore.LIGHTBLUE_EX}{len(good_users)}{Fore.RESET}"
    )

    return good_users




def save_usernames(users, filename="nft.txt"):
    count = 0
    with open(filename, "w", encoding="utf-8") as f:
        for user in users:
            username = user.username
            if username:
                f.write(f"@{username}" + "\n")
                count += 1

    print(f"{Fore.GREEN}[SUCCESS]{Fore.RESET} В файл {Fore.LIGHTBLUE_EX}{filename}{Fore.RESET} сохранено username: {Fore.LIGHTBLUE_EX}{count}{Fore.RESET}")


async def account_proceed(client, name, group):
    key = int(input("Введите 1 для парсинга по сообщениям или 2 для парсинга по группе "))
    if key == 1:
        users = await get_group_users_by_messages(client, name, group)
    else:
        users = await get_group_users(client, name, group)
    premium_users = filter_premium_users(users)
    good_users = await filter_users_with_stories(client, name, premium_users)
    save_usernames(good_users)


async def main():
    tasks = []
    with open(CONFIG_FILE, 'r', encoding="utf-8-sig") as f:
        data = json.load(f)
    proxy = load_proxy_settings()
    for number in data['numbers']:
        client = await json_input(f"{number}.json", proxy)
        if not client:
            continue
        me = await client.get_me()
        name = me.first_name
        group = input(f"Введите ссылку на группу для аккаунта {name}: ")
        tasks.append(account_proceed(client, name, group))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    init(autoreset=True)
    asyncio.run(main())
    input("Нажмите Enter для выхода...")
