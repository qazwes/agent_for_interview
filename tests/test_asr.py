"""预留 ASR 的资源和错误处理回归；不加载真实模型。"""

import asyncio
import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile

spec = importlib.util.spec_from_file_location(
    "asr_server_test", Path(__file__).parents[1] / "docker" / "asr" / "server.py"
)
server = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = server
spec.loader.exec_module(server)


def upload(data=b"audio"):
    return UploadFile(io.BytesIO(data), filename="test.audio")


def test_cancelled_request_keeps_model_lock_until_worker_finishes(monkeypatch):
    async def run():
        started, finish, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def slow(file, model):
            started.set()
            await finish.wait()
            await file.close()
            cleaned.set()
            return server.Transcript(text="已识别")
        monkeypatch.setattr(server, "transcribe_audio", slow)
        server.app.state.model = object()
        server.app.state.busy = False
        file = upload()
        request = asyncio.create_task(server.transcribe(file))
        await started.wait()
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert server.app.state.busy is True
        rejected = upload()
        with pytest.raises(HTTPException) as error:
            await server.transcribe(rejected)
        assert error.value.status_code == 429
        assert rejected.file.closed
        finish.set()
        await cleaned.wait()
        await asyncio.sleep(0)
        assert server.app.state.busy is False
        assert file.file.closed
    asyncio.run(run())


@pytest.mark.parametrize("case,code", [("empty", 422), ("large", 413), ("long", 422), ("silence", 422), ("corrupt", 422), ("valid", None)])
def test_audio_limits_and_temporary_files_are_cleaned(monkeypatch, case, code):
    monkeypatch.setattr(server, "MAX_BYTES", 5)
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(info=lambda path: SimpleNamespace(duration=61 if case == "long" else 1)))
    paths = []
    async def decode(source, target):
        paths.extend([source, target])
        if case == "corrupt":
            raise HTTPException(422, "音频无法解码")
        target.write_bytes(b"wav")
    monkeypatch.setattr(server, "decode_audio", decode)
    model = SimpleNamespace(generate=lambda **kwargs: [] if case == "silence" else [{"text": "查询北京收入"}])
    async def run():
        file = upload(b"" if case == "empty" else b"123456" if case == "large" else b"audio")
        if code:
            with pytest.raises(HTTPException) as error:
                await server.transcribe_audio(file, model)
            assert error.value.status_code == code
        else:
            assert (await server.transcribe_audio(file, model)).text == "查询北京收入"
        assert file.file.closed
        assert all(not path.exists() and not path.parent.exists() for path in paths)
    asyncio.run(run())
