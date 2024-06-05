from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.logger import logger
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_versioning import version
from main import custom_logger, setup_trace
from pcpapillon.utils.data_model import (
    Token,
)
from pcpapillon.utils.env_vars import (
    LOGIN_TOKEN_EXPIRATION,
    users_db,
)
from pcpapillon.utils.security import (
    authenticate_user,
    create_access_token,
)
from typing_extensions import Annotated

main_router = APIRouter(tags=["main"])


@main_router.get("/")
def read_root():
    custom_logger.info("Auth user welcome to : Validation API test")
    return "Auth user welcome to : Validation API test"


@main_router.get("/health/api")
def read_health():
    return "OK"


@main_router.post("/token", response_model=Token, dependencies=[Depends(setup_trace)])
@version(1, 0)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    log_extra_data = {"user": form_data.username}
    custom_logger.info("Requesting access token", extra=log_extra_data)
    user = authenticate_user(users_db, form_data.username, form_data.password)
    if not user:
        exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        logger.info("Failed authentification", extra=log_extra_data)
        raise exception
    access_token_expires = timedelta(minutes=LOGIN_TOKEN_EXPIRATION)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    custom_logger.info("Successful authentification", extra=log_extra_data)
    return {"access_token": access_token, "token_type": "bearer"}
