"""Realistic test data seed script for Almaty, Astana, and Shymkent."""

import argparse
import asyncio
from datetime import datetime, timedelta
import os
import random
import sys
from typing import List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    ALMATY_DISTRICTS,
    ASTANA_DISTRICTS,
    CITY_DISTRICTS,
    DEFAULT_CITY,
    GENDER_FEMALE,
    GENDER_MALE,
    HOUSING_TYPE_FLAT,
    HOUSING_TYPE_ROOM,
    HOUSING_TYPE_SHARING,
    HOUSING_TYPE_SPOT,
    LISTING_STATUS_ACTIVE,
    ROLE_BOTH,
    ROLE_OWNER,
    ROLE_SEEKER,
    SHYMKENT_DISTRICTS,
)
from app.db.base import async_session_factory, init_db
from app.db.models import Like, Listing, Match, Report, SavedSearch, SeekerProfile, User


MALE_NAMES = [
    "Арман", "Данияр", "Олжас", "Нурсултан", "Алибек", "Санжар", "Берик", "Тимур", "Ерлан", "Рустам",
    "Азамат", "Бауыржан", "Даурен", "Ильяс", "Марат", "Кайрат", "Алишер", "Диас", "Талгат", "Адиль",
    "Ержан", "Мирас", "Айдос", "Бекзат", "Куаныш", "Ербол", "Дамир", "Аслан", "Нурлан", "Султан",
    "Бахыт", "Жандос", "Асет", "Мурат", "Серик", "Темирлан", "Чингиз", "Максат", "Шынгыс", "Айбек",
]

FEMALE_NAMES = [
    "Айдана", "Диана", "Асель", "Мадина", "Камила", "Айгерим", "Зарина", "Дана", "Гульнар", "Сауле",
    "Анара", "Алина", "Айзере", "Томирис", "Жанна", "Жанар", "Бота", "Меруерт", "Назерке", "Динара",
    "Сабина", "Аружан", "Карлыгаш", "Аяулым", "Гаухар", "Лаура", "Индира", "Жания", "Амина", "Сымбат",
    "Алма", "Молдир", "Жанель", "Куралай", "Алия", "Дилара", "Айнур", "Улжан", "Жулдыз", "Айсулу",
]

CITY_DISTRICTS_LANDMARKS = {
    "Алматы": {
        "Бостандыкский": ["ул. Сатпаева 90", "мкр. Орбита-1", "ул. Тимирязева 42", "ул. Розыбакиева 247 (рядом с MEGA)", "мкр. Коктем-2", "пр. Гагарина 155", "ул. Жандосова / Байзакова", "мкр. Алмагуль 18"],
        "Алмалинский": ["ул. Толе би 59", "ул. Панфилова 108", "ул. Гоголя 75", "пр. Сейфуллина / Макатаева (Mega Park)", "ул. Байтурсынова 67", "ул. Шевченко 114", "ул. Кабанбай батыра 85"],
        "Медеуский": ["пр. Достык 89 (возле гостиницы Казахстан)", "мкр. Самал-1 25", "ул. Калдаякова 34", "ул. Кунаева 130", "ул. Казыбек би 20", "пр. Аль-Фараби (Самал-2)", "ул. Пушкина 45"],
        "Ауэзовский": ["мкр. Сайран (озеро Сайран)", "мкр. Аксай-4 19", "пр. Абая 150 (ТРЦ Москва)", "мкр. Жетысу-3", "ул. Шаляпина 88", "ул. Момышулы 14", "мкр. Мамыр 7"],
        "Жетысуский": ["мкр. Айнабулак-2", "ул. Жансугурова (Белинского)", "пр. Рыскулова 103", "мкр. Кулагер 42", "ул. Северное кольцо"],
        "Наурызбайский": ["мкр. Калкаман-2", "мкр. Шугыла 340 (Акимат)", "ул. Жандосова 210", "мкр. Таусамалы 45", "мкр. Акжар"],
        "Турксибский": ["ул. Сейфуллина (вокзал Алматы-1)", "пр. Суюнбая 261", "ул. Шолохова 8", "мкр. Алтай-1", "мкр. Жулдыз"],
        "Алатауский": ["мкр. Саялы 22", "мкр. Дархан 15", "мкр. Зердели 60", "ул. Момышулы (Алматы Арена)", "мкр. Томирис"],
    },
    "Астана": {
        "Есильский": ["пр. Мангилик Ел 38", "ул. Достык 18 (Байтерек)", "ул. Сыганак 25", "ул. Сарайшык 5", "пр. Кабанбай батыра 40 (ТРЦ Азия Парк)"],
        "Алматинский": ["пр. Тауелсиздик 21", "ул. Жумабаева 14", "пр. Бауыржана Момышулы 10", "ул. Кошкарбаева 37", "мкр. Юго-Восток"],
        "Байконурский": ["ул. Кенесары 52", "пр. Республики 44", "ул. Сейфуллина 29", "ул. Иманова 19", "ул. Валиханова 12"],
        "Сарыаркинский": ["пр. Богенбай батыра 54", "пр. Сарыарка 15", "ул. Желтоксан 2", "ул. Бейбитшилик 25", "пр. Женис 30"],
        "Нуринский": ["пр. Туран 48 (Хан Шатыр)", "ул. Кайыма Мухамедханова 8", "ул. Чингиза Айтматова 36", "пр. Улы Дала 12", "ул. Толе би 40"],
    },
    "Шымкент": {
        "Абайский": ["пр. Республики 20", "ул. Казыбек би 34", "мкр. Самал-1 15", "ул. Жангельдина 12", "пр. Байдибек би 45"],
        "Аль-Фарабийский": ["пр. Тауке хана 45", "пр. Кунаева 58", "ул. Байтурсынова 19", "пл. Аль-Фараби 3", "ул. Дулати 22"],
        "Енбекшинский": ["ул. Елшибек батыра 88", "мкр. Восток 14", "ул. Сайрамская 190", "ул. Калдаякова 11", "мкр. Отырар 28"],
        "Каратауский": ["мкр. Нурсат 110", "пр. Байдибек би 128", "мкр. Туран 45", "мкр. Асар 82", "мкр. Достык 19"],
        "Туранский": ["мкр. Шымсити 14", "мкр. Акжайык 22", "ул. Аргынбекова 74", "мкр. Курсай 33", "мкр. Сауле 5"],
    },
}

