import requests
import json
import os
import sys

class BrokerManager:
    def __init__(self, account_id, api_token, environment="practice"):
        """
        Connecteur vers un Broker (OANDA est utilisé ici en exemple d'API REST).
        - environment: 'practice' pour le Paper Trading, 'live' pour le vrai argent.
        """
        self.account_id = account_id
        self.api_token = api_token
        
        self.domain = "api-fxpractice.oanda.com" if environment == "practice" else "api-fxtrade.oanda.com"
        self.base_url = f"https://{self.domain}/v3/accounts/{self.account_id}"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
    def execute_trade(self, instrument, units, signal_type):
        """
        Exécute un ordre de marché (Market Order) chez le broker.
        - signal_type: "BUY" ou "SELL"
        - units: Taille de position (ex: 10000 = 1 mini-lot sur Oanda)
        """
        # Si on veut vendre, les unités oanda doivent être négatives
        if signal_type == "SELL":
            units = -units
            
        order_data = {
            "order": {
                "units": str(int(units)),
                "instrument": instrument,
                "timeInForce": "FOK", # Fill Or Kill (Haute fréquence)
                "type": "MARKET",
                "positionFill": "DEFAULT"
            }
        }
        
        print(f"🏦 [BROKER] Envoi de l'Ordre {signal_type} {abs(units)} EUR/USD à l'API OANDA...")
        
        try:
            # Requete POST à l'API du Broker
            response = requests.post(
                f"{self.base_url}/orders", 
                headers=self.headers, 
                data=json.dumps(order_data)
            )
            
            # Vérification de la réponse
            if response.status_code == 201:
                res_json = response.json()
                trade_id = res_json['orderFillTransaction']['id']
                price = res_json['orderFillTransaction']['price']
                print(f"✅ Transaction Validée ! ID: {trade_id} @ Prix Moyen Executé: {price}")
                return True
            else:
                print(f"❌ Erreur d'exécution Broker : {response.text}")
                return False
                
        except Exception as e:
            print(f"⚠️ Plantage de la Connexion API Broker : {e}")
            return False

if __name__ == "__main__":
    print("=========================================================")
    print("🏦 TEST DU CONNECTEUR BROKER (PAPER TRADING API) ")
    print("=========================================================")
    print("⚠️ C'est ici que tu mettras ta Vraie Clé OANDA ou ton API Binance pour laisser Satochi jouer ton argent.")
    print("Pour l'instant, on n'a pas tes clés complètes (Account_ID et API_TOKEN), la transaction échouerait.")
