import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib
import warnings
warnings.filterwarnings('ignore')

# ================================================
# DEFINE OUR 10 FEATURES
# These exact columns feed into XGBoost
# ================================================
FEATURE_COLUMNS = [
    'log_return_1', 'log_return_3', 'log_return_5', 'log_return_10',
    'atr_ratio',
    'rsi', 'rsi_change',
    'macd_histogram',
    'bb_percent_b',
    'volume_ratio',
    'hour_sin', 'hour_cos',
    'autocorr',
    'breadth',
    'spread_proxy'
]

TARGET_COLUMN = 'label'

# ================================================
# STEP 1: LOAD DATA
# ================================================
print("Loading labeled data...")
df = pd.read_csv('btc_labeled.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])
print(f"Loaded {len(df)} rows")

# ================================================
# STEP 2: WALK-FORWARD VALIDATION
# Train on past, test on future
# Split into 3 periods
# ================================================
print("\nStarting Walk-Forward Validation...")

total_rows = len(df)
fold_size = total_rows // 10  # each test fold = 10% of data

all_accuracies = []
all_reports = []

# We do 3 folds
for fold in range(3):
    # Calculate split points
    # Fold 0: train on 60%, test on next 10%
    # Fold 1: train on 70%, test on next 10%
    # Fold 2: train on 80%, test on next 10%
    
    train_end = int(total_rows * (0.6 + fold * 0.1))
    test_start = train_end
    test_end = test_start + fold_size
    
    if test_end > total_rows:
        break
    
    # Split features and labels
    X_train = df[FEATURE_COLUMNS].iloc[:train_end]
    y_train = df[TARGET_COLUMN].iloc[:train_end]
    
    X_test = df[FEATURE_COLUMNS].iloc[test_start:test_end]
    y_test = df[TARGET_COLUMN].iloc[test_start:test_end]
    
    print(f"\nFold {fold + 1}:")
    print(f"  Train: rows 0 to {train_end} ({train_end} rows)")
    print(f"  Test:  rows {test_start} to {test_end} ({test_end - test_start} rows)")
    
    # ================================================
    # STEP 3: TRAIN XGBOOST
    # These are the exact parameters from your docs
    # ================================================
    model = XGBClassifier(
        n_estimators=400,       # 400 decision trees
        learning_rate=0.1,      # how fast model learns
        max_depth=4,            # how complex each tree is
        min_child_weight=3,     # minimum data per leaf
        subsample=0.8,          # use 80% of data per tree
        reg_alpha=0.5,          # L1 regularization (prevents overfitting)
        reg_lambda=1.0,         # L2 regularization (prevents overfitting)
        eval_metric='logloss',
        random_state=42,
        verbosity=0
    )
    
    model.fit(X_train, y_train)
    
    # ================================================
    # STEP 4: TEST IT
    # ================================================
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]  # probability of label=1
    
    accuracy = accuracy_score(y_test, y_pred)
    all_accuracies.append(accuracy)
    
    print(f"  Accuracy: {accuracy:.1%}")
    print(f"  Avg BUY probability: {y_prob.mean():.3f}")
    
    # How many would pass 65% threshold?
    high_confidence = (y_prob >= 0.65).sum()
    print(f"  Signals above 65% threshold: {high_confidence} ({100*high_confidence/len(y_prob):.1f}%)")

print(f"\nAverage accuracy across all folds: {np.mean(all_accuracies):.1%}")

# ================================================
# STEP 5: TRAIN FINAL MODEL ON ALL DATA
# Now we use everything to train the best model
# ================================================
print("\nTraining final model on all data...")

X_all = df[FEATURE_COLUMNS]
y_all = df[TARGET_COLUMN]

final_model = XGBClassifier(
    n_estimators=400,
    learning_rate=0.1,
    max_depth=4,
    min_child_weight=3,
    subsample=0.8,
    reg_alpha=0.5,
    reg_lambda=1.0,
    eval_metric='logloss',
    random_state=42,
    verbosity=0
)

final_model.fit(X_all, y_all)
print("Final model trained!")

# ================================================
# STEP 6: FEATURE IMPORTANCE
# Which features matter most to XGBoost?
# ================================================
print("\nFeature Importance (which features matter most):")
importance = final_model.feature_importances_
for feat, imp in sorted(zip(FEATURE_COLUMNS, importance), 
                         key=lambda x: x[1], reverse=True):
    bar = "#" * int(imp * 100)
    print(f"  {feat:<20} {imp:.4f} {bar}")

# ================================================
# STEP 7: SAVE THE MODEL
# ================================================
joblib.dump(final_model, 'xgboost_model.pkl')
joblib.dump(FEATURE_COLUMNS, 'feature_columns.pkl')
print("\nModel saved to xgboost_model.pkl")
print("Feature columns saved to feature_columns.pkl")
print("\nDone! XGBoost model is ready!")
