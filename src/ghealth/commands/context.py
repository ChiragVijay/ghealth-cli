from collections.abc import Callable
from typing import Any

from ghealth.api import create_authenticated_client
from ghealth.auth.oauth import refresh_access_token, revoke_token
from ghealth.data_types import DataTypeRegistry
from ghealth.output import FormatEnum, console


class CliState:
    def __init__(
        self,
        output_format: FormatEnum = FormatEnum.TABLE,
        quiet: bool = False,
        debug: bool = False,
        no_color: bool = False,
        *,
        create_authenticated_client_func: Callable[[], Any] = create_authenticated_client,
        refresh_access_token_func: Callable[..., Any] = refresh_access_token,
        revoke_token_func: Callable[..., Any] = revoke_token,
    ) -> None:
        self.output_format = output_format
        self.quiet = quiet
        self.debug = debug
        self.no_color = no_color
        self.create_authenticated_client = create_authenticated_client_func
        self.refresh_access_token = refresh_access_token_func
        self.revoke_token = revoke_token_func

        if no_color:
            console.no_color = True

        self.registry = DataTypeRegistry()
