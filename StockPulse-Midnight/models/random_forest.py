import os,joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report,roc_auc_score
from data.indicators import compute_all,ML_FEATURES
from models.training_data import labelled_groups,cutoff_date
from config import Config
MODEL_PATH=os.path.join(Config.MODEL_DIR,'rf_model.pkl')
SCALER_PATH=os.path.join(Config.MODEL_DIR,'rf_scaler.pkl')

def generate_labels(df,future_days=5,threshold=.03):return pd.concat([f for _,f in labelled_groups(df,future_days,threshold)])
def train(df,future_days=5,threshold=.03):
    groups=labelled_groups(df,future_days,threshold);cutoff=cutoff_date(groups)
    training=pd.concat([f[f['_target_end']<cutoff] for _,f in groups]);testing=pd.concat([f[f.index>=cutoff] for _,f in groups])
    if len(training)<50 or len(testing)<10 or training.Label.nunique()<2 or testing.Label.nunique()<2:raise ValueError('Training and evaluation each need enough examples of both classes. Fetch more data.')
    scaler=StandardScaler().fit(training[ML_FEATURES].values)
    model=RandomForestClassifier(n_estimators=200,max_depth=10,min_samples_split=10,min_samples_leaf=5,class_weight='balanced',n_jobs=-1,random_state=42)
    model.fit(scaler.transform(training[ML_FEATURES].values),training.Label.values)
    x=scaler.transform(testing[ML_FEATURES].values);pred=model.predict(x);prob=model.predict_proba(x)[:,list(model.classes_).index(1)]
    metrics=dict(accuracy=float(np.mean(pred==testing.Label.values)),auc_roc=float(roc_auc_score(testing.Label.values,prob)),report=classification_report(testing.Label.values,pred,zero_division=0),features=ML_FEATURES,split_date=str(cutoff))
    for item,path in [(model,MODEL_PATH),(scaler,SCALER_PATH)]:joblib.dump(item,path+'.tmp');os.replace(path+'.tmp',path)
    return model,scaler,metrics

def train_on_multiple(tickers,period='2y'):
    from data.fetcher import fetch_stock
    frames=[]
    for ticker in tickers:
        frame=fetch_stock(ticker,period)
        if not frame.empty:frame=frame.copy();frame['Ticker']=ticker;frames.append(frame)
    return train(pd.concat(frames)) if frames else (None,None,{})
def load_model():
    if not all(os.path.exists(p) for p in [MODEL_PATH,SCALER_PATH]):return None,None
    return joblib.load(MODEL_PATH),joblib.load(SCALER_PATH)
def predict_breakout(df):
    model,scaler=load_model()
    if model is None:raise ValueError('Random Forest is not trained. Open Model settings.')
    frame=compute_all(df)
    last=frame[ML_FEATURES].iloc[[-1]].values
    if not np.isfinite(last).all():raise ValueError('The latest bar has incomplete model features.')
    probability=float(model.predict_proba(scaler.transform(last))[0,list(model.classes_).index(1)])
    return dict(breakout_probability=round(probability*100,2),signal='STRONG BUY' if probability>.70 else 'BUY' if probability>.55 else 'NEUTRAL' if probability>.40 else 'SELL',features_used=ML_FEATURES)
def get_feature_importance():
    model,_=load_model()
    if model is None:return {}
    return dict(sorted(zip(ML_FEATURES,model.feature_importances_.tolist()),key=lambda item:item[1],reverse=True))
