# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class MessageOut(BaseModel):
    message: str


class ResendVerifyIn(BaseModel):
    email: EmailStr


class VerifyOut(BaseModel):
    message: str