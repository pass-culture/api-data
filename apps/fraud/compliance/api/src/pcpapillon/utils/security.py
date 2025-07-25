from datetime import datetime, timedelta, timezone
from typing import Annotated, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pcpapillon.utils.data_model import TokenData, User, UserInDB
from pcpapillon.utils.env_vars import HASH_ALGORITHM, SECRET_KEY, users_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, db_password):
    return plain_password == db_password


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc)
    to_encode.update({"exp": expire})
    # Add your encoding logic here, such as signing the token with a secret key
    return to_encode