KZ_BIOS = [
    "Satbayev университетінің студентімін, тазалық пен тыныштықты ұнатамын, темекі тартпаймын.",
    "IT компаниясында backend-әзірлеушімін, көбіне жұмыстамын, кешке тыныштықты бағалаймын.",
    "КазНУ-да оқимын, сабаққа көп көңіл бөлемін, жауапты және ұқыптымын.",
    "Маркетолог болып жұмыс істеймін, спортпен шұғылданамын, үйді үнемі таза ұстаймын.",
    "Магистрантпын және қашықтан жұмыс істеймін. Пәтерде тәртіп сақтаймын, төлемді уақытылы жасаймын.",
    "Қаржы саласында жұмыс істеймін, бос уақытта кітап оқимын, үйде тыныш атмосфера болғанын қалаймын.",
    "Медициналық университетте оқимын, күндіз көбіне оқудамын, сыпайы және қарапайыммын.",
    "Дизайнермін, үйдің жайлы болғанын ұнатамын, тамақ пісіремін, зиянды әдеттерім жоқ.",
    "Құрылыс саласында инженермін, сабырлымын, көршілермен тату тұру маңызды.",
    "Университетте 2-курс оқимын, бос уақытымда спортпен айналысамын, пәтерде тазалықты қатаң қадағалаймын.",
]

RU_BIOS = [
    "Студент Satbayev University, чистоплотный, не курю, уважаю личные границы и покой.",
    "Работаю графическим дизайнером на удалёнке, аккуратный, ценю чистоту и уют.",
    "Backend разработчик, дома бываю в основном по вечерам, без вредных привычек.",
    "Студентка КазНУ, много времени провожу за учёбой, ищу спокойную соседку.",
    "Работаю маркетологом, люблю спорт и горы, гарантирую своевременную оплату.",
    "Финансовый аналитик, дома ценю тишину, порядок и комфортную обстановку.",
    "Работаю в IT-стартапе, спокойный образ жизни, вечеринок дома не устраиваю.",
    "Учусь на магистратуре и подрабатываю, ответственный, чистоплотный и вежливый.",
    "Проектный менеджер, часто бываю в командировках, в квартире ценю порядок и тишину.",
    "Студент 3 курса, спокойный характер, вредных привычек нет, чистоплотен.",
]

