import yfinance as yf
import pandas as pd
import pandas_ta as ta
import xgboost as xgb
import sys
import os
import requests
from datetime import datetime

# Importation du Risk Manager (Pour le dimensionnement Kelly)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from models.risk_manager import RiskManager


def send_notification(message):
    """
    Système de notification hybride :
    Si Telegram n'est pas configuré, affiche une pop-up directement sur ton bureau Linux.
    """
    bot_token = "8719801623:AAEX50r27GeiCLXSLbCsOc7y1g4ZJkbqJ4s"
    chat_id = "8062636688"

    if bot_token and "TON_TOKEN" not in bot_token:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            response = requests.post(url, data=payload)
            print(f"Statut de l'envoi Telegram : {response.status_code}")
            print(f"Réponse de Telegram : {response.text}")
        except Exception as e:
            print(f"Erreur d'envoi Telegram : {e}")
    else:
        print("⚠️ Telegram non configuré. Affichage d'une notification sur le bureau Linux.")
        try:
            import subprocess
            subprocess.Popen(['zenity', '--info', '--title=SATOCHI BOT', '--no-markup', f'--text={message}', '--width=400'])
        except Exception as e:
            print(f"Erreur d'affichage Zenity : {e}")


def load_pair_data(symbol, period="10y", interval="1d"):
    df = yf.download(symbol, period=period, interval=interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    return df


def add_indicators(df):
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df['Returns'] = df['Close'].pct_change()

    try:
        ichimoku, _ = ta.ichimoku(df['High'], df['Low'], df['Close'])
        tenkan_col = [c for c in ichimoku.columns if 'ITS' in c][0]
        kijun_col = [c for c in ichimoku.columns if 'IKS' in c][0]
        senkou_a_col = [c for c in ichimoku.columns if 'ISA' in c][0]
        senkou_b_col = [c for c in ichimoku.columns if 'ISB' in c][0]

        df['Dist_Tenkan'] = df['Close'] - ichimoku[tenkan_col]
        df['Dist_Kijun'] = df['Close'] - ichimoku[kijun_col]
        df['Nuage_Epaisseur'] = ichimoku[senkou_a_col] - ichimoku[senkou_b_col]
    except Exception as e:
        print("Erreur Ichimoku:", e)
        df['Dist_Tenkan'] = 0
        df['Dist_Kijun'] = 0
        df['Nuage_Epaisseur'] = 0

    rolling_high = df['High'].rolling(window=20).max()
    rolling_low = df['Low'].rolling(window=20).min()
    rolling_range = rolling_high - rolling_low
    rolling_range = rolling_range.replace(0, 0.0001)
    df['Fibo_Retracement'] = (df['Close'] - rolling_low) / rolling_range

    return df


def compute_sl_tp(df, symbol, prediction, last_close_price, last_atr):
    df_h4 = yf.download(symbol, period='20d', interval='4h', progress=False)
    if isinstance(df_h4.columns, pd.MultiIndex):
        df_h4.columns = df_h4.columns.get_level_values(0)

    low_h4 = df_h4['Low'].iloc[-12:]
    high_h4 = df_h4['High'].iloc[-12:]
    recent_low_h4 = float(low_h4.min())
    recent_high_h4 = float(high_h4.max())
    micro_buffer = last_atr * 0.1

    if prediction == 1:
        sl = recent_low_h4 - micro_buffer
        risk = last_close_price - sl
        if risk <= 0:
            risk = last_atr * 0.3
            sl = last_close_price - risk
        tp = last_close_price + (risk * 2.0)
    else:
        sl = recent_high_h4 + micro_buffer
        risk = sl - last_close_price
        if risk <= 0:
            risk = last_atr * 0.3
            sl = last_close_price + risk
        tp = last_close_price - (risk * 2.0)

    return sl, tp


def run_pair_strategy(symbol, pair_name):
    print("=========================================================")
    print(f"🌞 SATOCHI : L'INVESTISSEUR QUOTIDIEN (PAIRE {pair_name})")
    print("=========================================================")

    print("📥 1. Téléchargement des bougies Daily (10 ans d'historique)...")
    df = load_pair_data(symbol)

    print("🧠 2. Calcul des indicateurs de marché en cours (Ichimoku & Fibo inclus)...")
    df = add_indicators(df)

    df['Future_Close'] = df['Close'].shift(-1)
    df['Target'] = (df['Future_Close'] > df['Close']).astype(int)

    features = ['RSI', 'ATR', 'Returns', 'Dist_Tenkan', 'Dist_Kijun', 'Nuage_Epaisseur', 'Fibo_Retracement']
    train_df = df.dropna(subset=['Target'] + features)
    current_data = df[features].iloc[-1:]

    X_train = train_df[features]
    y_train = train_df['Target']

    print(f"🤖 3. Entraînement éclair de l'IA XGBoost sur les {len(X_train)} derniers jours de la paire {pair_name}...")
    model = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42, eval_metric='logloss')
    model.fit(X_train, y_train)

    prediction = model.predict(current_data)[0]
    probability = model.predict_proba(current_data)[0][prediction]
    signal = "ACHAT 🟢" if prediction == 1 else "VENTE 🔴"

    print(f"\n🔮 PRÉDICTION DE CLÔTURE POUR DEMAIN : {signal}")
    print(f"📊 Certitude Mathématique : {probability*100:.2f}%\n")

    risk_manager = RiskManager()
    trade_size_pct = risk_manager.calculate_position_size(win_probability=probability)

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    last_close_price = float(df['Close'].iloc[-1])
    last_atr = float(df['ATR'].iloc[-1])
    sl, tp = compute_sl_tp(df, symbol, prediction, last_close_price, last_atr)

    report = f"✅ *RAPPORT SATOCHI D1* ({date_str})\n"
    report += f"Paire: {pair_name}\n"
    report += f"Prix D1 (Clôture): {last_close_price:.5f}\n"
    report += f"Signal: {signal}\n"
    report += f"🛑 Stop Loss: {sl:.5f}\n"
    report += f"🎯 Take Profit: {tp:.5f}\n"
    report += f"Certitude IA: {probability*100:.2f}%\n"

    if trade_size_pct > 0:
        print(f"💰 Le Risk Manager valide la transaction : Risque alloué {trade_size_pct*100:.2f}% du portefeuille.")
        report += f"Allocation: {trade_size_pct*100:.2f}%\n"
        units_to_trade = 100000 * trade_size_pct
        print(f"✅ [SIMULATION] Envoi de l'ordre ({signal}) de {units_to_trade:.0f} unités au Broker !")
        report += f"Statut: Action Valide & Exécutée 🟢"
    else:
        print("🛑 Le Risk Manager bloque le trade : La certitude de l'IA est trop faible pour risquer du capital selon le critère de Kelly.")
        report += f"Statut: Rejeté par le RiskManager 🛑"

    print("=========================================================")
    send_notification(report)
