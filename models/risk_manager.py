class RiskManager:
    def __init__(self, max_daily_drawdown=0.03, half_kelly=True, reward_risk_ratio=1.5, max_risk_per_trade=0.05):
        """
        Gestionnaire de risque quantitatif strict (Indépendant de l'IA).
        - max_daily_drawdown : -3% de perte max autorisée par jour.
        - reward_risk_ratio : Gain moyen / Perte moyenne (1.5 ATR / 1.0 ATR).
        - max_risk_per_trade : Jamais plus de 5% du capital sur un seul trade.
        """
        self.max_daily_drawdown = max_daily_drawdown
        self.half_kelly = half_kelly
        self.reward_risk_ratio = reward_risk_ratio
        self.max_risk_per_trade = max_risk_per_trade
        
        # Simulation d'un état "Live" (Dans la réalité, on l'interroge depuis la BD ou le Broker)
        self.current_daily_drawdown = 0.00  # Exemple : 0% de perte aujourd'hui

    def check_circuit_breaker(self):
        """
        Vérifie si le bot doit être coupé pour protéger le capital.
        """
        if self.current_daily_drawdown >= self.max_daily_drawdown:
            return False, "CIRCUIT_BREAKER_ACTIVE: Limite de drawdown journalière atteinte (-3%)."
        return True, "RISQUE_OK"

    def calculate_position_size(self, win_probability):
        """
        Calcule la taille de position avec la formule de Kelly.
        f* = p - ((1 - p) / b)
        p = probabilité de victoire
        b = Ratio Reward/Risk
        """
        p = win_probability
        b = self.reward_risk_ratio
        
        # Formule de Kelly
        kelly_fraction = p - ((1.0 - p) / b)
        
        # Si edge statistique nul ou négatif, on ne rentre pas
        if kelly_fraction <= 0:
            return 0.0
            
        # On utilise le Demi-Kelly pour être conservateur (standard industriel)
        if self.half_kelly:
            kelly_fraction /= 2.0
            
        # On capte le risque au maximum autorisé par trade
        position_size = min(kelly_fraction, self.max_risk_per_trade)
        
        return round(position_size, 4)