KZ_IDEALS = [
    "Тазалықты сақтайтын, уақытылы төлейтін, кешке шуламайтын адам.",
    "Студент немесе жұмыс істейтін, зиянды әдеті жоқ, сыпайы көрші.",
    "Жауапты, өзгелердің демалысын құрметтейтін, тазалықты жақсы көретін көрші.",
    "Жұмыс істейтін, тыныш және үйді өз үйіндей күтетін адам.",
    "Студент, кішіпейіл, уақытылы ақшасын беретін, тәртіпті көрші.",
]

RU_IDEALS = [
    "Чистоплотный, платежеспособный, без вредных привычек и ночных вечеринок.",
    "Работающий или студент, который уважает тишину и порядок в доме.",
    "Адекватный, спокойный человек, ценящий уют и личное пространство.",
    "Без шумных компаний дома, чистоплотный, своевременная оплата аренды.",
    "Ответственный, опрятный, с позитивным отношением к жизни и уважением к другим.",
]


# 20 Diverse Test Users in Almaty
USERS_DATA = [
    {
        "telegram_id": 100001, "username": "arman_s", "first_name": "Арман",
        "age": 21, "gender": GENDER_MALE, "role": ROLE_SEEKER,
        "districts": ["Бостандыкский"], "budget": 110000, "date": "с 10 сентября",
        "occupation": "student", "smoking": "no", "pets": "no", "is_urgent": True,
        "bio": "Студент Satbayev University, чистоплотный, не курю, много учусь.",
    },
    {
        "telegram_id": 100002, "username": "diana_k", "first_name": "Диана",
        "age": 23, "gender": GENDER_FEMALE, "role": ROLE_SEEKER,
        "districts": ["Медеуский", "Алмалинский"], "budget": 130000, "date": "с 15 сентября",
        "occupation": "working", "smoking": "no", "pets": "yes", "is_urgent": False,
        "bio": "Работаю графическим дизайнером на удалёнке, есть воспитанная кошка.",
    },
    {
        "telegram_id": 100003, "username": "olzhas_dev", "first_name": "Олжас",
        "age": 25, "gender": GENDER_MALE, "role": ROLE_SEEKER,
        "districts": ["Бостандыкский", "Ауэзовский"], "budget": 100000, "date": "с 1 октября",
        "occupation": "working", "smoking": "no", "pets": "no", "is_urgent": False,
        "bio": "Backend разработчик, дома бываю в основном по вечерам, ценю тишину.",
    },
    {
        "telegram_id": 100004, "username": "asel_kz", "first_name": "Асель",
        "age": 20, "gender": GENDER_FEMALE, "role": ROLE_SEEKER,
        "districts": ["Алмалинский"], "budget": 90000, "date": "с 20 сентября",
        "occupation": "student", "smoking": "no", "pets": "no", "is_urgent": True,
        "bio": "Студентка КазНУ, ищу спокойную соседку без вредных привычек.",
    },
    {
        "telegram_id": 100005, "username": "nursultan_m", "first_name": "Нурсултан",
        "age": 24, "gender": GENDER_MALE, "role": ROLE_SEEKER,
        "districts": ["Медеуский"], "budget": 140000, "date": "с 15 сентября",
        "occupation": "working", "smoking": "yes", "pets": "no", "is_urgent": False,
        "bio": "Работаю маркетологом, люблю спорт и горы.",
    },
    {
        "telegram_id": 100006, "username": "madina_almaty", "first_name": "Мадина",
        "age": 22, "gender": GENDER_FEMALE, "role": ROLE_SEEKER,
        "districts": ["Бостандыкский"], "budget": 120000, "date": "в ближайшие 3 дня",
        "occupation": "working", "smoking": "no", "pets": "no", "is_urgent": True,
        "bio": "Срочно ищу подселение в Бостандыкском, чистоплотная и вежливая.",
    },
    {
        "telegram_id": 100007, "username": "daniyar_sat", "first_name": "Данияр",
        "age": 22, "gender": GENDER_MALE, "role": ROLE_SEEKER,
        "districts": ["Ауэзовский"], "budget": 80000, "date": "с 10 сентября",
        "occupation": "student", "smoking": "no", "pets": "no", "is_urgent": False,
        "bio": "Учусь на 4 курсе, ищу бюджетное место рядом с метро.",
    },
    {
        "telegram_id": 100008, "username": "kamila_t", "first_name": "Камила",
        "age": 26, "gender": GENDER_FEMALE, "role": ROLE_SEEKER,
        "districts": ["Медеуский", "Бостандыкский"], "budget": 150000, "date": "с 1 октября",
        "occupation": "working", "smoking": "no", "pets": "no", "is_urgent": False,
        "bio": "Финансовый аналитик, ищу отдельную уютную комнату.",
    },
    # Owners
    {
        "telegram_id": 100009, "username": "alibek_owner", "first_name": "Алибек",
        "age": 24, "gender": GENDER_MALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100010, "username": "aigerim_owner", "first_name": "Айгерим",
        "age": 23, "gender": GENDER_FEMALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100011, "username": "sanzhar_owner", "first_name": "Санжар",
        "age": 27, "gender": GENDER_MALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100012, "username": "zarina_owner", "first_name": "Зарина",
        "age": 25, "gender": GENDER_FEMALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100013, "username": "berik_owner", "first_name": "Берик",
        "age": 29, "gender": GENDER_MALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100014, "username": "dana_owner", "first_name": "Дана",
        "age": 22, "gender": GENDER_FEMALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100015, "username": "timur_owner", "first_name": "Тимур",
        "age": 26, "gender": GENDER_MALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100016, "username": "gulnar_owner", "first_name": "Гульнар",
        "age": 30, "gender": GENDER_FEMALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100017, "username": "erlan_owner", "first_name": "Ерлан",
        "age": 28, "gender": GENDER_MALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100018, "username": "saule_owner", "first_name": "Сауле",
        "age": 24, "gender": GENDER_FEMALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100019, "username": "rustam_owner", "first_name": "Рустам",
        "age": 25, "gender": GENDER_MALE, "role": ROLE_OWNER,
    },
    {
        "telegram_id": 100020, "username": "anara_owner", "first_name": "Анара",
        "age": 27, "gender": GENDER_FEMALE, "role": ROLE_OWNER,
    },
]

