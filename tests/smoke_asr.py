"""未来在资源充足环境验证独立 ASR；不经过产品接口、不调用问数模型。"""

import argparse
import io
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path


def wav(seconds):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * int(16000 * seconds))
    return output.getvalue()


def post(base, data, mime):
    boundary = uuid.uuid4().hex
    prefix = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test.audio"\r\nContent-Type: {mime}\r\n\r\n'.encode()
    request = urllib.request.Request(
        f"{base.rstrip('/')}/transcribe",
        data=prefix + data + f"\r\n--{boundary}--\r\n".encode(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=160)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--expect-text", default="", help="实际转写应包含的词句，忽略标点")
    args = parser.parse_args()
    for title, audio, mime, expected in (
        ("empty recording", b"", "audio/wav", 422),
        ("oversized upload", b"x" * (10 * 1024 * 1024 + 1), "audio/wav", 413),
        ("corrupt audio", b"not audio", "audio/wav", 422),
        ("overlong recording", wav(61), "audio/wav", 422),
        ("silence", wav(1), "audio/wav", 422),
    ):
        code, body = post(args.base_url, audio, mime)
        assert code == expected, f"{title}: expected {expected}, received {code}: {body}"
        assert isinstance(body.get("detail"), str), f"{title}: missing error description"
        print(f"[PASS] {title}: HTTP {code}")
    if args.audio:
        mime = mimetypes.guess_type(args.audio.name)[0] or "audio/wav"
        began = time.monotonic()
        code, body = post(args.base_url, args.audio.read_bytes(), mime)
        assert code == 200 and isinstance(body.get("text"), str) and body["text"].strip(), body
        def normalize(value):
            return re.sub(r"[\W_]", "", value).lower()
        assert normalize(args.expect_text) in normalize(body["text"]), body
        print(f"[PASS] actual transcript ({time.monotonic() - began:.1f}s): {body['text']}")
    print("All speech checks passed.")


if __name__ == "__main__":
    main()
