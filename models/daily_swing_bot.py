import yfinance as yf
import pandas as pd
import pandas_ta as ta
import xgboost as xgb
import sys
import os
import requests
from datetime import datetime

# Importation du Risk Manager (Pour le dimensionnement Kelly) et du Broker
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.risk_manager import RiskManager
from execution.broker_manager import BrokerManager

def send_notification(message):
    """
    Système de notification hybride :
    Si Telegram n'est pas configuré, affiche une pop-up directement sur ton bureau Linux !
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
        # Alternative : Notification locale (Pop-up sur ton PC Linux Asus)
        print("⚠️ Telegram non configuré. Affichage d'une notification sur le bureau Linux.")
        try:
            import subprocess
            # Lancement de Zenity de façon sécurisée (préserve parfaitement les sauts de ligne et le texte)
            subprocess.Popen(['zenity', '--info', '--title=SATOCHI BOT', '--no-markup', f'--text={message}', '--width=400'])
        except Exception as e:
            print(f"Erreur d'affichage Zenity : {e}")

def run_daily_swing_trade():
    print("=========================================================")
    print("🌞 SATOCHI : L'INVESTISSEUR QUOTIDIEN (TIMEFRAME D1)")
    print("=========================================================")
    
    # 1. Récupération des données jusqu'à la clôture d'aujourd'hui
    print("📥 1. Téléchargement des bougies Daily (10 ans d'historique)...")
    df = yf.download("EURUSD=X", period="10y", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)

    # 2. Indicateurs techniques
    print("🧠 2. Calcul des indicateurs de marché en cours (Ichimoku & Fibo inclus)...")
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    df['Returns'] = df['Close'].pct_change()

    # 2.1 Ichimoku
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

    # 2.2 Fibonacci Dynamique (Retracement 20 jours Swing)
    rolling_high = df['High'].rolling(window=20).max()
    rolling_low = df['Low'].rolling(window=20).min()
    rolling_range = rolling_high - rolling_low
    rolling_range = rolling_range.replace(0, 0.0001) # Éviter la division par zéro
    df['Fibo_Retracement'] = (df['Close'] - rolling_low) / rolling_range

    # Création des cibles passées pour l'entraînement
    df['Future_Close'] = df['Close'].shift(-1)
    df['Target'] = (df['Future_Close'] > df['Close']).astype(int)

    # NOTE : On garde EXACTEMENT les indicateurs qui ont fonctionné pour le PF à 1.535
    features = ['RSI', 'ATR', 'Returns', 'Dist_Tenkan', 'Dist_Kijun', 'Nuage_Epaisseur', 'Fibo_Retracement']
    
    # 3. Séparation : Passé (Entraînement) vs Aujourd'hui (Déduction)
    # On enlève la dernière ligne pour l'entraînement car son "Future_Close" est un NaN (on ne connaît pas encore demain !)
    train_df = df.dropna(subset=['Target'] + features)
    
    # "current_data" contient uniquement les indicateurs de la journée fraîche d'aujourd'hui
    current_data = df[features].iloc[-1:] 

    X_train = train_df[features]
    y_train = train_df['Target']

    # 4. Entraînement Flash (Le modèle reste frais et adaptatif)
    print(f"🤖 3. Entraînement éclair de l'IA XGBoost sur les {len(X_train)} derniers jours de la paire EUR/USD...")
    # Paramètres exacts du test validé à 1.535
    model = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42, eval_metric='logloss')
    model.fit(X_train, y_train)

    # 5. Prédiction pour le lendemain
    prediction = model.predict(current_data)[0]
    probability = model.predict_proba(current_data)[0][prediction] # Confiance de l'IA (en %)
    
    signal = "ACHAT 🟢" if prediction == 1 else "VENTE 🔴"
    
    print(f"\n🔮 PRÉDICTION DE CLÔTURE POUR DEMAIN : {signal}")
    print(f"📊 Certitude Mathématique : {probability*100:.2f}%\n")

    # 6. Gestion Rationnelle du Risque
    risk_manager = RiskManager()
    trade_size_pct = risk_manager.calculate_position_size(win_probability=probability)
    
    # === CONSTRUCTION DU RAPPORT POUR NOTIFICATION ===
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    last_close_price = float(df['Close'].iloc[-1])
    last_atr = float(df['ATR'].iloc[-1])
    
    # 1. Détection de la Structure Intraday (H4) pour affiner le SL/TP
    # On télécharge les données 4H des 5 derniers jours
    df_h4 = yf.download('EURUSD=X', period='20d', interval='4h', progress=False)
    
    # Extrema locaux très récents (environ 12 bougies H4 = les 48 dernières heures)
    low_h4 = df_h4[('Low', 'EURUSD=X')]
    high_h4 = df_h4[('High', 'EURUSD=X')]
    recent_low_h4 = float(low_h4.iloc[-12:].min())
    recent_high_h4 = float(high_h4.iloc[-12:].max())
    
    # 2. Calcul du Stop Loss (Structure H4 + un micro-bouclier de 10% de l'ATR)
    micro_buffer = last_atr * 0.1
    
    if prediction == 1:  # ACHAT
        sl = recent_low_h4 - micro_buffer
        risk = last_close_price - sl
        # Sécurité anti-bug si le prix actuel est étrangement sous le plus bas H4
        if risk <= 0:
            risk = last_atr * 0.3
            sl = last_close_price - risk
        tp = last_close_price + (risk * 2.0)  # Ratio 1:2 car le stop est très serré
    else:  # VENTE
        sl = recent_high_h4 + micro_buffer
        risk = sl - last_close_price
        if risk <= 0:
            risk = last_atr * 0.3
            sl = last_close_price + risk
        tp = last_close_price - (risk * 2.0)
    
    report = f"✅ *RAPPORT SATOCHI D1* ({date_str})\n"
    report += f"Paire: EUR/USD\n"
    report += f"Prix D1 (Clôture): {last_close_price:.5f}\n"
    report += f"Signal: {signal}\n"
    report += f"🛑 Stop Loss: {sl:.5f}\n"
    report += f"🎯 Take Profit: {tp:.5f}\n"
    report += f"Certitude IA: {probability*100:.2f}%\n"
    
    if trade_size_pct > 0:
        print(f"💰 Le Risk Manager valide la transaction : Risque alloué {trade_size_pct*100:.2f}% du portefeuille.")
        report += f"Allocation: {trade_size_pct*100:.2f}%\n"
        
        # 7. Exécution Fictive (Simulation Broker)
        units_to_trade = 100000 * trade_size_pct # Ex: Compte 100k
        print(f"✅ [SIMULATION] Envoi de l'ordre ({signal}) de {units_to_trade:.0f} unités au Broker !")
        report += f"Statut: Action Valide & Exécutée 🟢"
    else:
        print("🛑 Le Risk Manager bloque le trade : La certitude de l'IA est trop faible pour risquer du capital selon le critère de Kelly.")
        report += f"Statut: Rejeté par le RiskManager 🛑"
        
    print("=========================================================")
    
    # 8. Envoi de la notification
    send_notification(report)

if __name__ == "__main__":
    run_daily_swing_trade()