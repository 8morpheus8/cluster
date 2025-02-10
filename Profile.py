import os
import json
import base64
import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile  # Исправление 1: Добавлен импорт
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import create_engine, Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
import geckodriver_autoinstaller
from io import BytesIO
from typing import Dict, List
from pydantic import BaseModel, ValidationError

# Инициализация geckodriver
geckodriver_autoinstaller.install()

# Настройка логирования
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# Конфигурация
PROFILES_DIR = "firefox_profiles"
USERS_CSV = "users.csv"

# Инициализация шифрования
Base = declarative_base()
engine = create_engine('sqlite:///users.db')

class UserDB(Base):
    __tablename__ = 'users'
    Email = Column(String, primary_key=True)
    UserName = Column(String)
    Pswd = Column(Text)
    JWT = Column(Text)
    FirstName = Column(String)
    LastName = Column(String)

Base.metadata.create_all(engine)

# Загрузка переменных окружения
from dotenv import load_dotenv
load_dotenv()
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()

# Инициализация шифрования
cipher_suite = Fernet(
    base64.urlsafe_b64encode(
        PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"fixed_salt",
            iterations=480000,
        ).derive(ENCRYPTION_KEY)
    )
)

class SecureData:
    @staticmethod
    def encrypt(data: str) -> str:
        return cipher_suite.encrypt(data.encode()).decode()

    @staticmethod
    def decrypt(encrypted_data: str) -> str:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()

class BrowserProfile:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.profile_path = os.path.join(PROFILES_DIR, user_id)
        os.makedirs(self.profile_path, exist_ok=True)

    def get_driver(self):
        try:
            options = Options()
            # Исправление 2: Правильное создание профиля
            profile = FirefoxProfile(self.profile_path)
            options.profile = profile
            
            service = Service()
            driver = webdriver.Firefox(
                service=service,
                options=options
            )
            return driver
        except Exception as e:
            st.error(f"Ошибка запуска браузера: {str(e)}")
            return None

    def save_session_data(self, driver):
        try:
            cookies = driver.get_cookies()
            with open(os.path.join(self.profile_path, "cookies.json"), "w") as f:
                json.dump(cookies, f)
        except Exception as e:
            st.error(f"Ошибка сохранения сессии: {str(e)}")

class UserProfile:
    def __init__(self, user_data: dict):
        self.user_id = user_data["Email"]
        self.data = {
            "UserName": user_data.get("UserName", ""),
            "Email": user_data["Email"],
            "Pswd": SecureData.encrypt(user_data.get("Pswd", "")),
            "JWT": SecureData.encrypt(user_data.get("JWT", "")),
            "FirstName": user_data.get("FirstName", ""),
            "LastName": user_data.get("LastName", "")
        }
        self.browser_profile = BrowserProfile(self.user_id)

    def get_decrypted(self, field):
        try:
            return SecureData.decrypt(self.data[field])
        except KeyError:
            return ""
        except Exception as e:
            st.error(f"Ошибка дешифровки: {str(e)}")
            return ""

class ProfileManager:
    def __init__(self):
        Session = sessionmaker(bind=engine)
        self.session = Session()
        self.profiles = {}
        self.load_profiles()

    def load_profiles(self):
        try:
            users = self.session.query(UserDB).all()
            for user in users:
                self.profiles[user.Email] = UserProfile({
                    "Email": user.Email,
                    "UserName": user.UserName,
                    "Pswd": user.Pswd,
                    "JWT": user.JWT,
                    "FirstName": user.FirstName,
                    "LastName": user.LastName
                })
        except Exception as e:
            st.error(f"Ошибка загрузки профилей: {str(e)}")

    def add_profile(self, profile_data):
        try:
            new_user = UserDB(
                Email=profile_data["Email"],
                UserName=profile_data["UserName"],
                Pswd=SecureData.encrypt(profile_data["Pswd"]),
                JWT=SecureData.encrypt(profile_data.get("JWT", "")),
                FirstName=profile_data.get("FirstName", ""),
                LastName=profile_data.get("LastName", "")
            )
            self.session.add(new_user)
            self.session.commit()
            return True
        except Exception as e:
            st.error(f"Ошибка создания профиля: {str(e)}")
            return False

class UserProfileSchema(BaseModel):
    UserName: str
    Email: str
    Pswd: str
    JWT: str = ""
    FirstName: str = ""
    LastName: str = ""