# 25 Diverse Listings across Almaty
LISTINGS_DATA = [
    # --- Бостандыкский район (4 active listings: for testing smooth browsing then exhaustion!) ---
    {
        "owner_idx": 8, "district": "Бостандыкский",
        "address": "ул. Сатпаева / Байтурсынова", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 110000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "с 10 сентября", "preferred_gender": GENDER_MALE, "smoking": False, "pets": False,
        "utilities": True, "deposit": 30000, "urgent": True,
        "desc": "Уютная комната в 2-комнатной квартире. Живёт один парень (студент Satbayev). Рядом метро Байконур.",
    },
    {
        "owner_idx": 8, "district": "Бостандыкский",
        "address": "мкр. Орбита-2, ул. Мустафина", "housing_type": HOUSING_TYPE_SHARING,
        "total_rooms": 3, "price_per_person": 90000, "available_places": 2, "occupied_places": 1,
        "move_in_date": "с 15 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": False, "deposit": 20000, "urgent": False,
        "desc": "3-комнатная квартира, просторный зал, тихий зелёный двор. Ищем 2 человек для подселения по 90 000 ₸.",
    },
    {
        "owner_idx": 10, "district": "Бостандыкский",
        "address": "ул. Тимирязева / Розыбакиева (рядом с MEGA)", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 3, "price_per_person": 120000, "available_places": 1, "occupied_places": 2,
        "move_in_date": "с 20 сентября", "preferred_gender": GENDER_MALE, "smoking": False, "pets": False,
        "utilities": True, "deposit": 40000, "urgent": False,
        "desc": "Изолированная комната в ЖК рядом с Мегой на Розыбакиева. Современная мебель, Wi-Fi 500 Мбит.",
    },
    {
        "owner_idx": 12, "district": "Бостандыкский",
        "address": "ул. Жандосова / Алтынсарина", "housing_type": HOUSING_TYPE_SPOT,
        "total_rooms": 2, "price_per_person": 75000, "available_places": 1, "occupied_places": 2,
        "move_in_date": "свободно сейчас", "preferred_gender": GENDER_MALE, "smoking": False, "pets": False,
        "utilities": True, "deposit": 15000, "urgent": True,
        "desc": "Свободно одно место в комнате на двоих. Чисто, опрятно, стиралка, микроволновка.",
    },

    # --- Алмалинский район ---
    {
        "owner_idx": 9, "district": "Алмалинский",
        "address": "ул. Толе би / Байтурсынова", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 105000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "с 12 сентября", "preferred_gender": GENDER_FEMALE, "smoking": False, "pets": False,
        "utilities": True, "deposit": 30000, "urgent": False,
        "desc": "Для девушки. Светлая комната с балконом в центре Алматы. До Абылай хана 10 минут пешком.",
    },
    {
        "owner_idx": 11, "district": "Алмалинский",
        "address": "ул. Макатаева / Сейфуллина (ТРК Mega Park)", "housing_type": HOUSING_TYPE_SHARING,
        "total_rooms": 3, "price_per_person": 95000, "available_places": 2, "occupied_places": 1,
        "move_in_date": "с 15 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": False, "deposit": 25000, "urgent": False,
        "desc": "3-комнатная квартира, евроремонт. Свободны 2 места. Отличная транспортная развязка.",
    },
    {
        "owner_idx": 13, "district": "Алмалинский",
        "address": "ул. Гоголя / Панфилова", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 135000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "с 1 октября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": True, "deposit": 50000, "urgent": False,
        "desc": "Золотой квадрат, рядом Арбат и пешеходная Панфилова. Идеально для работающего специалиста.",
    },
    {
        "owner_idx": 9, "district": "Алмалинский",
        "address": "ул. Шевченко / Достык", "housing_type": HOUSING_TYPE_FLAT,
        "total_rooms": 2, "price_per_person": 140000, "available_places": 2, "occupied_places": 0,
        "move_in_date": "с 15 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": False, "deposit": 50000, "urgent": True,
        "desc": "Сдаётся квартира целиком для 2 студентов или пары. Полностью меблирована.",
    },

    # --- Медеуский район ---
    {
        "owner_idx": 11, "district": "Медеуский",
        "address": "пр. Достык / ул. Курмангазы", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 3, "price_per_person": 140000, "available_places": 1, "occupied_places": 2,
        "move_in_date": "с 15 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": True, "deposit": 40000, "urgent": False,
        "desc": "Престижный район, вид на горы, кондиционер, рядом гостиница Казахстан.",
    },
    {
        "owner_idx": 14, "district": "Медеуский",
        "address": "мкр. Самал-2, пр. Аль-Фараби", "housing_type": HOUSING_TYPE_SHARING,
        "total_rooms": 4, "price_per_person": 125000, "available_places": 3, "occupied_places": 1,
        "move_in_date": "с 20 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": False, "deposit": 30000, "urgent": False,
        "desc": "Просторная 4-комнатная квартира в Самале. Свободно 3 места. Ищем приличных соседей.",
    },
    {
        "owner_idx": 15, "district": "Медеуский",
        "address": "ул. Калдаякова / Казыбек би", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 115000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "свободно сейчас", "preferred_gender": GENDER_FEMALE, "smoking": False, "pets": False,
        "utilities": True, "deposit": 25000, "urgent": True,
        "desc": "Рядом парк 28 Панфиловцев. Зелёный район, тихие соседи, для чистоплотной девушки.",
    },

    # --- Ауэзовский район ---
    {
        "owner_idx": 16, "district": "Ауэзовский",
        "address": "мкр. Сайран, ул. Толе би", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 3, "price_per_person": 85000, "available_places": 1, "occupied_places": 2,
        "move_in_date": "с 10 сентября", "preferred_gender": GENDER_MALE, "smoking": False, "pets": False,
        "utilities": True, "deposit": 20000, "urgent": True,
        "desc": "Прямо возле озера Сайран и станции метро. Свежий воздух, отличный вид из окна.",
    },
    {
        "owner_idx": 16, "district": "Ауэзовский",
        "address": "мкр. Аксай-4, ул. Момышулы", "housing_type": HOUSING_TYPE_SPOT,
        "total_rooms": 2, "price_per_person": 70000, "available_places": 2, "occupied_places": 1,
        "move_in_date": "с 15 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": False, "deposit": 15000, "urgent": False,
        "desc": "Бюджетное жильё для студентов, рядом остановки, рынок Арыстан, супермаркет Магнум.",
    },
    {
        "owner_idx": 17, "district": "Ауэзовский",
        "address": "мкр. Жетысу-3, пр. Абая", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 95000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "с 1 октября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": True, "deposit": 25000, "urgent": False,
        "desc": "Рядом станция метро Сарыарка, ТРЦ Москва. Тёплая чистая квартира.",
    },

    # --- Жетысуский район ---
    {
        "owner_idx": 18, "district": "Жетысуский",
        "address": "мкр. Айнабулак-2", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 80000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "с 15 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": True, "deposit": 20000, "urgent": False,
        "desc": "Уютная комната, тихий двор, много магазинов вокруг.",
    },
    {
        "owner_idx": 18, "district": "Жетысуский",
        "address": "ул. Белинского (Жансугурова)", "housing_type": HOUSING_TYPE_SPOT,
        "total_rooms": 3, "price_per_person": 65000, "available_places": 2, "occupied_places": 2,
        "move_in_date": "свободно сейчас", "preferred_gender": GENDER_MALE, "smoking": False, "pets": False,
        "utilities": True, "deposit": 10000, "urgent": True,
        "desc": "2 места в 3-комнатной квартире, очень выгодно для парней-студентов.",
    },

    # --- Наурызбайский район ---
    {
        "owner_idx": 19, "district": "Наурызбайский",
        "address": "мкр. Калкаман-2, ул. Шаляпина", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 3, "price_per_person": 85000, "available_places": 1, "occupied_places": 2,
        "move_in_date": "с 1 октября", "preferred_gender": "any", "smoking": False, "pets": True,
        "utilities": True, "deposit": 20000, "urgent": False,
        "desc": "Новый жилой комплекс, экологически чистый район, можно с маленьким питомцем.",
    },

    # --- Турксибский район ---
    {
        "owner_idx": 17, "district": "Турксибский",
        "address": "ул. Сейфуллина (район Алматы-1)", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 75000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "с 10 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": True, "deposit": 15000, "urgent": False,
        "desc": "Рядом вокзал Алматы-1, много автобусов в любую точку города.",
    },

    # --- Алатауский район ---
    {
        "owner_idx": 19, "district": "Алатауский",
        "address": "мкр. Саялы, ул. Аккайнар", "housing_type": HOUSING_TYPE_ROOM,
        "total_rooms": 2, "price_per_person": 70000, "available_places": 1, "occupied_places": 1,
        "move_in_date": "с 15 сентября", "preferred_gender": "any", "smoking": False, "pets": False,
        "utilities": True, "deposit": 15000, "urgent": False,
        "desc": "Новые дома, тихо, чистый воздух, парковка во дворе.",
    },
]


