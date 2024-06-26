import os

import httpx
import pytz

from pathlib import Path

from datetime import datetime, time

from models.ticket import TicketRequest
from models.agents import Agent, Schedule

from utils.api_clients.usedesk_api_client import UsedeskAPIClient
from utils.logger import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERS_DATA_AGREE_PATH = PROJECT_ROOT / "statics/files/Согласие на обработку персональных данных.docx"
PERS_DATA_AGREE_AND_DIST_PATH = PROJECT_ROOT / "statics/files/Согласие на распространение персональных данных.docx"

USEDESK_PAVEL_ID = int(os.getenv("USEDESK_PAVEL_ID"))
USEDESK_DENIS_ID = int(os.getenv("USEDESK_DENIS_ID"))
USEDESK_NIKA_ID = int(os.getenv("USEDESK_NIKA_ID"))


class UsedeskService:
    def __init__(self, api_client: UsedeskAPIClient):
        self.api_client = api_client
        self.ticket: TicketRequest | None = None
        self.current_agent_id: int | None = None

    async def authenticate(self, token) -> None:
        await self.api_client.authenticate(token)

    async def load_ticket(self, ticket_data):
        self.ticket = ticket_data

    async def reply_to_reactivated_user(self, ticket_data, birthday) -> None:
        await self.load_ticket(ticket_data)

        text, file_paths = await self.get_notification_by_age(birthday)

        await self.send_message(message=text, ticket_id=self.ticket.id, file_paths=file_paths)
        await self.update_ticket(ticket_id=self.ticket.id, category_lid="Редактирование профиля")

        logger.info(f"The user with email {self.ticket.client_email} will receive a response ({self.ticket.id=}).")

    async def get_notification_by_age(self, birthday) -> (str, list):
        current_time = datetime.now()
        birthday_plus_12_years = birthday.replace(year=birthday.year + 12)
        birthday_plus_18_years = birthday.replace(year=birthday.year + 18)
        is_mistake_in_age = current_time < birthday_plus_12_years
        is_adult = current_time >= birthday_plus_18_years

        if is_mistake_in_age:
            return await self.get_incorrect_birth_year_notification()
        elif is_adult:
            return await self.get_adult_notification()
        else:
            return await self.get_teenager_notification()

    @staticmethod
    async def get_teenager_notification() -> tuple[str, list[Path]]:
        text = """
            <p>Здравствуйте!</p>
            <p>Ваш профиль был деактивирован по причине того, что вы не загрузили сканы согласий родителей на обработку ваших персональных данных в свой профиль.<br/>
            Временно активировали ваш профиль и продлили срок для загрузки согласий на 30 дней.<br/>
            Пожалуйста, загрузите сканы согласий в разделе — <a href="https://leader-id.ru/settings?tab=privacy">https://leader-id.ru/settings?tab=privacy</a>, иначе ваш профиль будет вновь деактивирован.</p>
            <p>Подробности можно прочитать в статье:<br/>
            <a href="http://leader-id.usedocs.com/article/42745">Где заполнить согласие несовершеннолетнего на обработку персональных данных?</a></p>
            <p>Если у вас остались вопросы, мы с радостью на них ответим.<br/>
            Служба поддержки Leader-ID.<br/>
            <a href="mailto:support@leader-id.ru">support@leader-id.ru</a></p>
            <hr/>
            <p>Основные вопросы и ответы в разделе «<a href="http://leader-id.usedocs.com/">Частые вопросы</a>»</p>
            <hr/>
            <p>Вы можете написать в наш чат-бот <a href="https://t.me/leaderid_bot" target="_blank">Telegram</a></p>
        """.strip()

        files = [PERS_DATA_AGREE_PATH, PERS_DATA_AGREE_AND_DIST_PATH]
        return text, files

    @staticmethod
    async def get_incorrect_birth_year_notification() -> tuple[str, None]:
        text = """
            <p>Здравствуйте!</p>
            <p>Ваш профиль был деактивирован, так как в настройках указан некорректный год рождения.<br/>
            Мы активировали профиль, пожалуйста, измените дату рождения, перейдя по ссылке: <a href="https://leader-id.ru/settings?tab=main">https://leader-id.ru/settings?tab=main</a>.</p>
            <br/>
            <p>Просим вас пройти небольшой <a href="https://pnp.leader-id.ru/polls/p/67645e46-f179-45f1-8caf-50ec0bcd99c8/" target="_blank">опрос удовлетворенности поддержкой</a>. Это позволит нам улучшить ее качество.</p>
            <br/>
            <p>Если у вас остались вопросы, мы с радостью на них ответим.<br/>
            Служба поддержки Leader-ID.<br/>
            <a href="mailto:support@leader-id.ru">support@leader-id.ru</a></p>
            <hr/>
            <p>Основные вопросы и ответы в разделе «<a href="http://leader-id.usedocs.com/">Частые вопросы</a>»</p>
            <hr/>
            <p>Вы можете написать в наш чат-бот <a href="https://t.me/leaderid_bot" target="_blank">Telegram</a></p>
        """.strip()
        return text, None

    @staticmethod
    async def get_adult_notification() -> tuple[str, None]:
        text = """
                    <p>Здравствуйте!</p>
                    <p>Восстановили ваш профиль. Пожалуйста, повторите вход в аккаунт.</p>
                    <br/>
                    <p>Просим вас пройти небольшой <a href="https://pnp.leader-id.ru/polls/p/67645e46-f179-45f1-8caf-50ec0bcd99c8/" target="_blank">опрос удовлетворенности поддержкой</a>. Это позволит нам улучшить ее качество.</p>
                    <br/>
                    <p>Если у вас остались вопросы, мы с радостью на них ответим.<br/>
                    Служба поддержки Leader-ID.<br/>
                    <a href="mailto:support@leader-id.ru">support@leader-id.ru</a></p>
                    <hr/>
                    <p>Основные вопросы и ответы в разделе «<a href="http://leader-id.usedocs.com/">Частые вопросы</a>»</p>
                    <hr/>
                    <p>Вы можете написать в наш чат-бот <a href="https://t.me/leaderid_bot" target="_blank">Telegram</a></p>
                """.strip()
        return text, None

    async def set_current_agent_id(self, agent_id=None) -> None:
        if agent_id:
            self.current_agent_id = agent_id
            return None

        agents = [
            Agent(usedesk_id=USEDESK_PAVEL_ID,
                  name="Pavel",
                  schedule=[Schedule(weekdays=[5, 6],
                                     start_time=time(9, 0),
                                     end_time=time(23, 0))]),
            Agent(usedesk_id=USEDESK_DENIS_ID,
                  name="Denis",
                  schedule=[Schedule(weekdays=list(range(0, 5)),
                                     start_time=time(18, 0),
                                     end_time=time(23, 0))]),
            Agent(usedesk_id=USEDESK_NIKA_ID,
                  name="Nika",
                  schedule=[Schedule(weekdays=list(range(0, 5)),
                                     start_time=time(10, 0),
                                     end_time=time(18, 0))]),
        ]
        tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(tz)
        weekday = now.weekday()
        current_time = now.time()

        for agent in agents:
            for schedule in agent.schedule:
                if weekday in schedule.weekdays and schedule.start_time <= current_time <= schedule.end_time:
                    self.current_agent_id = agent.usedesk_id
                    return None

    async def send_message(self, message, ticket_id, file_paths: list[Path] | None = None) -> httpx.Response:
        await self.set_current_agent_id()
        return await self.api_client.send_message(message=message,
                                                  ticket_id=ticket_id,
                                                  file_paths=file_paths,
                                                  agent_id=self.current_agent_id)

    async def update_ticket(self, ticket_id, category_lid) -> httpx.Response:
        return await self.api_client.update_ticket(ticket_id, category_lid)