class FileUploader:
    @staticmethod
    def parse_uploaded_file(uploaded_file):
        try:
            if uploaded_file.name.endswith('.csv'):
                return pd.read_csv(uploaded_file).to_dict('records')
            elif uploaded_file.name.endswith(('.xls', '.xlsx')):
                return pd.read_excel(uploaded_file).to_dict('records')
            elif uploaded_file.name.endswith('.json'):
                return pd.read_json(uploaded_file).to_dict('records')
            else:
                st.error("Неподдерживаемый формат файла")
                return []
        except Exception as e:
            st.error(f"Ошибка чтения файла: {str(e)}")
            return []

    @staticmethod
    def validate_data(records: List[Dict]):
        valid_profiles = []
        for idx, record in enumerate(records, 1):
            try:
                cleaned_data = {k: v if pd.notnull(v) else "" for k, v in record.items()}
                valid_profiles.append(UserProfileSchema(**cleaned_data))
            except ValidationError as e:
                st.error(f"Ошибка в строке {idx}: {str(e)}")
        return valid_profiles

def main():
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        password = st.text_input("Введите пароль администратора:", type="password")
        if password == os.getenv("ADMIN_PASSWORD"):
            st.session_state.auth = True
        else:
            st.error("Неверный пароль!")
            return

    st.set_page_config(page_title="User Profile Manager", layout="wide")
    
    if "manager" not in st.session_state:
        st.session_state.manager = ProfileManager()

    # Блок загрузки файлов
    with st.expander("📁 Загрузить пользователей из файла"):
        uploaded_file = st.file_uploader(
            "Выберите файл (CSV, Excel, JSON)",
            type=["csv", "xls", "xlsx", "json"]
        )

        if uploaded_file:
            raw_data = FileUploader.parse_uploaded_file(uploaded_file)
            profiles = FileUploader.validate_data(raw_data)

            if profiles:
                preview_df = pd.DataFrame([p.dict() for p in profiles])
                st.dataframe(preview_df.head(3))

                selected_emails = st.multiselect(
                    "Выберите пользователей:",
                    options=[p.Email for p in profiles]
                )

                if st.button("Сохранить выбранных"):
                    for profile in profiles:
                        if profile.Email in selected_emails:
                            st.session_state.manager.add_profile(profile.dict())
                    st.success("Данные сохранены!")

    with st.sidebar:
        st.header("Управление профилями")
        selected_user = st.selectbox(
            "Выберите профиль",
            options=["Новый профиль"] + list(st.session_state.manager.profiles.keys())
        )

    if selected_user == "Новый профиль":
        with st.form("Новый профиль"):
            st.write("### Создать новый профиль")
            new_data = {
                "UserName": st.text_input("Логин"),
                "Email": st.text_input("Email"),
                "Pswd": st.text_input("Пароль", type="password"),
                "JWT": st.text_input("JWT токен"),
                "FirstName": st.text_input("Имя"),
                "LastName": st.text_input("Фамилия")
            }
            if st.form_submit_button("Создать"):
                if st.session_state.manager.add_profile(new_data):
                    st.success("Профиль создан!")
                    st.rerun()

    else:
        profile = st.session_state.manager.profiles[selected_user]
        
        with st.form("Редактирование профиля"):
            st.write("### Редактирование профиля")
            updated_data = {
                "UserName": st.text_input("Логин", value=profile.data["UserName"]),
                "Email": st.text_input("Email", value=profile.data["Email"]),
                "Pswd": st.text_input("Пароль", value=profile.get_decrypted("Pswd"), type="password"),
                "JWT": st.text_input("JWT токен", value=profile.get_decrypted("JWT")),
                "FirstName": st.text_input("Имя", value=profile.data["FirstName"]),
                "LastName": st.text_input("Фамилия", value=profile.data["LastName"])
            }
            
            if st.form_submit_button("Сохранить изменения"):
                try:
                    profile.data.update({
                        "UserName": updated_data["UserName"],
                        "Email": updated_data["Email"],
                        "Pswd": SecureData.encrypt(updated_data["Pswd"]),
                        "JWT": SecureData.encrypt(updated_data["JWT"]),
                        "FirstName": updated_data["FirstName"],
                        "LastName": updated_data["LastName"]
                    })
                    st.session_state.manager.session.commit()
                    st.success("Изменения сохранены!")
                except Exception as e:
                    st.error(f"Ошибка: {str(e)}")

        if st.button("Запустить браузер"):
            driver = None
            try:
                driver = profile.browser_profile.get_driver()
                driver.get("https://example.com")
                
                cookies_file = os.path.join(profile.browser_profile.profile_path, "cookies.json")
                if os.path.exists(cookies_file):
                    with open(cookies_file) as f:
                        cookies = json.load(f)
                        driver.delete_all_cookies()
                        for cookie in cookies:
                            driver.add_cookie(cookie)
                        driver.refresh()
                
                st.success(f"Браузер запущен для {profile.data['Email']}")
            except Exception as e:
                st.error(f"Ошибка: {str(e)}")        
            finally:
                if driver:              
                    profile.browser_profile.save_session_data(driver)
                    driver.quit()

if __name__ == "__main__":
    main()