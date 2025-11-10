import  json
import asyncio
import sys
from colorama import Fore, init
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError
)
from telethon import functions
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


def users_maker(users_file):
    try:
        with open(f"{users_file}.txt", 'r', encoding="utf-8-sig") as f:
            users_list = [row.strip() for row in f]
        return users_list
    except Exception as e:
        print(f"Ошибка получения каналов из файла {users_file}.txt: {e}")
        return users_maker(input("Попробуйте ввести имя файла с пользователями (без .txt) еще раз "))


async def watch_user_story(client, name, user):
    try:
        # Получаем список историй
        result = await client(functions.stories.GetPeerStoriesRequest(peer=user))

        # Извлекаем список сторис
        peer_stories = result.stories
        stories_list = getattr(peer_stories, "stories", None)

        if not stories_list:
            print(f"{Fore.WHITE}[SUCCESS]{Fore.RESET} Аккаунт: {Fore.WHITE}{name}{Fore.RESET} — у пользователя {Fore.WHITE}{user}{Fore.RESET} нет активных историй")
            return False

        latest = stories_list[-1]

        # Отправляем реакцию 👀, чтобы Telegram засчитал просмотр
        from telethon.tl import types
        await client(functions.stories.SendReactionRequest(
            peer=user,
            story_id=latest.id,
            reaction=types.ReactionEmoji(emoticon="👀"),
            add_to_recent=False
        ))

        print(f"{Fore.GREEN}[SUCCESS]{Fore.RESET} Аккаунт: {Fore.GREEN}{name}{Fore.RESET} просмотрел историю пользователя {Fore.LIGHTBLUE_EX}@{user}{Fore.RESET}")
        return True

    except FloodWaitError as e:
        print(f"{Fore.YELLOW}[FLOOD]{Fore.RESET} Аккаунт: {Fore.YELLOW}{name}{Fore.RESET} — ожидание {e.seconds} секунд...")
        await asyncio.sleep(e.seconds)
        return await watch_user_story(client, name, user)

    except Exception as e:
        print(f"{Fore.LIGHTRED_EX}[ERROR]{Fore.RESET} Аккаунт: {Fore.LIGHTRED_EX}{name}{Fore.RESET} Ошибка при просмотре @{user}: {Fore.LIGHTRED_EX}{e}")
        return False



async def users_proceed(client, name, users_list):
    print(f"{Fore.GREEN}[PROCEEDING...]{Fore.RESET} Аккаунт: {Fore.GREEN}{name}")
    print(f"Пользователей для обработки: {Fore.LIGHTBLUE_EX} {len(users_list)}")

    for user in users_list:
        await watch_user_story(client, name, user)
        await asyncio.sleep(random.randint(3, 15))


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

        users_file = input(f"Введите название файла с пользователями для аккаунта {name} без .txt: ")
        users_list = users_maker(users_file)

        tasks.append(users_proceed(client, name, users_list))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    init(autoreset=True)
    asyncio.run(main())
    input("Нажмите Enter для выхода...")