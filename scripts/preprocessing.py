"""
Preprocessing — Lab 4.
Завантажує дані, очищує, розділяє на train/test.
"""
import os
import re
import argparse
try:
    import torch  # noqa: F401
except ImportError:
    pass
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import spacy
from nltk.corpus import stopwords
import nltk

nltk.download("stopwords", quiet=True)
nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
STOP_WORDS = set(stopwords.words("english"))

CATEGORIES = ["Technical", "Account", "Billing", "Feedback", "Other"]


def clean_text(text):
    text = re.sub(r"http\S+|www\S+", "", str(text))
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    return text.lower().strip()


def lemmatize(text):
    doc = nlp(text)
    return " ".join(
        t.lemma_ for t in doc if not t.is_stop and not t.is_punct and len(t.text) > 1
    )


def preprocess_pipeline(text):
    return lemmatize(clean_text(text))


def run_preprocessing(input_dir, output_dir, test_size=0.2, max_samples=None):
    """Повний пайплайн preprocessing."""
    print("=" * 60)
    print("PREPROCESSING STEP")
    print("=" * 60)

    input_files = [f for f in os.listdir(input_dir) if f.endswith(".csv")]
    if not input_files:
        raise FileNotFoundError(f"No CSV files in {input_dir}")

    df = pd.read_csv(os.path.join(input_dir, input_files[0]))
    print(f"Loaded {len(df)} rows")

    if max_samples:
        df = df.head(max_samples)
        print(f"Limited to {max_samples} samples")

    df = df.dropna(subset=["text", "category"])
    df = df[df["category"].isin(CATEGORIES)]
    print(f"After filtering: {len(df)} rows")

    print("Preprocessing text...")
    df["clean_text"] = df["text"].apply(preprocess_pipeline)
    df = df[df["clean_text"].str.len() > 0]

    label2id = {cat: i for i, cat in enumerate(CATEGORIES)}
    df["label"] = df["category"].map(label2id)

    train_df, test_df = train_test_split(
        df, test_size=test_size, random_state=42, stratify=df["category"]
    )

    os.makedirs(output_dir, exist_ok=True)
    train_df.to_csv(os.path.join(output_dir, "train.csv"), index=False)
    test_df.to_csv(os.path.join(output_dir, "test.csv"), index=False)

    print(f"Train: {len(train_df)}, Test: {len(test_df)}")
    print(f"Saved to {output_dir}")
    return train_df, test_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, default="data/raw")
    parser.add_argument("--output-dir", type=str, default="data/processed")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    run_preprocessing(args.input_dir, args.output_dir, args.test_size, args.max_samples)
