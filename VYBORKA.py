import pandas as pd
import random
import string
from faker import Faker

# Инициализация Faker для генерации данных
fake = Faker()

# Функция для генерации случайного JWT токена
def generate_jwt():
    header = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    payload = ''.join(random.choices(string.ascii_letters + string.digits, k=15))
    signature = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
    return f"{header}.{payload}.{signature}"

# Функция для генерации случайной Cookie
def generate_cookie():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=30))

# Создание датасета
def create_dataset(num_records):
    data = {
        "UserName": [fake.user_name() for _ in range(num_records)],
        "FirstName": [fake.first_name() for _ in range(num_records)],  # Добавляем имя
        "LastName": [fake.last_name() for _ in range(num_records)],    # Добавляем фамилию
        "Email": [fake.email() for _ in range(num_records)],
        "Pswd": [fake.password() for _ in range(num_records)],
        "JWT": [generate_jwt() for _ in range(num_records)],
        "Cookie": [generate_cookie() for _ in range(num_records)]
    }
    return pd.DataFrame(data)

# Количество записей
num_records = 30000

# Генерация датасета
dataset = create_dataset(num_records)

# Сохранение в CSV файл
dataset.to_csv("user_data.csv", index=False)

print(f"Датасет с {num_records} записями успешно создан и сохранен в файл 'user_data.csv'")