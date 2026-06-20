# Configuration for TFF Financial Futures Markets only - ASCII Keys for encoding safety

PARTICIPANTS_MAP = {
    "TFF": {
        "Leveraged Funds": {
            "long": "lev_money_positions_long",
            "short": "lev_money_positions_short",
            "spread": "lev_money_positions_spread"
        },
        "Asset Manager": {
            "long": "asset_mgr_positions_long",
            "short": "asset_mgr_positions_short",
            "spread": "asset_mgr_positions_spread"
        },
        "Dealer": {
            "long": "dealer_positions_long_all",
            "short": "dealer_positions_short_all",
            "spread": "dealer_positions_spread_all"
        },
        "Retail": {
            "long": "nonrept_positions_long_all",
            "short": "nonrept_positions_short_all",
            "spread": None
        }
    }
}

MARKETS = {
    "S&P 500": {
        "display_name": "S&P 500 INDEX FUTS",
        "cftc_code": "13874A",
        "dataset_id": "gpe5-46if",  # TFF Futures Only
        "report_type": "TFF",
        "ticker": "^GSPC",
        "color": "#00f0ff",  # Neon Cyan
        "sector": "INDEX"
    },
    "Nasdaq": {
        "display_name": "NASDAQ 100 FUTS",
        "cftc_code": "209742",      # Mini Nasdaq-100
        "dataset_id": "gpe5-46if",  # TFF Futures Only
        "report_type": "TFF",
        "ticker": "^NDX",
        "color": "#d000ff",  # Neon Purple/Magenta
        "sector": "INDEX"
    },
    "EUR": {
        "display_name": "EURO FX FUTS",
        "cftc_code": "099741",      # Euro FX
        "dataset_id": "gpe5-46if",  # TFF Futures Only
        "report_type": "TFF",
        "ticker": "EURUSD=X",
        "color": "#39ff14",  # Neon Green
        "sector": "FX"
    },
    "BTC": {
        "display_name": "CME BITCOIN FUTS",
        "cftc_code": "133741",      # Bitcoin CME
        "dataset_id": "gpe5-46if",  # TFF Futures Only
        "report_type": "TFF",
        "ticker": "BTC-USD",
        "color": "#ff5e00",  # Neon Orange/Red
        "sector": "CRYPTO"
    }
}

# General configurations
DATA_DIR_COT = "data/cot"
DATA_DIR_PRICES = "data/prices"
DEFAULT_HISTORY_WEEKS = 260
