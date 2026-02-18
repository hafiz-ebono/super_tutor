import httpx


async def fetch_via_jina(url: str, api_key: str) -> str | None:
    """Returns text if successful, None if failed or content too short."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://r.jina.ai/{url}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "X-Return-Format": "text",
                },
            )
            resp.raise_for_status()
        text = resp.text.strip()
        return text if len(text) > 200 else None
    except Exception:
        return None
