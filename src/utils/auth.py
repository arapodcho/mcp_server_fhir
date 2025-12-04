import asyncio
import base64
import os
import time
import webbrowser
import uuid
from typing import Optional, Dict, Any, TypeVar, Callable, Awaitable
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from aiohttp import web

from .auth_config import AuthConfig

T = TypeVar("T")

class Token(Dict):
    access_token: str
    refresh_token: str
    expires_at: datetime

class Auth:
    def __init__(self, auth_config: AuthConfig):
        self.auth_config = auth_config
        self.auth_state: Dict[str, asyncio.Future] = {}
        self.token: Optional[Token] = None
        self.server_app = web.Application()
        self.server_runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._server_started = False

    async def initialize(self):
        """Starts the callback server asynchronously."""
        if not self._server_started:
            await self._setup_callback_server()
            self._server_started = True

    async def _setup_callback_server(self):
        self.server_app.router.add_get('/oauth/callback', self._handle_callback)
        self.server_app.router.add_get('/health', self._handle_health)

        self.server_runner = web.AppRunner(self.server_app)
        await self.server_runner.setup()
        
        port = self.auth_config.callbackPort
        self.site = web.TCPSite(self.server_runner, 'localhost', port)
        try:
            await self.site.start()
            # print(f"OAuth callback server listening at http://localhost:{port}")
        except OSError as e:
            if "Address already in use" in str(e):
                 raise RuntimeError(f"Port {port} is already in use")
            raise e

    async def _handle_health(self, request):
        return web.Response(text="OAuth callback server is running")

    async def _handle_callback(self, request):
        code = request.query.get('code')
        state = request.query.get('state')
        error = request.query.get('error')

        future = self.auth_state.get(state)

        if not future:
            print(f"No state handler found for state: {state}")
            return web.Response(status=400, text="Invalid state")

        try:
            if error:
                future.set_exception(Exception(f"OAuth Error: {error}"))
            else:
                token = await self._exchange_code_for_token(code)
                self.token = token
                future.set_result(True)
            
            # Serve success page
            try:
                # Assuming auth-success.html is in the same directory as this file
                current_dir = os.path.dirname(os.path.abspath(__file__))
                success_file = os.path.join(current_dir, 'auth-success.html')
                if os.path.exists(success_file):
                    with open(success_file, 'r', encoding='utf-8') as f:
                        return web.Response(text=f.read(), content_type='text/html')
                else:
                    return web.Response(text="Authentication successful! You can close this window.")
            except Exception as e:
                print(f"Error serving success template: {e}")
                return web.Response(text="Authentication successful! You can close this window.")

        except Exception as e:
            if not future.done():
                future.set_exception(e)
            return web.Response(status=500, text=f"Authentication failed: {str(e)}")
        finally:
            self.auth_state.pop(state, None)

    async def _exchange_code_for_token(self, code: str) -> Token:
        params = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.auth_config.callbackURL
        }

        # Add credentials based on auth method
        if self.auth_config.authorizationMethod == 'body':
            params['client_id'] = self.auth_config.clientId
            params['client_secret'] = self.auth_config.clientSecret

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        if self.auth_config.authorizationMethod == 'header':
            credentials = f"{self.auth_config.clientId}:{self.auth_config.clientSecret}"
            encoded_creds = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded_creds}"

        token_url = f"{self.auth_config.tokenHost}{self.auth_config.tokenPath}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(token_url, data=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                return {
                    "access_token": data['access_token'],
                    "refresh_token": data.get('refresh_token', ''), # Some flows might not return refresh token
                    "expires_at": datetime.now() + timedelta(seconds=data.get('expires_in', 3600))
                }
            except Exception as e:
                raise Exception(f"Error getting token: {str(e)}. URL: {token_url}")

    async def _refresh_token(self):
        if not self.token or not self.token.get('refresh_token'):
            raise Exception('No refresh token available')

        token_url = f"{self.auth_config.tokenHost}{self.auth_config.tokenPath}"
        
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.token['refresh_token'],
            'client_id': self.auth_config.clientId,
            'client_secret': self.auth_config.clientSecret
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(token_url, data=params)
                response.raise_for_status()
                data = response.json()

                self.token = {
                    "access_token": data['access_token'],
                    "refresh_token": data.get('refresh_token', self.token['refresh_token']),
                    "expires_at": datetime.now() + timedelta(seconds=data.get('expires_in', 3600))
                }
            except Exception as e:
                print(f"Token refresh failed: {e}")
                self.token = None
                raise e

    def _is_token_expired(self) -> bool:
        if not self.token or not self.token.get('expires_at'):
            return True
        # Add 5 minute buffer
        return self.token['expires_at'] - timedelta(minutes=5) < datetime.now()

    async def ensure_valid_token(self) -> str:
        if not self.token:
            raise Exception('No token available')

        if self._is_token_expired():
            await self._refresh_token()

        return self.token['access_token']

    def _open_browser(self, url: str):
        # Python's webbrowser module handles platform differences automatically
        webbrowser.open(url)

    async def execute_with_auth(self, operation: Callable[[], Awaitable[T]]) -> T:
        await self.initialize() # Ensure server is running

        try:
            if self.token:
                await self.ensure_valid_token()
                return await operation()
            
            # Need to authenticate first
            state = str(uuid.uuid4())
            future = asyncio.get_running_loop().create_future()
            self.auth_state[state] = future

            # Construct Auth URL
            params = {
                'response_type': 'code',
                'client_id': self.auth_config.clientId,
                'redirect_uri': self.auth_config.callbackURL,
                'scope': self.auth_config.scopes,
                'state': state,
                'aud': self.auth_config.audience
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            query_string = urlencode(params)
            base_url = f"{self.auth_config.tokenHost}{self.auth_config.authorizePath}"
            # Ensure base_url doesn't double slash if tokenHost has trailing slash
            # (Assuming authConfig handles this or simple concatenation)
            # A safer join:
            if not base_url.startswith('http'):
                 base_url = f"https://{base_url}" # Fallback
                 
            authorization_uri = f"{base_url}?{query_string}"

            self._open_browser(authorization_uri)

            # Wait for callback
            await future
            
            # Now run the operation
            return await operation()

        except Exception as e:
            if "refresh" in str(e).lower():
                self.token = None
                return await self.execute_with_auth(operation)
            raise e

    async def cleanup(self):
        if self.server_runner:
            await self.server_runner.cleanup()