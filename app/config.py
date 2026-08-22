import os
import secrets
from typing import Optional
from fastapi import Security, HTTPException, status, Query
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key(
    api_key_header_val: Optional[str] = Security(api_key_header),
    api_key_query: Optional[str] = Query(None, alias="api_key")
) -> str:
    """
    Validates X-API-Key header or api_key query parameter against API_KEY environment variable.
    Enforces fail-closed behavior if API_KEY is unset or empty, and uses constant-time comparison.
    """
    expected_api_key = os.getenv("API_KEY")
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication misconfigured: API_KEY is missing.",
        )
    api_key = api_key_header_val or api_key_query
    if not api_key or not secrets.compare_digest(api_key, expected_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header or api_key query parameter",
        )
    return api_key


verify_api_key = get_api_key

