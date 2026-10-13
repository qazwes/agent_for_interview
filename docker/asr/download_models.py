"""从 Hugging Face 下载模型；推理容器只读取这些本地目录。"""
import os

from huggingface_hub import snapshot_download

MODELS = (
    ("funasr/paraformer-zh", "paraformer", "ASR_MODEL_REVISION"),
    ("funasr/fsmn-vad", "vad", "ASR_VAD_REVISION"),
    ("funasr/ct-punc", "punctuation", "ASR_PUNC_REVISION"),
)

if __name__ == "__main__":
    for repo, directory, revision_key in MODELS:
        print(f"Downloading {repo}", flush=True)
        snapshot_download(
            repo_id=repo,
            revision=os.getenv(revision_key, "main"),
            local_dir=f"/models/{directory}",
        )
    print("All ASR models downloaded", flush=True)