async def seed_database(session: AsyncSession, count: int = 500, city: str = "all") -> dict:
    """Populates database with realistic test users and listings.
    Supports generating up to 500+ realistic candidates across Almaty, Astana, and Shymkent.
    """
    created_users = []
    created_listings = []

    # 1. Base curated users (Almaty)
    for udata in USERS_DATA:
        stmt = select(User).where(User.telegram_id == udata["telegram_id"])
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=udata["telegram_id"],
                username=udata["username"],
                first_name=udata["first_name"],
                age=udata.get("age"),
                gender=udata.get("gender"),
                role=udata["role"],
                is_verified=True,
                language="kz" if udata["telegram_id"] % 2 == 0 else "ru",
            )
            session.add(user)
            await session.flush()

        if udata["role"] in (ROLE_SEEKER, ROLE_BOTH):
            p_stmt = select(SeekerProfile).where(SeekerProfile.user_id == user.id)
            p_res = await session.execute(p_stmt)
            prof = p_res.scalar_one_or_none()
            if not prof:
                prof = SeekerProfile(
                    user_id=user.id,
                    name=udata["first_name"],
                    age=udata.get("age"),
                    gender=udata.get("gender"),
                    city=DEFAULT_CITY,
                    districts=udata.get("districts", ["Бостандыкский"]),
                    budget_max=udata.get("budget", 120000),
                    budget_range=f"{udata.get('budget', 120000):,} ₸",
                    move_in_date=udata.get("date", "В ближайшее время"),
                    smoking=udata.get("smoking", "no"),
                    pets=udata.get("pets", "no"),
                    occupation=udata.get("occupation", "student"),
                    raw_bio=udata.get("bio"),
                    about_self_desc=udata.get("bio"),
                    ideal_neighbor_desc="Тазалықты сақтайтын, тыныш көрші",
                    is_urgent=udata.get("is_urgent", False),
                    is_active=True,
                    has_apartment=False,
                    preferred_room_type="Тек жеке бөлме",
                )
                session.add(prof)

        created_users.append(user)

    for ldata in LISTINGS_DATA:
        owner_idx = ldata["owner_idx"]
        owner_user = created_users[owner_idx]

        chk_stmt = select(Listing).where(
            Listing.owner_id == owner_user.id,
            Listing.address_landmark == ldata["address"],
        )
        chk_res = await session.execute(chk_stmt)
        if chk_res.scalar_one_or_none():
            continue

        listing = Listing(
            owner_id=owner_user.id,
            city=DEFAULT_CITY,
            district=ldata["district"],
            address_landmark=ldata["address"],
            housing_type=ldata["housing_type"],
            total_rooms=ldata["total_rooms"],
            total_price=ldata["price_per_person"] * ldata["available_places"],
            price_per_person=ldata["price_per_person"],
            utilities_included=ldata["utilities"],
            deposit_amount=ldata["deposit"],
            move_in_date=ldata["move_in_date"],
            available_places=ldata["available_places"],
            occupied_places=ldata["occupied_places"],
            preferred_gender=ldata["preferred_gender"],
            smoking_allowed=ldata["smoking"],
            pets_allowed=ldata["pets"],
            conditions_description=ldata["desc"],
            status=LISTING_STATUS_ACTIVE,
            is_verified=True,
            is_urgent=ldata["urgent"],
            last_confirmed_at=datetime.utcnow(),
        )
        session.add(listing)
        created_listings.append(listing)

    # 2. Dynamic generation for requested count
    target_additional = max(0, count - len(created_users))
    if target_additional > 0:
        max_tid_res = await session.execute(select(func.max(User.telegram_id)))
        max_tid = max_tid_res.scalar() or 200000
        start_tid = max(200000, max_tid + 1)

        cities_pool = ["Алматы", "Астана", "Шымкент"] if city == "all" else [city]
        occupations_pool = ["student", "working", "work_study"]
        move_in_dates_kz = ["⚡ Мүмкіндігінше тезірек", "📅 Бір апта ішінде", "🗓 Бір ай ішінде", "Жақын арада", "1 қыркүйек"]
        move_in_dates_ru = ["⚡ Как можно скорее", "📅 В течение недели", "🗓 В течение месяца", "В ближайшее время", "С 1 числа"]
        budgets_pool = [70000, 80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 170000, 200000]
        budget_ranges_pool = [
            "До 70 000 ₸", "70 000–100 000 ₸", "100 000–150 000 ₸", "150 000–200 000 ₸", "Более 200 000 ₸"
        ]
        rooms_count_kz = ["1-бөлмелі", "2-бөлмелі", "3-бөлмелі", "4+ бөлмелі"]
        rooms_count_ru = ["1-комнатная", "2-комнатная", "3-комнатная", "4+ комнатная"]
        pref_rooms_kz = ["🛏 Тек жеке бөлме", "👥 Бір бөлмеде (подселение)", "🤝 Бәрібір"]
        pref_rooms_ru = ["🛏 Тек жеке бөлме", "👥 Общая комната (подселение)", "🤝 Всё равно"]

        for i in range(target_additional):
            t_id = start_tid + i
            u_gender = random.choice([GENDER_MALE, GENDER_FEMALE])
            first_name = random.choice(MALE_NAMES if u_gender == GENDER_MALE else FEMALE_NAMES)
            username = f"{first_name.lower()}_{random.randint(100, 99999)}"
            u_age = random.randint(18, 34)
            u_lang = "kz" if random.random() < 0.65 else "ru"
            u_occ = random.choice(occupations_pool)
            has_apt = random.random() < 0.42  # ~42% have an apartment
            u_role = ROLE_BOTH if has_apt else ROLE_SEEKER

            u_city = random.choice(cities_pool)
            districts_list = list(CITY_DISTRICTS_LANDMARKS.get(u_city, {}).keys()) or ["Бостандыкский"]
            u_district = random.choice(districts_list)
            landmarks_list = CITY_DISTRICTS_LANDMARKS.get(u_city, {}).get(u_district, [f"{u_district} ауданы"])
            address_str = random.choice(landmarks_list)

            u_budget = random.choice(budgets_pool)
            u_budget_range = random.choice(budget_ranges_pool)
            u_move_date = random.choice(move_in_dates_kz if u_lang == "kz" else move_in_dates_ru)

            bio_text = random.choice(KZ_BIOS if u_lang == "kz" else RU_BIOS)
            ideal_text = random.choice(KZ_IDEALS if u_lang == "kz" else RU_IDEALS)

            new_user = User(
                telegram_id=t_id,
                username=username,
                first_name=first_name,
                age=u_age,
                gender=u_gender,
                occupation=u_occ,
                role=u_role,
                language=u_lang,
                is_verified=True,
            )
            session.add(new_user)
            await session.flush()

            rooms_str = random.choice(rooms_count_kz if u_lang == "kz" else rooms_count_ru) if has_apt else None
            room_type_str = random.choice(["separate", "shared"]) if has_apt else None
            neighbors_cnt = random.choice([1, 1, 2, 2, 3]) if has_apt else 1
            pref_room = None if has_apt else random.choice(pref_rooms_kz if u_lang == "kz" else pref_rooms_ru)

            new_profile = SeekerProfile(
                user_id=new_user.id,
                name=first_name,
                age=u_age,
                gender=u_gender,
                city=u_city,
                districts=[u_district],
                budget_max=u_budget,
                budget_range=u_budget_range,
                move_in_date=u_move_date,
                spots_needed=1,
                smoking="no" if random.random() < 0.8 else "yes",
                pets="no" if random.random() < 0.85 else "yes",
                occupation=u_occ,
                preferred_gender="any" if random.random() < 0.6 else u_gender,
                has_apartment=has_apt,
                apartment_address=address_str if has_apt else None,
                rooms_count=rooms_str,
                room_type=room_type_str,
                neighbors_needed=neighbors_cnt,
                preferred_room_type=pref_room or "any",
                ideal_neighbor_desc=ideal_text,
                about_self_desc=bio_text,
                neighbor_preferences=ideal_text,
                raw_bio=bio_text,
                neighbor_criteria={
                    "lifestyle": random.choice(["quiet", "active", "neutral"]),
                    "cleanliness": "important",
                    "parties": "undesirable",
                    "smoking": "non_smoker_preferred",
                },
                notifications_enabled=True,
                is_active=True,
                is_urgent=random.random() < 0.15,
            )
            session.add(new_profile)

            if has_apt:
                rooms_int = 2
                if rooms_str and ("1" in rooms_str):
                    rooms_int = 1
                elif rooms_str and ("3" in rooms_str):
                    rooms_int = 3
                elif rooms_str and ("4" in rooms_str):
                    rooms_int = 4

                listing = Listing(
                    owner_id=new_user.id,
                    city=u_city,
                    district=u_district,
                    address_landmark=address_str,
                    housing_type="room" if room_type_str == "separate" else "sharing",
                    total_rooms=rooms_int,
                    total_price=u_budget * neighbors_cnt,
                    price_per_person=u_budget,
                    utilities_included=random.choice([True, False]),
                    deposit_amount=random.choice([0, 20000, 30000, 50000]),
                    move_in_date=u_move_date,
                    available_places=neighbors_cnt,
                    occupied_places=1,
                    preferred_gender=new_profile.preferred_gender,
                    smoking_allowed=False,
                    pets_allowed=False,
                    conditions_description=f"{rooms_str}, {address_str}. {ideal_text}",
                    status=LISTING_STATUS_ACTIVE,
                    is_verified=True,
                    is_urgent=new_profile.is_urgent,
                    last_confirmed_at=datetime.utcnow(),
                )
                session.add(listing)
                created_listings.append(listing)

            created_users.append(new_user)

    await session.commit()
    return {
        "users_created": len(created_users),
        "listings_created": len(created_listings),
    }


