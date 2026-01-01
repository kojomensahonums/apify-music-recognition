import streamlit as st
import requests
import base64
import time

# -----------------------------
# Configuration
# -----------------------------
APIFY_ACTOR = "philip.boyedoku~apify-music-recognition"
APIFY_TOKEN = st.secrets["APIFY_TOKEN"]

APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/runs"
APIFY_RUN_STATUS_URL = "https://api.apify.com/v2/actor-runs"

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Music Recognition", layout="centered")

st.title("🎵 Music Recognition")
st.caption("Identify songs from audio using AudD")

uploaded_file = st.file_uploader(
    "Upload an audio file",
    type=["mp3", "wav", "m4a", "ogg"]
)

audio_url = st.text_input("Or paste an audio URL")

include_raw = st.checkbox("Include raw provider data (advanced)", value=False)

run_button = st.button("Recognize")

# -----------------------------
# Helpers
# -----------------------------
def run_actor(payload: dict) -> dict:
    resp = requests.post(
        f"{APIFY_RUN_URL}?waitForFinish=300",
        headers={
            "Authorization": f"Bearer {APIFY_TOKEN}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def wait_for_run(run_id: str):
    while True:
        status_resp = requests.get(
            f"{APIFY_RUN_STATUS_URL}/{run_id}",
            headers={"Authorization": f"Bearer {APIFY_TOKEN}"}
        )
        status_resp.raise_for_status()

        status = status_resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            return
        if status in ["FAILED", "ABORTED", "TIMED-OUT"]:
            raise RuntimeError(f"Actor failed with status: {status}")

        time.sleep(2)


def fetch_output(run_id: str) -> dict:
    # Step 1: Get run metadata to find the default KV store
    run_resp = requests.get(
        f"{APIFY_RUN_STATUS_URL}/{run_id}",
        headers={"Authorization": f"Bearer {APIFY_TOKEN}"}
    )
    run_resp.raise_for_status()
    run_data = run_resp.json()["data"]
    store_id = run_data["defaultKeyValueStoreId"]

    # Step 2: Fetch the 'OUTPUT' key from the KV store
    kv_resp = requests.get(
        f"https://api.apify.com/v2/key-value-stores/{store_id}/records/OUTPUT",
        headers={"Authorization": f"Bearer {APIFY_TOKEN}"}
    )
    kv_resp.raise_for_status()
    return kv_resp.json()


# -----------------------------
# Execution
# -----------------------------
if run_button:
    if not uploaded_file and not audio_url:
        st.error("Please provide an audio file or an audio URL.")
        st.stop()

    payload = {"include_raw": include_raw}

    if uploaded_file:
        audio_bytes = uploaded_file.read()
        payload["audio_b64"] = base64.b64encode(audio_bytes).decode("utf-8")
    else:
        payload["audio_url"] = audio_url

    with st.spinner("Recognizing music..."):
        try:
            run_id = run_actor(payload)
            wait_for_run(run_id)
            data = fetch_output(run_id)
        except Exception as e:
            st.error(str(e))
            st.stop()

    # -----------------------------
    # Render Results
    # -----------------------------
    summary = data.get("summary", {})
    track = summary.get("track", {})
    links = summary.get("links", {})
    confidence = summary.get("confidence", {})

    if not confidence.get("recognized"):
        st.warning("No song could be confidently identified.")
        st.stop()

    st.subheader("🎶 Track Identified")

    st.markdown(f"### {track.get('title', 'Unknown title')}")
    st.markdown(track.get("artist", "Unknown artist"))

    meta_cols = st.columns(3)
    meta_cols[0].metric("Album", track.get("album") or "—")
    meta_cols[1].metric("Release Date", track.get("release_date") or "—")
    meta_cols[2].metric("ISRC", track.get("isrc") or "—")

    link_cols = st.columns(3)
    if links.get("spotify"):
        link_cols[0].link_button("Open on Spotify", links["spotify"])
    if links.get("apple_music"):
        link_cols[1].link_button("Open on Apple Music", links["apple_music"])
    if links.get("song_page"):
        link_cols[2].link_button("Song Page", links["song_page"])

    # -----------------------------
    # Optional Details
    # -----------------------------
    with st.expander("Platform Details"):
        st.json(data.get("enrichment"))

    if data.get("warnings"):
        with st.expander("Warnings"):
            st.json(data.get("warnings"))

    if include_raw and data.get("raw"):
        with st.expander("Raw Provider Payload"):
            st.json(data.get("raw"))
