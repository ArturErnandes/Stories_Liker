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


async def get_group_users(client, name, group_link: str, max_batches: int = 10):
    try:
        entity = await client.get_entity(group_link)

        print(f"{Fore.WHITE}[INFO]{Fore.RESET} {name} Получаю участников из: {Fore.LIGHTBLUE_EX}{group_link}")

        all_users_by_id = {}
        offset = 2400
        limit = 200  # максимум, который имеет смысл просить у Telegram

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
                # больше никого не отдали — выходим
                break

            # добавляем пользователей без дублей по id
            for u in users_batch:
                all_users_by_id[u.id] = u

            print(
                f"{Fore.WHITE}[BATCH]{Fore.RESET} {name} — пакет #{batch + 1}: "
                f"получено {Fore.LIGHTBLUE_EX}{len(users_batch)}{Fore.RESET} пользователей "
                f"(offset={offset})"
            )

            # если вернули меньше, чем просили — дальше уже нечего запрашивать
            if len(participants_batch) < limit:
                break

            # сдвигаем окно на следующие 200
            offset += limit

        users = list(all_users_by_id.values())
        print(
            f"{Fore.GREEN}[SUCCESS]{Fore.RESET} Итогово загружено пользователей: "
            f"{Fore.LIGHTBLUE_EX}{len(users)}{Fore.RESET}"
        )
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
    """
    Точный вариант: проверяем сторис у каждого премиум-пользователя
    через stories.GetPeerStoriesRequest, без GetAllStoriesRequest.

    Между запросами — случайная задержка 3–5 секунд.
    """

    print(
        f"{Fore.WHITE}[CHECK]{Fore.RESET} Аккаунт: {Fore.GREEN}{name}{Fore.RESET} — "
        f"проверяю сторис у премиум-пользователей (точная проверка)..."
    )

    good_users = []

    for user in premium_users:
        try:
            # Точечный запрос сторис конкретного пользователя
            result = await client(functions.stories.GetPeerStoriesRequest(
                peer=user.id
            ))

            # У результата есть поле stories, в котором тоже есть список stories
            if result.stories and result.stories.stories:
                good_users.append(user)
                print('+1 сторис')
                try:
                    print(user.username)
                except Exception as e:
                    print(f'error {e}')
            else:
                print('без сторис')

        except FloodWaitError as e:
            print(
                f"{Fore.YELLOW}[FLOOD]{Fore.RESET} Аккаунт: {Fore.YELLOW}{name}{Fore.RESET} — "
                f"FloodWait на {e.seconds} секунд при проверке {user.id}"
            )
            await asyncio.sleep(e.seconds)
            # после ожидания просто идём дальше к следующему user
            continue

        except Exception as e:
            print(
                f"{Fore.LIGHTRED_EX}[WARN]{Fore.RESET} Аккаунт: {Fore.LIGHTRED_EX}{name}{Fore.RESET} — "
                f"ошибка при проверке сторис у {user.id}: {e}"
            )

        # Случайная задержка 3–5 секунд между запросами
        await asyncio.sleep(random.randint(1, 3))

    print(
        f"{Fore.GREEN}[SUCCESS]{Fore.RESET} Аккаунт: {Fore.GREEN}{name}{Fore.RESET} — "
        f"премиум-пользователей со сторис найдено: {Fore.LIGHTBLUE_EX}{len(good_users)}{Fore.RESET}"
    )

    return good_users




def save_usernames(users, filename="users.txt"):
    count = 0
    with open(filename, "w", encoding="utf-8") as f:
        for user in users:
            username = user.username
            if username:
                f.write(f"@{username}" + "\n")
                count += 1

    print(f"{Fore.GREEN}[SUCCESS]{Fore.RESET} В файл {Fore.LIGHTBLUE_EX}{filename}{Fore.RESET} сохранено username: {Fore.LIGHTBLUE_EX}{count}{Fore.RESET}")


async def account_proceed(client, name, group):
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