async def wipe_database(session: AsyncSession):
    """Wipes test entities."""
    await session.execute(delete(Like))
    await session.execute(delete(Match))
    await session.execute(delete(Report))
    await session.execute(delete(SavedSearch))
    await session.execute(delete(Listing))
    await session.execute(delete(SeekerProfile))
    await session.execute(delete(User))
    await session.commit()


async def main():
    parser = argparse.ArgumentParser(description="Seed test users and listings for Korshi Tap")
    parser.add_argument("--count", type=int, default=500, help="Total number of seeds to generate (default: 500)")
    parser.add_argument("--city", type=str, default="all", help="City filter: all, Алматы, Астана, Шымкент")
    parser.add_argument("--wipe", action="store_true", help="Wipe database before generating seeds")
    args = parser.parse_args()

    print(f"🌱 Инициализация базы данных и сидирование {args.count} тестовых данных (город: {args.city})...")
    await init_db()
    async with async_session_factory() as session:
        if args.wipe:
            print("🧹 Очистка предыдущих тестовых данных...")
            await wipe_database(session)
        stats = await seed_database(session, count=args.count, city=args.city)
    print(f"✅ Успешно создано {stats['users_created']} пользователей и {stats['listings_created']} объявлений!")


if __name__ == "__main__":
    asyncio.run(main())
