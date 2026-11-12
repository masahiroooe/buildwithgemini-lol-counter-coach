"""Make an ADK agent's A2UI output render in the ADK dev UI (`adk web`) and Hextech Frontend.

Includes automatic healing for common LLM A2UI JSON quirks (prose around JSON,
`children` as a flat list instead of `{"explicitList": [...]}`, `text` as a raw
string instead of `{"literalString": ...}`, missing `beginRendering`, or
dangling child component IDs) so the UI always renders a clean card.
"""

import json
import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# A2UI message kinds this renderer understands (v0.8).
_A2UI_KEYS = ("beginRendering", "surfaceUpdate", "dataModelUpdate", "deleteSurface")

# Tags the model may wrap around its output (its own render wrapper, or the SDK's).
_TAG_RE = re.compile(r"</?(?:a2a_datapart_json|a2ui-json)>")
_A2UI_BLOCK_RE = re.compile(r"<a2ui-json>(.*?)</a2ui-json>", re.DOTALL)

_HTTP_URL_RE = re.compile(r"^https?://", re.I)
_IMAGE_NOTE = "画像を生成しました（Artifacts パネルまたはスプラッシュアートを参照してください）。"


def _wrap_a2ui_part(a2ui_message: dict) -> types.Part:
    """Wrap a single A2UI message for rendering in adk web / frontend."""
    datapart_json = json.dumps(
        {
            "kind": "data",
            "metadata": {"mimeType": "application/json+a2ui"},
            "data": a2ui_message,
        },
        ensure_ascii=False,
    )
    blob_data = (
        b"<a2a_datapart_json>" + datapart_json.encode("utf-8") + b"</a2a_datapart_json>"
    )
    return types.Part(
        inline_data=types.Blob(
            data=blob_data,
            mime_type="text/plain",
        )
    )


def _iter_json_values(text: str):
    """Yield top-level JSON values from a string that may contain prose or tags."""
    decoder = json.JSONDecoder()
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx] not in "{[":
            idx += 1
        if idx >= n:
            break
        try:
            value, end = decoder.raw_decode(text, idx)
            yield value
            idx = end
        except json.JSONDecodeError:
            idx += 1


def _extract_a2ui_messages(text: str) -> list[dict]:
    """Pull A2UI messages out of the model's raw text output."""
    blocks = _A2UI_BLOCK_RE.findall(text)
    candidates = blocks if blocks else [text]

    values: list = []
    for chunk in candidates:
        chunk = chunk.strip()
        if chunk.startswith("```"):
            chunk = chunk.split("\n", 1)[-1]
            if chunk.endswith("```"):
                chunk = chunk[:-3]
        chunk = _TAG_RE.sub("", chunk).strip()
        for value in _iter_json_values(chunk):
            if isinstance(value, list):
                values.extend(value)
            else:
                values.append(value)

    messages: list[dict] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        inner = value.get("data")
        if isinstance(inner, dict) and any(k in inner for k in _A2UI_KEYS):
            messages.append(inner)
        elif any(k in value for k in _A2UI_KEYS):
            messages.append(value)
    return messages


def _heal_a2ui_messages(messages: list[dict]) -> list[dict]:
    """Normalize and auto-heal A2UI component trees so they are always renderable."""
    all_ids: set[str] = set()
    first_comp_id: str | None = None
    surface_id = "main"

    # Pass 1: Normalize component properties and collect all defined component IDs
    for m in messages:
        br = m.get("beginRendering")
        if isinstance(br, dict) and isinstance(br.get("surfaceId"), str):
            surface_id = br["surfaceId"]
        su = m.get("surfaceUpdate")
        if not isinstance(su, dict):
            continue
        if isinstance(su.get("surfaceId"), str):
            surface_id = su["surfaceId"]
        comps = su.get("components")
        if not isinstance(comps, list):
            continue
        for c in comps:
            if not isinstance(c, dict):
                continue
            cid = c.get("id")
            if isinstance(cid, str) and cid:
                all_ids.add(cid)
                if first_comp_id is None:
                    first_comp_id = cid
            comp = c.get("component")
            if not isinstance(comp, dict):
                continue
            for kind, spec in list(comp.items()):
                if not isinstance(spec, dict):
                    continue
                # Normalize children list -> {"explicitList": [...]}
                children = spec.get("children")
                if isinstance(children, list):
                    spec["children"] = {
                        "explicitList": [x for x in children if isinstance(x, str)]
                    }
                # Normalize Text.text string -> {"literalString": ...}
                if kind == "Text":
                    t_val = spec.get("text")
                    if isinstance(t_val, str):
                        spec["text"] = {"literalString": t_val}
                # Normalize Image.url string -> {"literalString": ...}
                if kind == "Image":
                    u_val = spec.get("url")
                    if isinstance(u_val, str):
                        spec["url"] = {"literalString": u_val}

    # Pass 2: Prune dangling child references so missing IDs never blank the tree
    for m in messages:
        su = m.get("surfaceUpdate")
        if not isinstance(su, dict) or not isinstance(su.get("components"), list):
            continue
        for c in su["components"]:
            if not isinstance(c, dict) or not isinstance(c.get("component"), dict):
                continue
            for spec in c["component"].values():
                if not isinstance(spec, dict):
                    continue
                if isinstance(spec.get("child"), str) and spec["child"] not in all_ids:
                    del spec["child"]
                children = spec.get("children")
                if isinstance(children, dict) and isinstance(
                    children.get("explicitList"), list
                ):
                    children["explicitList"] = [
                        cid
                        for cid in children["explicitList"]
                        if isinstance(cid, str) and cid in all_ids
                    ]

    # Pass 3: Ensure a valid beginRendering pointing to an existing root ID
    has_begin = False
    for m in messages:
        br = m.get("beginRendering")
        if isinstance(br, dict):
            has_begin = True
            if not isinstance(br.get("root"), str) or br["root"] not in all_ids:
                if first_comp_id:
                    br["root"] = first_comp_id
            if "surfaceId" not in br:
                br["surfaceId"] = surface_id

    if not has_begin and first_comp_id:
        messages.insert(
            0,
            {
                "beginRendering": {
                    "surfaceId": surface_id,
                    "root": first_comp_id,
                }
            },
        )

    return messages


