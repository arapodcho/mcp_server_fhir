from dataclasses import dataclass
from typing import Literal, TypedDict
from datetime import datetime

@dataclass
class AuthConfig:
    clientId: str
    clientSecret: str
    tokenHost: str
    authorizePath: str
    authorizationMethod: Literal['body', 'header']
    tokenPath: str
    audience: str
    callbackURL: str
    scopes: str
    callbackPort: int

class Token(TypedDict):
    access_token: str
    refresh_token: str
    expires_at: datetime