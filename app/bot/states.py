"""FSM states for KORSHI TAP Telegram Bot."""

from aiogram.fsm.state import State, StatesGroup


class QuestionnaireState(StatesGroup):
    waiting_language = State()          # Step 1: Язык
    waiting_welcome = State()           # Step 2: Приветствие («Давай начнём»)
    waiting_city = State()              # Step 3: Город (Алматы, Астана, Шымкент)
    waiting_name = State()              # Step 4: Имя
    waiting_gender = State()            # Step 5: Пол (Парень / Девушка)
    waiting_age = State()               # Step 6: Возраст
    waiting_occupation = State()        # Step 7: Работа / Учёба
    waiting_district = State()          # Step 8: Район
    waiting_neighbor_gender = State()   # Step 9: Какого соседа ищешь
    waiting_has_apartment = State()     # Step 10: Есть ли уже квартира
    # For users who have apartment:
    waiting_rooms_count = State()       # 1-комн, 2-комн, 3-комн, 4+ комн
    waiting_room_type = State()         # отдельная комната vs общая в одной комнате
    waiting_neighbors_needed = State()  # сколько соседей нужно (1, 2, 3+)
    waiting_apartment_address = State() # Адрес квартиры (если есть)
    # For users who do NOT have apartment:
    waiting_preferred_room_type = State() # отдельная комната vs в одной комнате vs всё равно
    # Common questions:
    waiting_budget = State()            # Step 11: Бюджет / стоимость с соседа
    waiting_custom_budget = State()     # Step 11b: Свой вариант бюджета
    waiting_move_in_date = State()      # Step 12: Когда хочешь заехать
    waiting_ideal_neighbor = State()    # Step 14: Каким должен быть идеальный сосед
    waiting_about_self = State()        # Step 15: Пару слов о себе


class OnboardingState(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_occupation = State()
    waiting_district = State()


class SeekerRegistration(StatesGroup):
    waiting_method = State()       # Steps vs Free text
    waiting_free_text = State()    # AI input
    waiting_name = State()
    waiting_age = State()
    waiting_gender = State()
    waiting_district = State()
    waiting_budget = State()
    waiting_date = State()
    waiting_housing_type = State()
    waiting_smoking = State()
    waiting_pets = State()
    waiting_occupation = State()
    waiting_confirm = State()


class OwnerListingCreation(StatesGroup):
    waiting_city = State()                   # Step 1: Астана, Алматы, Шымкент
    waiting_housing_type = State()           # Step 2: Квартира, Комната, Дом, Другое
    waiting_rooms_count = State()            # Step 3: Сколько комнат (1, 2, 3, 4+)
    waiting_price = State()                  # Step 4: Стоимость для одного соседа (в ₸)
    waiting_utilities = State()              # Step 5: Входят / Отдельно / Не знаю
    waiting_utilities_amount = State()       # Step 5b: Примерная сумма комуслуг (если отдельно)
    waiting_occupied_count = State()         # Step 6: Сколько уже проживает (1, 2, 3, 4+)
    waiting_roommates_needed = State()       # Step 7: Сколько соседей ищут (1, 2, 3, Другое)
    waiting_move_in_date = State()           # Step 8: Дата заселения
    waiting_custom_date = State()            # Step 8b: Ввод своей даты
    waiting_lease_duration = State()         # Step 9: Срок проживания (1-3 мес, 3-6 мес, и т.д.)
    waiting_gender_pref = State()            # Step 10: Кого ищут (Мужчину, Женщину, Не имеет значения)
    waiting_age_pref = State()               # Step 11: Возраст соседа (18-25, 20-30, Любой, или свой)
    waiting_custom_age = State()             # Step 11b: Ввод возраста текстом
    waiting_neighbor_description = State()   # Step 12: Главное — описание соседа своими словами
    waiting_district = State()               # District selection if city is Almaty (or skip)
    waiting_address = State()                # Address / landmark
    waiting_confirm = State()


class SwipeState(StatesGroup):
    browsing = State()
    district_exhausted = State()
    choosing_new_district = State()


class OwnerBrowseState(StatesGroup):
    browsing_seekers = State()


class ReportState(StatesGroup):
    waiting_reason = State()
    waiting_details = State()