def _build_fallback_card(raw_text: str) -> list[dict]:
    """Build a valid A2UI Card from raw text or partial JSON when JSON is truncated."""
    # Extract any literalString values if partial JSON was emitted
    literals = re.findall(r'"literalString"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_text)
    if literals:
        lines = [
             bytes(s, "utf-8").decode("unicode_escape", errors="replace")
            if "\\u" in s or "\\n" in s
            else s
            for s in literals
        ]
    else:
        cleaned = _TAG_RE.sub("", raw_text).strip()
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

    if not lines:
        lines = ["回答を生成しました。もう一度質問してください。"]

    text_comps = []
    text_ids = []
    for i, line in enumerate(lines[:12]):
        tid = f"text_{i}"
        text_ids.append(tid)
        hint = "h2" if i == 0 else "body"
        text_comps.append(
            {
                "id": tid,
                "component": {
                    "Text": {
                        "text": {"literalString": line},
                        "usageHint": hint,
                    }
                },
            }
        )

    components = [
        {
            "id": "root_card",
            "component": {"Card": {"child": "main_col"}},
        },
        {
            "id": "main_col",
            "component": {"Column": {"children": {"explicitList": text_ids}}},
        },
        *text_comps,
    ]
    return [
        {"beginRendering": {"surfaceId": "main", "root": "root_card"}},
        {"surfaceUpdate": {"surfaceId": "main", "components": components}},
    ]


def _sanitize_image_components(messages: list[dict]) -> None:
    """Replace un-fetchable <Image> components with a short <Text> note, in place."""
    for m in messages:
        surface = m.get("surfaceUpdate")
        if not isinstance(surface, dict):
            continue
        for c in surface.get("components") or []:
            if not isinstance(c, dict):
                continue
            comp = c.get("component")
            if not isinstance(comp, dict) or "Image" not in comp:
                continue
            img = comp.get("Image")
            url = img.get("url") if isinstance(img, dict) else None
            literal = url.get("literalString") if isinstance(url, dict) else None
            if isinstance(literal, str) and _HTTP_URL_RE.match(literal):
                continue
            c["component"] = {
                "Text": {
                    "text": {"literalString": _IMAGE_NOTE},
                    "usageHint": "body",
                }
            }


def _component_ids_and_refs(components: list) -> tuple[set, set]:
    """Return (defined ids, referenced child ids) for a component list."""
    ids: set = set()
    refs: set = set()
    for c in components:
        if not isinstance(c, dict):
            continue
        if "id" in c:
            ids.add(c["id"])
        comp = c.get("component")
        if not isinstance(comp, dict):
            continue
        for spec in comp.values():
            if not isinstance(spec, dict):
                continue
            if isinstance(spec.get("child"), str):
                refs.add(spec["child"])
            children = spec.get("children")
            if isinstance(children, dict):
                for cid in children.get("explicitList") or []:
                    if isinstance(cid, str):
                        refs.add(cid)
    return ids, refs


def _surface_is_renderable(messages: list[dict]) -> bool:
    """True only if the messages form a surface adk web / frontend can draw."""
    all_ids: set = set()
    all_refs: set = set()
    roots: list = []
    has_body = False
    for m in messages:
        if "dataModelUpdate" in m or "deleteSurface" in m:
            return True
        br = m.get("beginRendering")
        if isinstance(br, dict) and isinstance(br.get("root"), str):
            roots.append(br["root"])
        su = m.get("surfaceUpdate")
        if isinstance(su, dict) and su.get("components"):
            has_body = True
            ids, refs = _component_ids_and_refs(su["components"])
            all_ids |= ids
            all_refs |= refs
    if not has_body:
        return False
    if any(root not in all_ids for root in roots):
        return False
    if all_refs - all_ids:
        return False
    return True


def a2ui_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Convert A2UI JSON in text output to rendered components."""
    if not llm_response.content or not llm_response.content.parts:
        return None

    for part in llm_response.content.parts:
        text = (part.text or "").strip()
        if not text:
            continue
        if not any(k in text for k in _A2UI_KEYS):
            continue

        messages = _extract_a2ui_messages(text)
        if messages:
            messages = _heal_a2ui_messages(messages)
            _sanitize_image_components(messages)

        if not messages or not _surface_is_renderable(messages):
            messages = _build_fallback_card(text)

        new_parts = [_wrap_a2ui_part(m) for m in messages]
        return LlmResponse(
            content=types.Content(role="model", parts=new_parts),
            custom_metadata={"a2a:response": "true"},
        )

    return None
