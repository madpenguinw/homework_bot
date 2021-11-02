import os
import logging
import time
import requests
import datetime
import telegram


from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

bot = telegram.Bot(token=TELEGRAM_TOKEN)

NUMBER_OF_MIUTES = 10
RETRY_TIME = 60 * NUMBER_OF_MIUTES
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}


class CodeIsNot200Error(Exception):
    """API возвращает код, отличный от 200."""


class RequestError(Exception):
    """Ошибка во время запроса."""


class UnexpectedHomeworkStatusError(Exception):
    """Обнаружен недокументированный статус домашней работы."""


def send_message(bot, message):
    """Отправка сообщений в Telegram."""
    bot.send_message(CHAT_ID, message)
    logger.info(
        f'В Telegram отправлено сообщение: {message}')


def get_api_answer(url, current_timestamp):
    """Получение ответа на запрос с API эндпоинта."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': current_timestamp}
    try:
        response = requests.get(url, headers=headers, params=payload)
        if response.status_code != 200:
            message = f'Эндпоинт недоступен. Код ответа {response.status_code}'
            logger.error(message)
            raise CodeIsNot200Error(message)
        return response.json()
    except requests.exceptions.RequestException as error:
        message = f'Во время запроса произошла ошибка {error}'
        logger.error(message)
        raise RequestError(message)


def parse_status(homework):
    """Выделение из полученного ответа статуса домашней работы."""
    status = homework.get('status')
    if status is None:
        message = 'Не получено значение статуса домашней работы'
        logging.error(message)
        send_message(bot, message)
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_STATUSES[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверка полученного ответа."""
    homeworks = response.get('homeworks')
    status = homeworks[0].get('status')
    if status not in HOMEWORK_STATUSES.keys():
        message = 'Обнаружен недокументированный статус домашней работы:'
        f'{status}'
        logger.error(message)
        raise UnexpectedHomeworkStatusError(message)
    if homeworks is None:
        logger.error('Не получено значение для homeworks')
    if homeworks == []:
        logger.error('На сайте нет работ, в которые были'
                     'внесены изменения за указанный промежуток времни.')
    return homeworks[0]


def main():
    """Запуск бота."""
    if PRACTICUM_TOKEN is None:
        logging.critical('Отсутствует PRACTICUM_TOKEN')
        exit()
    elif TELEGRAM_TOKEN is None:
        logging.critical('Отсутствует TELEGRAM_TOKEN')
        exit()
    elif CHAT_ID is None:
        logging.critical('Отсутствует CHAT_ID')
        exit()
    send_message(bot, 'Привет! Бот запущен.')
    dt = datetime.datetime.now()
    current_time_in_sec = time.mktime(dt.timetuple())
    number_of_days_ago = 30
    days_ago_in_sec = 86400 * number_of_days_ago
    time_delta = int(current_time_in_sec) - days_ago_in_sec
    old_homework = ''
    while True:
        try:
            response = get_api_answer(ENDPOINT, time_delta)
            current_homework = check_response(response)
            if current_homework != old_homework:
                current_homework_status = parse_status(current_homework)
                send_message(bot, current_homework_status)
            else:
                logger.info('За указаный промежуток времени статус '
                            'домашней работы не поменялся')
            old_homework = current_homework
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
