from apify import Actor
import asyncio
import requests
import os
import base64
import tempfile
import json

AUDD_API_TOKEN = os.environ.get("AUDD_API_TOKEN")
AUDD_ENDPOINT = "https://api.audd.io/"

# -----------------------------
# Helpers
# -----------------------------
def call_audd(audio_url=None, audio_b64=None, return_sources="spotify,apple_music"):
    payload = {
        "api_token": AUDD_API_TOKEN,
        "return": return_sources,
    }

    files = None

    if audio_url:
        payload["url"] = audio_url
    elif audio_b64:
        audio_bytes = base64.b64decode(audio_b64)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.write(audio_bytes)
        tmp.close()
        files = {"file": open(tmp.name, "rb")}
    else:
        raise ValueError("No audio input provided")

    response = requests.post(
        AUDD_ENDPOINT,
        data=payload,
        files=files,
        timeout=60
    )
    response.raise_for_status()
    return response.json()


def normalize_audd_response(resp: dict) -> dict:
    result = resp.get("result") or {}

    spotify = result.get("spotify") or {}
    apple = result.get("apple_music") or {}

    summary = {
        "status": resp.get("status"),
        "track": {
            "title": result.get("title"),
            "artist": result.get("artist"),
            "album": result.get("album"),
            "release_date": result.get("release_date"),
            "label": result.get("label"),
            "duration_seconds": (
                spotify.get("duration_ms", 0) // 1000 if spotify else None
            ),
            "isrc": spotify.get("external_ids", {}).get("isrc")
        },
        "confidence": {
            "recognized": bool(result),
            "timecode": result.get("timecode")
        },
        "links": {
            "song_page": result.get("song_link"),
            "spotify": spotify.get("external_urls", {}).get("spotify"),
            "apple_music": apple.get("url")
        }
    }

    enrichment = {
        "spotify": {
            "popularity": spotify.get("popularity"),
            "explicit": spotify.get("explicit"),
            "preview_url": spotify.get("preview_url")
        } if spotify else None,
        "apple_music": {
            "has_lyrics": apple.get("hasLyrics"),
            "genre": apple.get("genreNames"),
            "preview_url": (
                apple.get("previews", [{}])[0].get("url")
                if apple.get("previews") else None
            )
        } if apple else None
    }

    return {
        "summary": summary,
        "enrichment": enrichment,
        "warnings": resp.get("warning")
    }


# -----------------------------
# Actor entry point
# -----------------------------
async def main():
    await Actor.init()

    input_data = await Actor.get_input() or {}
    Actor.log.info(f"Received input: {input_data.keys()}")

    audio_url = input_data.get("audio_url")
    audio_b64 = input_data.get("audio_b64")
    include_raw = input_data.get("include_raw", False)

    audd_response = call_audd(
        audio_url=audio_url,
        audio_b64=audio_b64
    )

    normalized = normalize_audd_response(audd_response)

    output = normalized
    if include_raw:
        output["raw"] = audd_response

    await Actor.set_output(output)


if __name__ == "__main__":
    asyncio.run(main())
