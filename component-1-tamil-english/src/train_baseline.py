from pathlib import Path
import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)

from prepare_dataset import load_dataset
from preprocessing import clean_comment


PROJECT_DIR = Path(__file__).resolve().parent.parent

TRAIN_PATH = Path(
    r"C:\Users\Almeda\Desktop\Y4\RP\Test Data\New folder"
    r"\DravidianCodeMix\tamil_offensive_full_train.csv"
)

DEV_PATH = PROJECT_DIR / "data" / "tamil_offensive_full_dev.csv"


def prepare_binary_dataset(path):
    """Load data and map offensive-language labels to two classes."""

    df = load_dataset(path)

    # Exclude comments labelled as not Tamil
    df = df[df["label"] != "not-Tamil"].copy()

    # Map the original labels to two classes
    df["target"] = df["label"].apply(
        lambda label: (
            "Non-offensive"
            if label == "Not_offensive"
            else "Offensive"
        )
    )

    # Clean the text
    df["clean_comment"] = df["comment"].apply(clean_comment)

    # Remove comments that become empty
    df = df[df["clean_comment"] != ""].copy()

    return df.reset_index(drop=True)


def main():
    print("Loading datasets...")

    train_df = prepare_binary_dataset(TRAIN_PATH)
    dev_df = prepare_binary_dataset(DEV_PATH)

    print(f"Training records: {len(train_df)}")
    print(f"Development records: {len(dev_df)}")

    print("\nTraining class distribution:")
    print(train_df["target"].value_counts().to_string())

    # Character n-grams can help capture spelling variations
    vectorizer = TfidfVectorizer(
        analyzer="char",
        ngram_range=(2, 5),
        min_df=2,
        max_features=300000,
        sublinear_tf=True,
    )

    print("\nConverting comments into TF-IDF features...")

    X_train = vectorizer.fit_transform(train_df["clean_comment"])
    X_dev = vectorizer.transform(dev_df["clean_comment"])

    y_train = train_df["target"]
    y_dev = dev_df["target"]

    models = {
        "Logistic Regression": LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        ),
        "Linear SVM": LinearSVC(
            class_weight="balanced",
            random_state=42,
        ),
    }

    print(f"Training feature matrix: {X_train.shape}")
    print(f"Development feature matrix: {X_dev.shape}")

    for model_name, model in models.items():
        print("\n" + "=" * 60)
        print(f"MODEL: {model_name}")
        print("=" * 60)

        start_time = time.time()

        model.fit(X_train, y_train)
        predictions = model.predict(X_dev)

        elapsed = time.time() - start_time

        print(f"Accuracy: {accuracy_score(y_dev, predictions):.4f}")
        print(f"Macro F1: {f1_score(y_dev, predictions, average='macro'):.4f}")
        print(f"Training and prediction time: {elapsed:.2f} seconds")

        print("\nClassification report:")
        print(
            classification_report(
                y_dev,
                predictions,
                zero_division=0,
            )
        )


if __name__ == "__main__":
    main()