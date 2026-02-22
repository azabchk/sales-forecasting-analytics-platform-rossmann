from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import joblib
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


def load_config(config_path: str) -> tuple[dict, Path]:
    cfg_path = Path(config_path).resolve()
    with open(cfg_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file), cfg_path


def resolve_path(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def load_intents_dataset(path: Path) -> tuple[list[str], list[str]]:
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    texts: list[str] = []
    labels: list[str] = []
    for label, samples in payload.items():
        if not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, str):
                continue
            sample = sample.strip()
            if not sample:
                continue
            texts.append(sample)
            labels.append(label)

    if not texts:
        raise ValueError("Intents dataset is empty")
    return texts, labels


def _augment_sample(sample: str) -> list[str]:
    variants = {sample}
    normalized = re.sub(r"\s+", " ", sample.strip())
    variants.add(normalized)
    variants.add(normalized.lower())

    replacements = {
        "forecast": ["predict", "projection"],
        "predict": ["forecast"],
        "sales": ["revenue"],
        "store": ["branch"],
        "promo": ["promotion"],
        "model": ["algorithm"],
        "summary": ["overview"],
        "data": ["dataset"],
    }

    lowered = normalized.lower()
    for src, targets in replacements.items():
        if src in lowered:
            for target in targets:
                variants.add(re.sub(src, target, lowered))

    if "store " in lowered and not re.search(r"store\s+\d+", lowered):
        variants.add(f"{lowered} store 1")
        variants.add(f"{lowered} store 25")

    if "day" in lowered and not re.search(r"\d+\s*(day|days|d)", lowered):
        variants.add(f"{lowered} 30 days")
        variants.add(f"{lowered} 90 days")

    return [item for item in variants if item]


def augment_dataset(texts: list[str], labels: list[str]) -> tuple[list[str], list[str]]:
    aug_texts: list[str] = []
    aug_labels: list[str] = []
    for text, label in zip(texts, labels):
        for variant in _augment_sample(text):
            aug_texts.append(variant)
            aug_labels.append(label)
    return aug_texts, aug_labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Train chatbot intent classifier")
    parser.add_argument("--config", required=True, help="Path to ml/config.yaml")
    args = parser.parse_args()

    cfg, cfg_path = load_config(args.config)
    chatbot_cfg = cfg.get("chatbot", {})

    intents_path = resolve_path(cfg_path.parent, chatbot_cfg.get("intents_path", "chat_intents.json"))
    model_path = resolve_path(cfg_path.parent, chatbot_cfg.get("model_path", "artifacts/chat_intent_model.joblib"))
    min_confidence = float(chatbot_cfg.get("min_confidence", 0.45))

    texts, labels = load_intents_dataset(intents_path)
    texts, labels = augment_dataset(texts, labels)

    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )

    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=1,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=3000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    pipeline.fit(x_train, y_train)
    y_pred = pipeline.predict(x_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, zero_division=0)

    artifact = {
        "pipeline": pipeline,
        "labels": sorted(set(labels)),
        "accuracy": float(accuracy),
        "min_confidence": min_confidence,
        "dataset_size": len(texts),
    }

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)

    print("[Chatbot] Training completed")
    print(f"[Chatbot] Dataset size: {len(texts)}")
    print(f"[Chatbot] Validation accuracy: {accuracy:.4f}")
    print(f"[Chatbot] Model saved to: {model_path}")
    print("[Chatbot] Classification report:")
    print(report)


if __name__ == "__main__":
    main()
