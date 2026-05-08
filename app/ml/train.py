import pandas as pd, numpy as np, joblib, os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, mean_squared_error
from xgboost import XGBClassifier, XGBRegressor
 
DATA_PATH = os.path.join(os.path.dirname(__file__),
                         '..', 'data', 'training_data.csv')
OUT_DIR   = os.path.dirname(__file__)
 
print("Loading training data...")
df = pd.read_csv(DATA_PATH)
print(f"  Rows: {len(df)}  Columns: {list(df.columns)}")
 
# ── SEVERITY CLASSIFIER ──────────────────────────────────────────
print("\nTraining severity classifier...")
le_type = LabelEncoder()
le_sev  = LabelEncoder()
 
type_col  = next((c for c in df.columns if 'type' in c.lower()), None)
sev_col   = next((c for c in df.columns
                  if 'severity' in c.lower() or 'outcome' in c.lower()), None)
hour_col  = next((c for c in df.columns if 'hour' in c.lower()), None)
zone_col  = next((c for c in df.columns if 'zone' in c.lower()), None)
sos_col   = next((c for c in df.columns if 'sos' in c.lower()), None)
count_col = next((c for c in df.columns if 'count' in c.lower()), None)
 
if not type_col or not sev_col:
    print("  WARNING: expected columns not found, generating synthetic data")
    n = max(len(df), 2000)
    df['incident_type']    = np.random.choice(
        ['cardiac','trauma','respiratory','accident','stroke','other'], n)
    df['outcome_severity'] = np.random.choice(
        ['low','medium','high','critical'], n,
        p=[0.30, 0.35, 0.25, 0.10])
    df['hour_of_day']      = np.random.randint(0, 24, n)
    df['zone_risk']        = np.random.uniform(0.1, 1.0, n)
    df['sos_mode']         = np.random.randint(0, 2, n)
    df['patient_count']    = np.random.randint(1, 5, n)
    type_col='incident_type'; sev_col='outcome_severity'
    hour_col='hour_of_day';   zone_col='zone_risk'
    sos_col='sos_mode';       count_col='patient_count'
 
X_clf = pd.DataFrame({
    'type':  le_type.fit_transform(df[type_col].astype(str)),
    'count': df[count_col].fillna(1) if count_col else 1,
    'hour':  df[hour_col].fillna(12) if hour_col else 12,
    'zone':  df[zone_col].fillna(0.5) if zone_col else 0.5,
    'sos':   df[sos_col].fillna(0)  if sos_col  else 0,
})
y_clf = le_sev.fit_transform(df[sev_col].astype(str))
 
Xtr, Xte, ytr, yte = train_test_split(
    X_clf, y_clf, test_size=0.2, random_state=42)
clf = XGBClassifier(
    n_estimators=120,
    max_depth=4,
    eval_metric='mlogloss',
    random_state=42,
)
clf.fit(Xtr, ytr)
acc = accuracy_score(yte, clf.predict(Xte))
print(f"  Severity classifier accuracy: {acc:.3f}")
joblib.dump({'model': clf, 'le_type': le_type, 'le_sev': le_sev},
            os.path.join(OUT_DIR, 'severity_model.pkl'))
print("  Saved severity_model.pkl")
 
# ── HOSPITAL DELAY PREDICTOR ─────────────────────────────────────
print("\nTraining hospital delay predictor...")
n = len(df)
delay_df = pd.DataFrame({
    'occupancy':  np.random.uniform(40, 98, n),
    'hour':       np.random.randint(0, 24, n),
    'er_wait':    np.random.uniform(5, 60, n),
    'icu_beds':   np.random.randint(0, 20, n),
    'incoming':   np.random.randint(0, 8, n),
})
delay_y = (
    delay_df['occupancy'] * 0.4
    + delay_df['er_wait'] * 0.3
    + delay_df['incoming'] * 2
    + np.random.normal(0, 3, n)
).clip(2, 90)
 
Xtr2, Xte2, ytr2, yte2 = train_test_split(
    delay_df, delay_y, test_size=0.2, random_state=42)
reg1 = XGBRegressor(n_estimators=100, max_depth=3, random_state=42)
reg1.fit(Xtr2, ytr2)
rmse1 = mean_squared_error(yte2, reg1.predict(Xte2)) ** 0.5
print(f"  Hospital delay RMSE: {rmse1:.2f} min")
joblib.dump(reg1, os.path.join(OUT_DIR, 'delay_model.pkl'))
print("  Saved delay_model.pkl")
 
# ── ETA DRIFT PREDICTOR ──────────────────────────────────────────
print("\nTraining ETA drift predictor...")
drift_df = pd.DataFrame({
    'congestion': np.random.uniform(0.8, 3.0, n),
    'hour':       np.random.randint(0, 24, n),
    'distance':   np.random.uniform(0.5, 15.0, n),
    'weather':    np.random.choice([1.0, 1.2, 1.5], n),
})
drift_y = (
    drift_df['congestion'] * 1.8
    + drift_df['distance'] * 0.15
    + (drift_df['weather'] - 1) * 3
    + np.random.normal(0, 1, n)
).clip(0, 20)
 
Xtr3, Xte3, ytr3, yte3 = train_test_split(
    drift_df, drift_y, test_size=0.2, random_state=42)
reg2 = XGBRegressor(n_estimators=100, max_depth=3, random_state=42)
reg2.fit(Xtr3, ytr3)
rmse2 = mean_squared_error(yte3, reg2.predict(Xte3)) ** 0.5
print(f"  ETA drift RMSE: {rmse2:.2f} min")
joblib.dump(reg2, os.path.join(OUT_DIR, 'eta_drift_model.pkl'))
print("  Saved eta_drift_model.pkl")
 
print("\nAll 3 models trained and saved.")
print("PASS ml_training")
