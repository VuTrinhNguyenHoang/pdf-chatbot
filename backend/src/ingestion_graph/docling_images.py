import base64
import hashlib
import io
from dataclasses import dataclass

from docling.datamodel.document import PictureItem
from openai import OpenAI
from PIL import Image

from src.shared import settings

VISION_PROMPT = (
    "Describe this image concisely (2-4 sentences). Include: what the image shows, "
    "any visible text, numbers, or labels, and the insight it provides in a document "
    "context (e.g. trend of a chart, structure of a diagram, subject of a photo)."
)


@dataclass(frozen=True)
class ImagePreview:
    data: bytes | None
    mime_type: str | None
    status: str


def extract_image_preview(doc_items, dl_doc) -> ImagePreview:
    for item in doc_items:
        if not isinstance(item, PictureItem):
            continue
        try:
            pil_img = item.get_image(dl_doc)
            if pil_img is None:
                continue
            encoded = _encode_image_preview(pil_img)
            if len(encoded) > settings.MAX_IMAGE_PREVIEW_BYTES:
                return ImagePreview(None, None, "too_large")
            return ImagePreview(encoded, "image/jpeg", "extracted")
        except Exception:
            pass
    return ImagePreview(None, None, "missing")


def describe_image(
    image_preview: ImagePreview | None,
    vision: OpenAI | None,
    fallback: str,
    image_cache: dict[str, str],
    image_budget: dict[str, int],
) -> str:
    if vision is None or image_preview is None or image_preview.data is None:
        return _image_fallback(fallback)

    try:
        image_hash = hashlib.sha1(image_preview.data).hexdigest()
        if image_hash in image_cache:
            return image_cache[image_hash]
        if image_budget["remaining"] <= 0:
            return _image_fallback(fallback)

        image_budget["remaining"] -= 1
        b64 = base64.b64encode(image_preview.data).decode()
        resp = vision.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_preview.mime_type};base64,{b64}",
                        },
                    },
                ],
            }],
            max_tokens=300,
        )
        description = (resp.choices[0].message.content or "").strip()
        if description:
            image_cache[image_hash] = description
            return description
    except Exception:
        pass
    return _image_fallback(fallback)


def image_data_url(image_preview: ImagePreview | None) -> str | None:
    if (
        image_preview is None
        or image_preview.data is None
        or image_preview.mime_type is None
    ):
        return None
    b64 = base64.b64encode(image_preview.data).decode()
    return f"data:{image_preview.mime_type};base64,{b64}"


def _encode_image_preview(pil_img) -> bytes:
    image = pil_img.copy()
    image.thumbnail((settings.PDF_IMAGE_MAX_EDGE, settings.PDF_IMAGE_MAX_EDGE))
    if image.mode in {"RGBA", "LA"}:
        bg = Image.new("RGB", image.size, "white")
        bg.paste(image, mask=image.getchannel("A"))
        image = bg
    elif image.mode != "RGB":
        image = image.convert("RGB")

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _image_fallback(fallback: str) -> str:
    return fallback or "Image extracted from the document."
