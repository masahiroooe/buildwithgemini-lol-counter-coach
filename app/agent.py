import datetime
import difflib
import json
import os
import urllib.request
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor, UnsafeLocalCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from app.a2ui_utils import a2ui_callback

load_dotenv(Path(__file__).parent.parent / ".env")

# Hardcoded Project ID string & Bucket Name string required by Agent Engine / Agent Platform
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-9285eef2192b"
GCS_BUCKET_NAME = "qwiklabs-gcp-02-9285eef2192b-static-assets-bucket"
MEMORY_BANK_ID = "5910349438563385344"

# Comprehensive Katakana / English mapping for LoL Champions
CHAMPION_NAME_MAP = {
    # Mid / Top Assassin & Fighter
    "ヤスオ": "yasuo", "やすお": "yasuo", "ヤスヲ": "yasuo",
    "ヨネ": "yone", "よね": "yone",
    "ゼド": "zed", "ぜど": "zed", "ゼト": "zed",
    "アカリ": "akali", "あかり": "akali",
    "カタリナ": "katarina", "かたりな": "katarina",
    "ルブラン": "leblanc", "るぶらん": "leblanc",
    "サイラス": "sylas", "さいらす": "sylas",
    "エコー": "ekko", "えこー": "ekko",
    "フィズ": "fizz", "ふぃず": "fizz",
    "キヤナ": "qiyana", "きやな": "qiyana",
    "アーリ": "ahri", "あーり": "ahri",
    "ヴェックス": "vex", "べっくす": "vex", "ヴェックス": "vex",
    "シンドラ": "syndra", "しんどら": "syndra",
    "オリアナ": "orianna", "おりあな": "orianna",
    "ゾーイ": "zoe", "ぞーい": "zoe",
    "ビクター": "viktor", "ヴィクトル": "viktor", "びくたー": "viktor",
    "アニビア": "anivia", "あにびあ": "anivia",
    "ヴェールズ": "varus", "ヴァルス": "varus",
    "ヴェルコズ": "velkoz", "ヴェル＝コズ": "velkoz", "ベルコズ": "velkoz",
    "ラックス": "lux", "らっくす": "lux",
    "ゼラス": "xerath", "ぜらす": "xerath",
    "コーキ": "corki", "こーき": "corki",
    "ジェイス": "jayce", "じぇいす": "jayce",
    "ガリオ": "galio", "がりお": "galio",
    "ツイステッドフェイト": "tf", "tf": "twistedfate", "ツイステッド・フェイト": "twistedfate",
    
    # Top Lane Tanks & Bruisers
    "ダリウス": "darius", "だりうす": "darius", "ダリアス": "darius",
    "ガレン": "garen", "がれん": "garen",
    "アートロックス": "aatrox", "あーとろっくす": "aatrox",
    "パンテオン": "pantheon", "ぱんておん": "pantheon",
    "レネクトン": "renekton", "れねくとん": "renekton",
    "マルファイト": "malphite", "まるふぁいと": "malphite",
    "フィオラ": "fiora", "ふぃおら": "fiora",
    "イレリア": "irelia", "いれりあ": "irelia",
    "リベン": "riven", "りべん": "riven",
    "カミール": "camille", "かみーる": "camille",
    "オーン": "ornn", "おーん": "ornn",
    "サイオン": "sion", "さいおん": "sion",
    "ジャックス": "jax", "じゃっくす": "jax",
    "セト": "sett", "せと": "sett",
    "モルデカイザー": "mordekaiser", "もるでかいざー": "mordekaiser",
    "トリンダメア": "tryndamere", "とりんだめあ": "tryndamere",
    "ガングプランク": "gangplank", "がんぐぷらんく": "gangplank",
    "ポッピー": "poppy", "ぽっぴー": "poppy",
    "ナサス": "nasus", "なさす": "nasus",
    "クイン": "quinn", "くいん": "quinn",
    "ケーニッヒ": "kled", "クレッド": "kled",
    "ケネン": "kennen", "けねん": "kennen",

    # Jungle & ADC & Support
    "リーシン": "leesin", "りーしん": "leesin",
    "カ＝ジックス": "khazix", "カジックス": "khazix",
    "ヴィエゴ": "viego", "ゔぃえご": "viego",
    "ジンクス": "jinx", "じんくす": "jinx",
    "カイ＝サ": "kaisa", "カイサ": "kaisa", "かいさ": "kaisa",
    "ルシアン": "lucian", "るしあん": "lucian",
    "ヴェイン": "vayne", "べいん": "vayne",
    "エズリアル": "ezreal", "えずりある": "ezreal",
    "サムィラ": "samira", "サミラ": "samira",
    "スレッシュ": "thresh", "すれっしゅ": "thresh",
    "ブリッツクランク": "blitzcrank", "ぶりっつ": "blitzcrank",
    "レオナ": "leona", "れおな": "leona",
    "ノーチラス": "nautilus", "のーちらす": "nautilus",
    "スウェイン": "swain", "すうぇいん": "swain",
}


