"""lattice.auth — scoped credential injection and permission checking."""

from lattice.auth.scopes import (
    CredentialStore,
    bind_credentials,
    get_credentials,
    require_role,
    require_scope,
    unbind_credentials,
)

__all__ = [
    "CredentialStore",
    "bind_credentials",
    "get_credentials",
    "require_role",
    "require_scope",
    "unbind_credentials",
]
