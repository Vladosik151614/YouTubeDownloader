"""Helpers for playlists advertised by TikTok profile metadata."""


def extract_catalog_playlists(info: dict) -> list[dict]:
    """Return profile playlist/collection links when TikTok exposes them."""
    seen = set()
    result = []

    def visit(value):
        if isinstance(value, dict):
            title = value.get("mixName") or value.get("playlistName") or value.get("title")
            mix_id = value.get("mixId") or value.get("playlistId") or value.get("id")
            url = value.get("webpage_url") or value.get("url")
            if not url and mix_id and info.get("uploader_url"):
                url = f"{str(info['uploader_url']).rstrip('/')}/collection/{title or 'playlist'}-{mix_id}"
            if url and title and "tiktok.com/" in str(url).lower():
                key = str(url)
                if key not in seen:
                    seen.add(key)
                    result.append({"title": str(title), "url": key})
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for key in ("mixes", "playlists", "collections", "playlist"):
        visit(info.get(key))
    return result