def hiragana_to_katakana(text: str) -> str:
    """Converts Hiragana characters in a string to Katakana."""
    return "".join(
        chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c
        for c in text
    )


_DDRAGON_CHAMP_CACHE: dict[str, str] = {}
_DDRAGON_PROPER_ID: dict[str, str] = {}


def _load_ddragon_champions() -> None:
    """Loads all ~170 official Japanese & English champion names from Riot Data Dragon."""
    if _DDRAGON_CHAMP_CACHE:
        return
    try:
        ver_req = urllib.request.Request(
            "https://ddragon.leagueoflegends.com/api/versions.json",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(ver_req, timeout=4) as resp:
            latest_version = json.loads(resp.read().decode())[0]
        ja_url = f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/ja_JP/champion.json"
        ja_req = urllib.request.Request(ja_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(ja_req, timeout=5) as resp:
            champ_dict = json.loads(resp.read().decode()).get("data", {})
        for champ_id, info in champ_dict.items():
            lower_id = champ_id.lower()
            _DDRAGON_PROPER_ID[lower_id] = champ_id
            ja_name = info.get("name", "").strip()
            if ja_name:
                _DDRAGON_CHAMP_CACHE[ja_name] = lower_id
                # Also register without middle dot '・' or '＝'
                clean_ja = ja_name.replace("・", "").replace("＝", "")
                _DDRAGON_CHAMP_CACHE[clean_ja] = lower_id
            _DDRAGON_CHAMP_CACHE[lower_id] = lower_id
    except Exception:
        pass


def resolve_champion_name(raw_name: str) -> str:
    """Fuzzy resolves champion names even with typos, Hiragana, or spelling variations."""
    _load_ddragon_champions()
    name = raw_name.strip()
    katakana_name = hiragana_to_katakana(name).replace("・", "").replace("＝", "")

    combined_map = {**_DDRAGON_CHAMP_CACHE, **CHAMPION_NAME_MAP}

    # 1. Exact match in Japanese map keys or English values
    for k, v in combined_map.items():
        k_clean = k.replace("・", "").replace("＝", "")
        if k == name or k_clean == katakana_name or v == name.lower():
            return v

    # 2. Substring match: only check if a known champion name (len >= 2) is contained in the input query
    best_sub = None
    best_len = 0
    for k, v in combined_map.items():
        k_clean = k.replace("・", "").replace("＝", "")
        if len(k_clean) >= 2 and (k_clean in name or k_clean in katakana_name):
            if len(k_clean) > best_len:
                best_len = len(k_clean)
                best_sub = v
    if best_sub:
        return best_sub

    # 3. Safe fuzzy match against Japanese Katakana keys (high cutoff to avoid false positives)
    matches = difflib.get_close_matches(
        katakana_name, list(combined_map.keys()), n=1, cutoff=0.75
    )
    if matches:
        return combined_map[matches[0]]

    # 4. Safe fuzzy match against English champion names
    eng_names = list(set(combined_map.values()))
    matches_eng = difflib.get_close_matches(name.lower(), eng_names, n=1, cutoff=0.75)
    if matches_eng:
        return matches_eng[0]

    return name.lower()


# Resolve Agent Engine resource name from deployment_metadata.json for Code Execution Sandbox
agent_engine_resource_name = None
metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
if metadata_path.exists():
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Could not read deployment_metadata.json: {e}")

_USE_VERTEXAI = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in ("true", "1")

if _USE_VERTEXAI and agent_engine_resource_name:
    code_executor = AgentEngineSandboxCodeExecutor(
        agent_engine_resource_name=agent_engine_resource_name
    )
else:
    code_executor = UnsafeLocalCodeExecutor()

# Local in-memory matchup fallback seeded from seed_firestore.py when Firestore ADC is unavailable
LOCAL_MATCHUPS: dict[str, dict] = {
    "yasuo": {
        "champion_name": "Yasuo",
        "lane": "Mid",
        "recommended_counters": ["Renekton", "Vex", "Malphite", "Pantheon"],
        "counter_reasons": "CC and burst champions overwhelm Yasuo's mobility. Renekton and Pantheon ignore Wind Wall and stun him instantly.",
        "do_not_pick": ["Lux", "Vel'Koz", "Ahri"],
        "do_not_pick_reasons": "Skillshot-reliant mages get blocked by Wind Wall and dashed on through minion waves.",
        "playstyle_tips": "Bait Wind Wall (26s early CD). Pop his passive shield before all-in. Avoid fighting inside full enemy minion waves.",
    },
    "zed": {
        "champion_name": "Zed",
        "lane": "Mid",
        "recommended_counters": ["Lissandra", "Garen", "Malphite"],
        "counter_reasons": "Lissandra R completely negates Death Mark. Point-and-click CC and armor shut down his assassination combos.",
        "do_not_pick": ["Veigar", "Xerath", "Ziggs"],
        "do_not_pick_reasons": "Immobile squishy mages are free targets for Zed's Death Mark at level 6.",
        "playstyle_tips": "Track his Shadow (W) cooldown. Rush Zhonya's Hourglass or Seeker's Armguard. Ping missing immediately.",
    },
    "darius": {
        "champion_name": "Darius",
        "lane": "Top",
        "recommended_counters": ["Vayne", "Quinn", "Wukong", "Yorick"],
        "counter_reasons": "Ranged kiting prevents Darius from landing Apprehend (E). Clones and pets block his targeted abilities.",
        "do_not_pick": ["Sion", "Nautilus", "Garen", "Nasus"],
        "do_not_pick_reasons": "Melee tanks give Darius free Hemorrhage 5-stacks and true damage ultimate resets.",
        "playstyle_tips": "Dodge the outer blade of Q to prevent his healing. Never take extended trades past 3 Hemorrhage stacks.",
    },
    "ahri": {
        "champion_name": "Ahri",
        "lane": "Mid",
        "recommended_counters": ["Yasuo", "Tristana", "Sylas"],
        "counter_reasons": "Yasuo Wind Wall blocks Charm (E) and Orb (Q). Tristana and Sylas out-trade her all-in damage early.",
        "do_not_pick": ["Lux", "Taliyah"],
        "do_not_pick_reasons": "Ahri's Spirit Rush (R) easily dodges slow skillshots and catches immobile mages.",
        "playstyle_tips": "Stand behind minions to block Charm. Trade when Charm is on cooldown (12s+).",
    },
    "pantheon": {
        "champion_name": "Pantheon",
        "lane": "Top / Mid / Support",
        "recommended_counters": ["Ornn", "Malphite", "Gragas", "Morgana"],
        "counter_reasons": "Tanks and displacement CC neutralize Pantheon's point-and-click stun (W) and Aegis Assault (E).",
        "do_not_pick": ["Yasuo", "Kassadin", "Twisted Fate"],
        "do_not_pick_reasons": "Point-and-click stun and Aegis Assault (E) block all frontal damage and interrupt squishy combos.",
        "playstyle_tips": "Respect his empowered W level 1-3 all-in. Wait out Aegis Assault (E) shield before throwing major damage skills.",
    },
}


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: after each turn, send the session to Memory Bank for extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def generate_champion_avatar(champion_name: str, tool_context: ToolContext = None) -> str:
    """Generates an anime-style champion avatar image for a League of Legends champion using gemini-3.1-flash-lite-image model,
    saves it as a session artifact for Playground UI, uploads it to Cloud Storage, and returns the public https URL.

    Args:
        champion_name: The name of the League of Legends champion (e.g., 'Yasuo', 'ヤスオ', 'やすお', 'Zed', 'ゼド', 'Darius', 'Ahri').
        tool_context: ToolContext provided by ADK framework.

    Returns:
        The public Cloud Storage HTTPS URL (https://storage.googleapis.com/<bucket>/<object>) of the generated image.
    """
    raw_name = champion_name.strip()
    eng_name = resolve_champion_name(raw_name).capitalize()

    try:
        if _USE_VERTEXAI:
            genai_client = genai.Client(
                vertexai=True,
                project=FIRESTORE_PROJECT_ID,
                location="global",
            )
        else:
            genai_client = genai.Client()

        prompt = (
            f"A dramatic, vibrant, high-quality League of Legends champion portrait avatar of {eng_name}, "
            "epic fantasy game art style, detailed character lighting, colorful background."
        )

        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if image_bytes:
            filename = f"{eng_name.lower()}_avatar.jpg"
            if tool_context:
                part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                tool_context.save_artifact(filename=filename, artifact=part)

            if _USE_VERTEXAI:
                storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
                bucket = storage_client.bucket(GCS_BUCKET_NAME)
                blob_name = f"avatars/{eng_name.lower()}_{uuid.uuid4().hex[:8]}.jpg"
                blob = bucket.blob(blob_name)
                blob.upload_from_string(image_bytes, content_type=mime_type)
                return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob.name}"
            else:
                avatars_dir = Path(__file__).parent.parent / "frontend" / "static" / "avatars"
                avatars_dir.mkdir(parents=True, exist_ok=True)
                local_name = f"{eng_name.lower()}_{uuid.uuid4().hex[:8]}.jpg"
                (avatars_dir / local_name).write_bytes(image_bytes)
                port = os.environ.get("PORT", "8080")
                return f"http://localhost:{port}/avatars/{local_name}"
    except Exception:
        pass

    return f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{eng_name}_0.jpg"


def get_champion_live_stats(champion_name: str) -> str:
    """Fetches real-time base stats and patch version for a LoL champion from Riot Games Data Dragon API.

    Args:
        champion_name: Name of the champion (e.g., 'Yasuo', 'ヤスオ', 'やすお', 'Zed', 'ゼド', 'Darius', 'Ahri').

    Returns:
        A summary string of live stats (HP, Armor, MR, Attack Damage, Attack Range) and patch version.
    """
    raw_name = champion_name.strip()
    resolved = resolve_champion_name(raw_name)
    eng_name = _DDRAGON_PROPER_ID.get(resolved, resolved.capitalize())

    try:
        ver_req = urllib.request.Request(
            "https://ddragon.leagueoflegends.com/api/versions.json",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(ver_req, timeout=5) as resp:
            versions = json.loads(resp.read().decode())
            latest_version = versions[0]
    except Exception:
        latest_version = "16.19.1"

    try:
        url = f"https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion/{eng_name}.json"
        champ_req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(champ_req, timeout=5) as resp:
            champ_data = json.loads(resp.read().decode())["data"][eng_name]

        stats = champ_data.get("stats", {})
        title = champ_data.get("title", "")
        resource = champ_data.get("partype", "Mana")

        return (
            f"Live Game Stats for {eng_name} ('{title}') - Patch {latest_version}:\n"
            f"• Resource: {resource}\n"
            f"• Base HP: {stats.get('hp')} (+{stats.get('hpperlevel')}/lvl)\n"
            f"• Base Armor: {stats.get('armor')} (+{stats.get('armorperlevel')}/lvl)\n"
            f"• Base Magic Resist: {stats.get('spellblock')} (+{stats.get('spellblockperlevel')}/lvl)\n"
            f"• Base Attack Damage: {stats.get('attackdamage')} (+{stats.get('attackdamageperlevel')}/lvl)\n"
            f"• Attack Range: {stats.get('attackrange')}\n"
            f"• Move Speed: {stats.get('movespeed')}"
        )
    except Exception as e:
        return f"Could not fetch live stats for champion '{champion_name}' ({eng_name}): {e}"


def get_matchup_info(champion_name: str) -> str:
    """Fetches counter picks, reasons, do-not-pick warnings, and playstyle tips for a given LoL champion from Firestore.

    Args:
        champion_name: The name of the opponent champion to look up (e.g., 'Yasuo', 'ヤスオ', 'やすお', 'Zed', 'ゼド', 'Darius', 'Ahri').

    Returns:
        A summary string of matchup details including recommended counters, reasons, do-not-pick champions, and playstyle tips.
    """
    raw_name = champion_name.strip()
    doc_id = resolve_champion_name(raw_name)
    data = None

    if _USE_VERTEXAI:
        try:
            db = get_firestore_client()
            doc_ref = db.collection("matchups").document(doc_id)
            doc = doc_ref.get()
            if not doc.exists:
                docs = list(db.collection("matchups").stream())
                for d in docs:
                    d_data = d.to_dict()
                    champ = d_data.get("champion_name", "").lower()
                    if raw_name.lower() in champ or champ in raw_name.lower() or d.id == doc_id:
                        doc = d
                        break
            if doc.exists:
                data = doc.to_dict()
        except Exception:
            data = None

    if data is None:
        data = LOCAL_MATCHUPS.get(doc_id)
        if data is None:
            for k, v in LOCAL_MATCHUPS.items():
                champ = v.get("champion_name", "").lower()
                if raw_name.lower() in champ or champ in raw_name.lower() or k == doc_id:
                    data = v
                    break

    if not data:
        return f"No matchup information found in database for champion '{champion_name}'."

    champ = data.get("champion_name", champion_name)
    lane = data.get("lane", "Unknown")
    counters = ", ".join(data.get("recommended_counters", []))
    counter_reasons = data.get("counter_reasons", "None provided.")
    do_not_pick = ", ".join(data.get("do_not_pick", []))
    do_not_pick_reasons = data.get("do_not_pick_reasons", "None provided.")
    tips = data.get("playstyle_tips", "None provided.")

    return (
        f"Matchup Info for {champ} ({lane} Lane):\n"
        f"• Recommended Counter Picks: {counters}\n"
        f"• Counter Reasons: {counter_reasons}\n"
        f"• DO NOT PICK (Hard Countered Champions): {do_not_pick}\n"
        f"• Do Not Pick Reasons: {do_not_pick_reasons}\n"
        f"• Playstyle & Strategy Tips: {tips}"
    )


def add_or_update_matchup(
    champion_name: str,
    lane: str,
    recommended_counters: list[str],
    counter_reasons: str,
    do_not_pick: list[str],
    do_not_pick_reasons: str,
    playstyle_tips: str,
) -> str:
    """Adds or updates matchup counter information for a League of Legends champion in Firestore.

    Args:
        champion_name: Name of the champion (e.g., 'Aatrox').
        lane: Typical lane for this matchup (e.g., 'Top', 'Mid', 'Bot').
        recommended_counters: List of champion names that counter this champion.
        counter_reasons: Explanation of why these counters are effective.
        do_not_pick: List of champion names that should NEVER be picked against this champion (hard counters).
        do_not_pick_reasons: Explanation of why these champions are bad picks.
        playstyle_tips: Playstyle advice and power spike strategy.

    Returns:
        A confirmation message indicating success.
    """
    doc_id = resolve_champion_name(champion_name)

    data = {
        "champion_name": champion_name,
        "lane": lane,
        "recommended_counters": recommended_counters,
        "counter_reasons": counter_reasons,
        "do_not_pick": do_not_pick,
        "do_not_pick_reasons": do_not_pick_reasons,
        "playstyle_tips": playstyle_tips,
    }

    LOCAL_MATCHUPS[doc_id] = data
    if _USE_VERTEXAI:
        try:
            db = get_firestore_client()
            db.collection("matchups").document(doc_id).set(data)
        except Exception:
            pass
    return f"Successfully saved matchup data for {champion_name} ({lane}) to database."


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are an elite League of Legends Pro & High-Elo Head Coach (LoL プロ・元プロ視点のカウンターコーチ). "
        "Your advice incorporates pro player knowledge (LCK, LPL, LJL, World Championship level insights from players like Faker, Chovy, ShowMaker, Rookie, Caps), "
        "wave management theory (slow push, freeze, crash, bounce), vision control, item power spike timing, and macro map movements. "
        "Your goal is to help players counter specific champions, pick the optimal champion match, and execute lane strategies like a professional."
    ),
    workflow_description=(
        "CHAMPION NAME RECOGNITION (カタカナ名・誤字・表記揺れの完全予測と正規化):\n"
        "- Users will type champion names in Katakana (e.g., 'ヤスオ', 'ゼド', 'カタリナ', 'レネクトン', 'ルシアン', 'カイサ', 'アカリ', 'フィオラ', 'リベン', 'カミール', 'ヴェルコズ', 'ベルコズ'), Hiragana, or English.\n"
        "- ALWAYS correctly resolve the champion name to its official English/Japanese name.\n"
        "- IMMEDIATELY call `get_matchup_info` and/or `get_champion_live_stats` when a champion name or matchup query is entered.\n\n"
        "PRO PLAYER & EX-PRO STRATEGY PERSPECTIVE (プロ・元プロ視点のアドバイス徹底):\n"
        "- Always frame advice from a Pro League of Legends Coach perspective (プロ・元プロのアナリスト・コーチ視点).\n"
        "- Explicitly mention wave management (ウェーブ管理: 3ウェーブ・スロープッシュ, タワー下フリーズ, リコールタイミング), cool-down punish (スキルクールダウンのスキを突く), item/level power spikes (レベル2ファーストタッチ, レベル6スパイク, コアアイテム完成時), and macro roams.\n"
        "- Example advice style: '【プロ・元プロ視点のアドバイス】ヤスオW(風の壁)はCD26秒です。プロ戦術ではWを使わせた瞬間に26秒間のウィンドウでジャングルを呼ぶかスロープッシュで圧をかけます。'\n\n"
        "STRICT DISTINCTION BETWEEN COUNTER PICKS AND DO-NOT-PICK (推奨カウンターとNG不利ピックの厳密な区別):\n"
        "- When a user asks how to counter Opponent X ('Xの対策' or 'Xのカウンター'):\n"
        "  1. `✅ 推奨カウンターピック（対Xに有利な自軍チャンプ）`: Champions YOU should pick to BEAT Opponent X.\n"
        "  2. `❌ 出してはいけない不利ピック（対Xに不利なNG自軍チャンプ）`: Champions YOU must NEVER pick against Opponent X because Opponent X hard-counters them.\n"
        "- NEVER put the same champion in both `推奨カウンターピック` and `出してはいけない不利ピック`, and NEVER confuse 'champions strong against X' with 'champions weak against X'.\n\n"
        "MEMORY & PERSONALIZATION (記憶・パーソナライズ):\n"
        "- Actively remember the user's main champion pool (よく使用するチャンピオン / メインチャンピオン), preferred lanes, and playstyle.\n"
        "- Whenever giving advice, tailor recommendations specifically to the user's remembered champion pool when relevant.\n\n"
        "Use `get_matchup_info` to retrieve counter data and bad matchup warnings from Firestore.\n"
        "Use `get_champion_live_stats` to fetch real-time base stats and patch version from Riot Games Data Dragon API.\n"
        "Use `generate_champion_avatar` when the user requests an image or avatar for a champion.\n"
        "Use Python code execution for complex calculations (damage output, gold efficiency, stat scaling).\n"
        "Always respond in Japanese ('日本語で') unless requested otherwise."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public http(s) "
        "URL for the image. Set the Image url to that exact link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'h3', 'body') for "
        "headings and emphasis. "
        "Follow this exact A2UI v0.8 JSON structure inside <a2ui-json>...</a2ui-json>:\n"
        "<a2ui-json>\n"
        "[\n"
        "  {\"beginRendering\": {\"surfaceId\": \"main\", \"root\": \"card_root\"}},\n"
        "  {\"surfaceUpdate\": {\"surfaceId\": \"main\", \"components\": [\n"
        "    {\"id\": \"card_root\", \"component\": {\"Card\": {\"child\": \"col_main\"}}},\n"
        "    {\"id\": \"col_main\", \"component\": {\"Column\": {\"children\": {\"explicitList\": [\"t_title\", \"t_counters\", \"t_bad\", \"t_tips\"]}}}},\n"
        "    {\"id\": \"t_title\", \"component\": {\"Text\": {\"text\": {\"literalString\": \"⚔️ [対面チャンピオン名] 対策ガイド\"}, \"usageHint\": \"h1\"}}},\n"
        "    {\"id\": \"t_counters\", \"component\": {\"Text\": {\"text\": {\"literalString\": \"✅ 推奨カウンター（有利ピック）: [有利なチャンプ名と理由]\"}, \"usageHint\": \"h3\"}}},\n"
        "    {\"id\": \"t_bad\", \"component\": {\"Text\": {\"text\": {\"literalString\": \"❌ 出してはいけないNGピック（不利対面）: [この相手にカモにされる出してはいけないチャンプ名と理由]\"}, \"usageHint\": \"body\"}}},\n"
        "    {\"id\": \"t_tips\", \"component\": {\"Text\": {\"text\": {\"literalString\": \"💡 【プロ・元プロ視点のアドバイス】...\"}, \"usageHint\": \"body\"}}}\n"
        "  ]}}\n"
        "]\n"
        "</a2ui-json>"
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview"),
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[get_matchup_info, add_or_update_matchup, get_champion_live_stats, generate_champion_avatar, PreloadMemoryTool()],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
