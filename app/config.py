import os
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
    """
    api_key = api_key_header_val or api_key_query
    expected_api_key = os.getenv("API_KEY", "YOUR_SECRET_API_KEY_HERE")
    if not api_key or api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header or api_key query parameter",
        )
    return api_key
