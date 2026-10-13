"""独立 CPU 语音服务：模型启动时加载一次，音频仅在临时目录中处理。"""

import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")
MAX_BYTES = int(os.getenv("ASR_MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_SECONDS = int(os.getenv("ASR_MAX_SECONDS", "60"))
THREADS = int(os.getenv("ASR_CPU_THREADS", "2"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    from funasr import AutoModel

    logger.info("Loading Chinese ASR, VAD and punctuation models on CPU")
    if not all((Path("/models") / directory / "model.pt").is_file() for directory in ("paraformer", "vad", "punctuation")):
        raise RuntimeError("ASR models missing; run the asr-model-download tool service first")
    app.state.model = await asyncio.to_thread(
        AutoModel,
        model="/models/paraformer",
        vad_model="/models/vad",
        punc_model="/models/punctuation",
        device="cpu",
        ncpu=THREADS,
        disable_update=True,
        disable_pbar=True,
    )
    app.state.busy = False
    logger.info("ASR models ready")
    yield
    app.state.model = None


app = FastAPI(lifespan=lifespan)


class Transcript(BaseModel):
    text: str


@app.get("/health")
async def health():
    return {"status": "ok"}


async def decode_audio(source: Path, target: Path):
    # 多解码 1 秒，用实际 PCM 长度识别超限音频；不信任浏览器声明的时长。
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source),
        "-t", str(MAX_SECONDS + 1), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.wait(), timeout=20)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        raise HTTPException(422, "音频无法解码，请重新录音。")


async def transcribe_audio(file: UploadFile, model) -> Transcript:
    import soundfile as sf

    try:
        with tempfile.TemporaryDirectory(prefix="asr-") as directory:
            source = Path(directory) / "input.audio"
            target = Path(directory) / "decoded.wav"
            size = 0
            with source.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise HTTPException(413, "音频超过上传大小限制。")
                    output.write(chunk)
            if not size:
                raise HTTPException(422, "录音为空，请重新录音。")
            await decode_audio(source, target)
            info = sf.info(target)
            if info.duration > MAX_SECONDS:
                raise HTTPException(422, "录音超过时长限制，请分段录制。")
            result = await asyncio.to_thread(
                model.generate, input=str(target), batch_size_s=MAX_SECONDS,
                disable_pbar=True,
            )
            text = "".join(item.get("text", "") for item in result).strip()
            if not text:
                raise HTTPException(422, "未识别到语音，请靠近麦克风后重试。")
            return Transcript(text=text)
    finally:
        await file.close()


@app.post("/transcribe", response_model=Transcript)
async def transcribe(file: UploadFile):
    if app.state.busy:
        await file.close()
        raise HTTPException(429, "语音服务正在处理其他录音，请稍后重试。")
    # 单进程内不等待排队，防止多个 CPU 推理同时占用内存。
    app.state.busy = True
    # 客户端断开时仍让已开始的推理完成并清理临时音频，避免过早释放模型锁。
    job = asyncio.create_task(transcribe_audio(file, app.state.model))

    def completed(task):
        app.state.busy = False
        if not task.cancelled():
            task.exception()

    job.add_done_callback(completed)
    try:
        return await asyncio.shield(job)
    except HTTPException:
        raise
    except TimeoutError:
        raise HTTPException(504, "音频处理超时，请缩短录音后重试。") from None
    except Exception:
        logger.exception("ASR processing failed")
        raise HTTPException(500, "语音识别失败，请稍后重试。") from None
