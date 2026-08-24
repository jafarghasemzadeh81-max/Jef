#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
═══════════════════════════════════════════════════════════════════════════
         ADVANCED TRADING BOT v13.0 - COMPLETE SELF-HEALING VERSION
═══════════════════════════════════════════════════════════════════════════

✅ سیستم خطایابی کامل در هر بخش
✅ تست اتصال به بایننس
✅ 15+ اندیکاتور تکنیکال
✅ خودآموزی خودکار
✅ یادگیری تطبیقی پیشرفته
✅ بک‌تست واقعی

نسخه کامل - بدون هیچ خلاصه‌سازی
"""

# ============================================================================
# بخش 1: ایمپورت کتابخانه‌ها
# ============================================================================

import os
import sys
import time
import json
import math
import threading
import traceback
import shutil
from typing import List, Dict, Any, Optional, Tuple
from collections import deque
from datetime import datetime
from functools import wraps

import requests
import numpy as np
import pandas as pd

# scikit-learn برای مدل یادگیری ماشین واقعی (جایگزین/تکمیل سیستم همبستگی‌محور قبلی).
# اختیاری است: اگر نصب نباشد (مثلاً روی محیط‌های محدود مثل Termux)، ربات کاملاً عادی کار می‌کند
# و فقط این بخش غیرفعال می‌ماند - هیچ‌جای دیگر کد به این کتابخانه وابسته نیست.
try:
    from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import roc_auc_score, accuracy_score, brier_score_loss
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# XGBoost is the primary modern tabular model. It is optional so the bot never dies
# if the package is unavailable (for example on a fresh Termux install).
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
    try:
        import xgboost as _xgb
        XGBOOST_VERSION = getattr(_xgb, "__version__", "unknown")
    except Exception:
        XGBOOST_VERSION = "unknown"
except Exception:
    XGBClassifier = None
    XGBOOST_AVAILABLE = False
    XGBOOST_VERSION = "not-installed"

try:
    from catboost import CatBoostClassifier
    CATBOOST_AVAILABLE = True
except Exception:
    CatBoostClassifier = None
    CATBOOST_AVAILABLE = False

# مهم: خروجی استاندارد را روی UTF-8 اجبار می‌کنیم و خطاهای انکودینگ را جایگزین می‌کنیم، نه کرش.
# بدون این، وقتی برنامه در پس‌زمینه/nohup اجرا می‌شود (که برای اجرای بیش از چند ساعت معمول است)،
# پایتون گاهی stdout را با انکودینگ محدودتر از UTF-8 باز می‌کند و چاپ نمادهایی مثل نام‌های
# غیرلاتین (مثلاً برخی توکن‌های میمی در بایننس) با UnicodeEncodeError کل ترد را بی‌صدا می‌کشد.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ============================================================================
# بخش 2: تنظیمات اصلی (CONFIG) - کامل
# ============================================================================

# دریافت آرگومان‌های خط فرمان
KLINE_INTERVAL = sys.argv[1].strip() if len(sys.argv) > 1 else "1h"
LEVERAGE = int(sys.argv[2]) if len(sys.argv) > 2 else 25

# تشخیص خودکار مسیر داده (چندسکویی)
def get_default_data_dir() -> str:
    # اگر متغیر محیطی DATA_DIR تنظیم شده باشد (مثلاً روی Railway با یک Volume متصل)، همان استفاده می‌شود
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        return env_dir
    try:
        if os.name == 'nt':
            return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'TradingBot')
        elif hasattr(os, 'uname') and os.uname().sysname == 'Darwin':
            return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'TradingBot')
        else:
            if os.path.exists('/sdcard/Download/'):
                return '/sdcard/Download/'
            return os.path.join(os.path.expanduser('~'), '.tradingbot')
    except Exception as e:
        print(f"❌ خطا در تشخیص مسیر داده: {e}")
        return os.path.join(os.path.expanduser('~'), '.tradingbot')

DATA_DIR = get_default_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
print(f"📁 مسیر داده: {DATA_DIR}")

# مسیرهای فایل‌ها
PATHS = {
    "HISTORY_FILE": os.path.join(DATA_DIR, "coin_history.json"),
    "SIGNAL_HISTORY_FILE": os.path.join(DATA_DIR, "signal_history.json"),
    "FINAL_SIGNAL_FILE": os.path.join(DATA_DIR, "final_signals.json"),
    "ANALYZER_OUTPUT_FILE": os.path.join(DATA_DIR, "pro_analyzer_output.json"),
    "FILTER_JSON": os.path.join(DATA_DIR, "symbols_filter.json"),
    "OPTIMIZED_PARAMS_FILE": os.path.join(DATA_DIR, "optimized_params.json"),
    "FEATURE_WEIGHTS_FILE": os.path.join(DATA_DIR, "feature_weights.json"),
    "PATTERNS_FILE": os.path.join(DATA_DIR, "learned_patterns.json"),
    "AUTO_LEARN_QUEUE": os.path.join(DATA_DIR, "auto_learn_queue.json"),
    "PERFORMANCE_REPORT": os.path.join(DATA_DIR, "performance_report.json"),
    "ML_MODEL_FILE": os.path.join(DATA_DIR, "ml_model.joblib"),
    "DEBUG_LOG": os.path.join(DATA_DIR, "debug.log"),
    "ARCHIVE_FILE": os.path.join(DATA_DIR, "trades_archive.json"),
    "AUTOPILOT_STATE": os.path.join(DATA_DIR, "autopilot_state.json"),
    "CONFIG_BACKUP_DIR": os.path.join(DATA_DIR, "config_backups"),
}

# تنظیمات اصلی
CONFIG = {
    # اجرا
    "CHECK_INTERVAL": 150,
    "KLINE_INTERVAL": KLINE_INTERVAL,
    
    # آستانه‌های سیگنال
    "PUMP_THRESHOLD": 2.2,   # کمی کاهش‌یافته نسبت به 2.8 برای افزایش تعداد سیگنال - نه به‌اندازه‌ی مقدار تستی قدیمی (1.6)
    "DUMP_THRESHOLD": -2.2,
    "MIN_CONFIDENCE_SCORE": 6,  # به مقدار پایدار قبلی برگشت (5.5 با نمونه‌ی کم باعث افت واقعی کیفیت شد)
    "WEIGHT_SHARPEN_EXPONENT_MAX": 2.0,   # حداکثر شدت تشدید - فقط وقتی وزن‌ها با نمونه‌ی زیاد پخته شده باشند
    "WEIGHT_SHARPEN_MIN_TRADES": 100,     # زیر این تعداد معامله، اصلاً تشدید انجام نمی‌شود (خطر تشدید نویز)
    "WEIGHT_SHARPEN_FULL_TRADES": 300,    # از این تعداد به بعد، تشدید کامل (MAX) اعمال می‌شود

    # ML AutoPilot v3: model zoo + walk-forward + automatic rollback.
    # مدل اصلی XGBoost است؛ اگر نصب نباشد، HistGradientBoosting/ExtraTrees/Logistic
    # به‌صورت خودکار تست می‌شوند. مدل بد هرگز وارد امتیاز اصلی نمی‌شود.
    "ML_MIN_TRADES_TO_TRAIN": 60,
    "ML_RETRAIN_INTERVAL": 25,
    "ML_MAX_INFLUENCE": 0.18,
    "ML_FULL_MATURITY_TRADES": 400,
    "ML_MIN_AUC_FOR_INFLUENCE": 0.56,
    "ML_FULL_AUC_FOR_INFLUENCE": 0.65,
    "ML_MIN_WF_FOLDS": 3,
    "ML_MIN_WF_AUC": 0.56,
    "ML_MAX_WF_AUC_STD": 0.08,
    "ML_MIN_TRAIN_SAMPLES": 60,
    "ML_TEST_BLOCK": 20,
    "ML_WF_GAP": 8,
    "ML_MODEL_VERSION": 3,
    "ML_AUTO_HEAL": True,
    "ML_REQUIRE_BRIER_MAX": 0.26,
    "ML_ALLOW_PROVISIONAL_MODEL": True,
    # آستانه‌ی اضافه بر اساس رژیم بازار - VOLATILE از قبل فیلتر سخت‌گیرانه دارد و جواب داده (وین‌ریت 55%).
    # حالا با نمونه‌ی بزرگ و پایدار (108 معامله)، TRENDING هم به‌طور پیوسته ضعیف عمل کرده (35%)
    # با اینکه 70% حجم سیگنال از همینجاست - آستانه‌ی متوسط (نه به‌شدت VOLATILE) تا حجم زیاد افت نکند
    "REGIME_CONFIDENCE_ADJUSTMENT": {
        "VOLATILE": 1.5,
        "TRENDING": 1.0,
        "UNKNOWN": 0.5,
    },
    "REGIME_MIN_TRADES_FOR_ADJUST": 25,     # حداقل نمونه‌ی هر رژیم قبل از تنظیم خودکار آستانه‌اش
    "REGIME_MAX_ADJUSTMENT": 2.5,           # سقف افزایش آستانه برای هر رژیم
    "REGIME_ADJUSTMENT_STEP": 0.3,          # حداکثر تغییر آستانه در هر دور بهینه‌سازی (تدریجی، نه پرشی)
    "REGIME_ADJUSTMENT_SENSITIVITY": 0.15,  # هر چقدر بزرگ‌تر، به فاصله‌ی وین‌ریت رژیم حساس‌تر می‌شود
    
    # آستانه‌های تطبیقی
    "ADAPTIVE_PUMP_THRESHOLD": False,
    "PUMP_THRESHOLD_BASE": 2.8,
    "PUMP_THRESHOLD_MIN": 1.5,
    "PUMP_THRESHOLD_MAX": 5.0,
    
    # محدودیت‌های بازار
    "KLINE_LIMIT": 1000,
    "MIN_QUOTE_VOLUME": 500000,
    "MAX_SPREAD_PCT": 0.001,
    "MAX_24H_CHANGE": 50.0,
    
    # مدیریت ریسک
    "ACCOUNT_BALANCE": 1000.0,
    "RISK_PERCENT": 1.0,
    "LEVERAGE": LEVERAGE,
    "MAX_RISK_PER_DAY": 5.0,
    "MIN_RISK_PERCENT": 0.5,
    "MAX_RISK_PERCENT": 2.0,
    
    # کارمزد و لغزش
    "COMMISSION_PCT": 0.0004,
    "SLIPPAGE_PCT": 0.0005,
    
    # اندیکاتورها
    "EMA_SHORT": 20,
    "EMA_MED": 50,
    "EMA_LONG": 100,
    "RSI_PERIOD": 14,
    "ATR_PERIOD": 14,
    
    # حد ضرر و حد سود
    "ATR_MULT_SL": 2.0,
    "ATR_MULT_MIN": 1.2,
    "ATR_MULT_MAX": 3.5,
    "TP_ATR_MULTS": [2.0, 3.0, 4.0],  # TP1 برابر با فاصله‌ی SL شد (1R) به‌جای 0.5R قبلی - نیاز به وین‌ریت کمتر برای سودآوری
    
    # بک‌تست
    "BACKTEST_CANDLES": 1000,
    "BACKTEST_MAX_HOLD": 24,   # منسوخ - برای سازگاری نگه داشته شده؛ به‌جایش از get_max_hold_candles() استفاده می‌شود
    "BACKTEST_MIN_REQUIRED": 60,
    
    # نوسان
    "VOLATILITY_REGIME_ATR_RATIO": 0.012,
    "VOLATILITY_LOW_THRESHOLD": 0.005,
    "VOLATILITY_HIGH_THRESHOLD": 0.025,
    
    # یادگیری
    "WF_TRAIN_RATIO": 0.7,
    "LEARNING_WINDOW": 100,
    "ADAPTIVE_UPDATE_INTERVAL": 24,
    "MIN_TRADES_FOR_LEARNING": 30,       # حداقل نمونه برای اینکه همبستگی آماری معنی‌دار باشد
    "MIN_TRADES_FOR_CORRELATION": 15,    # حداقل نمونه برای محاسبه همبستگی هر فیچر
    "LEARNING_RATE": 0.1,
    "MIN_WF_TEST_TRADES": 8,             # حداقل نمونه در بخش تست walk-forward
    "LEARNING_REPORT_INTERVAL_HOURS": 1, # هر چند ساعت گزارش یادگیری به تلگرام ارسال شود
    
    # بهینه‌سازی
    "GRID_SEARCH_ENABLED": True,
    "GRID_PARAMS": {
        "ATR_MULT_SL": [1.2, 1.5, 2.0, 2.5],
        "EMA_SHORT": [8, 12, 20],
        "EMA_MED": [26, 34, 50],
    },
    
    # فیلترهای کیفیت
    "REQUIRE_VOLUME_SPIKE": True,
    "MIN_VOLUME_RATIO": 1.2,
    "MAX_CONSECUTIVE_LOSSES": 5,
    "COOLDOWN_AFTER_LOSS": 3600,
    
    # خودآموزی
    "AUTO_LEARN_HOURS": 24,               # منسوخ - جایگزین با MAX_HOLD_MINUTES (متناسب با تایم‌فریم)
    "MAX_HOLD_MINUTES": 30,                # اسکالپ: نتیجه باید حداکثر تا ۳۰ دقیقه مشخص شود
    "AUTO_LEARN_ENABLED": True,
    "AUTO_LEARN_PATH_BASED": True,        # بررسی برخورد SL/TP در طول مسیر، نه فقط قیمت پایانی

    # اندیکاتورهای تکمیلی
    "CCI_PERIOD": 20,
    "WILLIAMS_R_PERIOD": 14,
    "MFI_PERIOD": 14,
    "SUPERTREND_PERIOD": 10,
    "SUPERTREND_MULT": 3.0,
    "ADX_TREND_MIN": 20,
    
    # تلگرام (اختیاری)
    "TELEGRAM_BOT_TOKEN": "8044605578:AAEQEZcm8tNeZGD1FeYGw4bWe_n9Vb-pWFI",
    "TELEGRAM_CHAT_ID": "-1002906437733",
}

# ===================== AUTO-PILOT / SELF-HEALING v4 =====================
CONFIG.update({
    "MEMORY_MAX_SIZE": 2000,
    "ARCHIVE_MAX_SIZE": 100000,
    "ML_MIN_TRADES_TO_TRAIN": 60,
    "ML_RETRAIN_INTERVAL": 20,
    "ML_MAX_INFLUENCE": 0.15,
    "ML_PROVISIONAL_INFLUENCE": 0.05,
    "ML_MIN_AUC_FOR_INFLUENCE": 0.56,
    "ML_FULL_AUC_FOR_INFLUENCE": 0.66,
    "ML_MIN_WF_AUC": 0.56,
    "ML_MAX_WF_AUC_STD": 0.20,
    "ML_MIN_WF_FOLDS": 3,
    "ML_REQUIRE_BRIER_MAX": 0.29,
    "ML_ALLOW_PROVISIONAL_MODEL": True,
    "ML_AUTO_HEAL": True,
    "ML_PROBABILITY_FLOOR": 0.05,
    "ML_PROBABILITY_CEILING": 0.95,
    "ML_DIRECTION_MIN_SAMPLES": 25,
    "ML_REGIME_MIN_SAMPLES": 25,
    "REGIME_MIN_TRADES_FOR_ADJUST": 25,
    "REGIME_MAX_ADJUSTMENT": 0.45,
    "REGIME_ADJUSTMENT_STEP": 0.05,
    "REGIME_BAD_WINRATE": 0.47,
    "REGIME_GOOD_WINRATE": 0.56,
    "MIN_CONFIDENCE_SCORE": 6.0,
    "PUMP_THRESHOLD": 1.8,
    "DUMP_THRESHOLD": -1.8,
    "MAX_CONSECUTIVE_LOSSES": 4,
    "COOLDOWN_AFTER_LOSS": 1800,
    "SYMBOL_COOLDOWN_SEC": 1800,
    "MAX_PENDING_PER_SYMBOL": 1,
    "MAX_NEW_SIGNALS_PER_CYCLE": 10,
    "MAX_NEW_SIGNALS_PER_HOUR": 50,
    "MAX_SAME_DIRECTION_RATIO": 0.80,
    "AUTO_HEAL_INTERVAL_SEC": 300,
    "MAX_EFFECTIVE_CONFIDENCE": 6.7,
    "SIGNAL_STARVATION_MINUTES": 20,
    "SIGNAL_STARVATION_THRESHOLD_MIN": 1.4,
    "SIGNAL_STARVATION_THRESHOLD_MAX": 1.9,
    "SIGNAL_STARVATION_RECOVERY_STEP": 0.15,
    "AUTO_HEAL_MIN_TRADES": 30,
    "ROLLBACK_IF_PF_DROP": 0.15,
    "ROLLBACK_IF_WR_DROP": 0.10,
    "RECENT_PERFORMANCE_WINDOW": 80,
    "DIRECTION_WINDOW": 120,
    "REGIME_WINDOW": 160,
    "DEDUP_WINDOW_SEC": 1800,
    "REQUIRE_CLOSED_CANDLE": True,
})

# ===================== FINAL STABILITY / SELF-HEALING POLICY =====================
# این لایه آخرین مرجع تنظیمات است؛ هیچ optimizer یا regime learner حق ندارد
# آستانه‌ای بالاتر از MAX_EFFECTIVE_CONFIDENCE بسازد و سیستم را بدون سیگنال رها کند.
CONFIG.update({
    "MIN_CONFIDENCE_SCORE": 6.0,
    "MAX_EFFECTIVE_CONFIDENCE": 6.4,
    "REGIME_MAX_ADJUSTMENT": 0.30,
    "REGIME_ADJUSTMENT_STEP": 0.05,
    "REGIME_BAD_WINRATE": 0.46,
    "REGIME_GOOD_WINRATE": 0.55,
    "PUMP_THRESHOLD": 1.8,
    "DUMP_THRESHOLD": -1.8,
    "SIGNAL_STARVATION_MINUTES": 12,
    "SIGNAL_STARVATION_THRESHOLD_MIN": 1.10,
    "SIGNAL_STARVATION_THRESHOLD_MAX": 1.80,
    "SIGNAL_STARVATION_RECOVERY_STEP": 0.20,
    "MAX_NEW_SIGNALS_PER_CYCLE": 8,
    "MAX_NEW_SIGNALS_PER_HOUR": 60,
    "FALLBACK_SCAN_AFTER_MINUTES": 12,
    "FALLBACK_CANDIDATES": 18,
    "FALLBACK_MIN_CONFIDENCE": 5.90,
    "MAX_PENDING_PER_SYMBOL": 1,
    "SYMBOL_COOLDOWN_SEC": 1200,
    "DEDUP_WINDOW_SEC": 1200,
    "AUTO_HEAL_INTERVAL_SEC": 180,
    "ML_RETRAIN_INTERVAL": 15,
    "ML_MAX_INFLUENCE": 0.15,
    "ML_PROVISIONAL_INFLUENCE": 0.03,
    "ML_MIN_AUC_FOR_INFLUENCE": 0.56,
    "ML_MIN_WF_AUC": 0.56,
    "ML_MAX_WF_AUC_STD": 0.20,
    "ML_REQUIRE_BRIER_MAX": 0.29,
    "ML_ALLOW_PROVISIONAL_MODEL": True,
})

BASE_CONFIG = CONFIG.copy()

# قفل سراسری برای جلوگیری از تداخل بین ترد یادگیری خودکار و حلقه اصلی
# هنگام نوشتن روی CONFIG (توسط AdaptiveParameterOptimizer) یا خواندن دسته‌ای از آن
CONFIG_LOCK = threading.Lock()


# ============================================================================
# بخش 3: سیستم لاگینگ و خطایابی - کامل
# ============================================================================

class DebugLogger:
    """سیستم ثبت خطاها و لاگ‌های پیشرفته"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info_logs = []
        self.debug_logs = []
        self.log_file = PATHS["DEBUG_LOG"]
        self._clear_old_log()
    
    def _clear_old_log(self):
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    lines = f.readlines()
                if len(lines) > 2000:
                    with open(self.log_file, 'w') as f:
                        f.writelines(lines[-1000:])
        except Exception:
            pass
    
    def _write_to_file(self, level: str, message: str):
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                f.write(f"[{timestamp}] [{level}] {message}\n")
        except Exception:
            pass
    
    def _safe_print(self, text: str):
        """چاپ امن - حتی اگر انکودینگ ترمینال محدود باشد (مثلاً روی Termux در پس‌زمینه)، هرگز کرش نمی‌کند
        و به‌جایش کاراکترهای غیرقابل‌نمایش را با ؟ جایگزین می‌کند. این دقیقاً همون چیزیه که نبودنش
        باعث می‌شد یک نماد غیرلاتین (مثل توکن‌های میمی با اسم چینی) کل ترد یادگیری را بی‌صدا بکشد."""
        try:
            print(text)
        except UnicodeEncodeError:
            try:
                enc = sys.stdout.encoding or "utf-8"
                print(text.encode(enc, errors="replace").decode(enc, errors="replace"))
            except Exception:
                pass
        except Exception:
            pass

    def error(self, message: str, show_traceback: bool = True):
        self.errors.append({"time": time.time(), "message": message})
        self._write_to_file("ERROR", message)
        self._safe_print(f"\n❌ خطا: {message}")
        if show_traceback:
            try:
                traceback.print_exc()
            except Exception:
                pass
    
    def warning(self, message: str):
        self.warnings.append({"time": time.time(), "message": message})
        self._write_to_file("WARNING", message)
        self._safe_print(f"⚠️ اخطار: {message}")
    
    def info(self, message: str):
        self.info_logs.append({"time": time.time(), "message": message})
        self._write_to_file("INFO", message)
        self._safe_print(f"ℹ️ {message}")
    
    def debug(self, message: str):
        self.debug_logs.append({"time": time.time(), "message": message})
        self._write_to_file("DEBUG", message)
        # در حالت debug، نمایش نمی‌دهیم تا صفحه پر نشود
        # print(f"🔍 {message}")
    
    def get_report(self) -> dict:
        return {
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "total_debug": len(self.debug_logs),
            "last_error": self.errors[-1] if self.errors else None,
            "last_warning": self.warnings[-1] if self.warnings else None,
            "errors": self.errors[-20:],
            "warnings": self.warnings[-20:],
        }
    
    def print_summary(self):
        print("\n" + "="*50)
        print("📊 خلاصه خطاها:")
        print(f"   خطاها: {len(self.errors)}")
        print(f"   اخطارها: {len(self.warnings)}")
        if self.errors:
            print(f"   آخرین خطا: {self.errors[-1]['message']}")
        if self.warnings:
            print(f"   آخرین اخطار: {self.warnings[-1]['message']}")
        print("="*50 + "\n")

logger = DebugLogger()


def _atomic_write_json(path: str, obj) -> bool:
    """نوشتن اتمیک JSON روی دیسک - برای جلوگیری از خراب شدن فایل هنگام کرش وسط نوشتن"""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp_path = f"{path}.tmp{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return True
    except Exception as e:
        logger.error(f"خطا در نوشتن اتمیک {path}: {e}")
        return False


# ============================================================================
# بخش 4: تست اتصال به بایننس - کامل
# ============================================================================

def test_binance_connection() -> dict:
    """تست کامل اتصال به بایننس با جزئیات"""
    logger.info("🔍 در حال تست اتصال به بایننس...")
    
    result = {
        "success": False,
        "api_status": None,
        "fapi_status": None,
        "symbols_count": 0,
        "usdt_count": 0,
        "sample_data": None,
        "error": None,
        "latency": None
    }
    
    try:
        # تست 1: اتصال به API عمومی
        logger.debug("تست اتصال به api.binance.com...")
        start_time = time.time()
        resp = requests.get("https://api.binance.com/api/v3/time", timeout=10)
        result["latency"] = round((time.time() - start_time) * 1000, 2)
        result["api_status"] = resp.status_code
        
        logger.debug(f"پاسخ API: {resp.status_code} (تأخیر: {result['latency']}ms)")
        
        if resp.status_code != 200:
            result["error"] = f"API ناموفق: {resp.status_code}"
            logger.error(result["error"])
            return result
        
        # تست 2: دریافت زمان سرور
        server_time = resp.json().get("serverTime")
        if server_time:
            result["server_time"] = server_time
            logger.debug(f"زمان سرور: {datetime.fromtimestamp(server_time/1000)}")
        
        # تست 3: دریافت تیکرهای فیوچرز
        logger.debug("دریافت تیکرها از fapi.binance.com...")
        resp2 = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=15)
        result["fapi_status"] = resp2.status_code
        
        if resp2.status_code != 200:
            result["error"] = f"FAPI ناموفق: {resp2.status_code}"
            logger.error(result["error"])
            return result
        
        data = resp2.json()
        result["symbols_count"] = len(data)
        logger.debug(f"تعداد کل نمادها: {result['symbols_count']}")
        
        # فیلتر نمادهای USDT
        usdt_symbols = []
        for d in data:
            sym = d.get("symbol", "")
            if sym.endswith("USDT"):
                usdt_symbols.append(d)
        
        result["usdt_count"] = len(usdt_symbols)
        logger.debug(f"تعداد نمادهای USDT: {result['usdt_count']}")
        
        if result["usdt_count"] > 0:
            # جمع‌آوری نمونه داده
            sample = usdt_symbols[0]
            result["sample_data"] = {
                "symbol": sample.get("symbol"),
                "price": sample.get("lastPrice"),
                "change_24h": sample.get("priceChangePercent"),
                "volume": sample.get("volume"),
                "high": sample.get("highPrice"),
                "low": sample.get("lowPrice"),
            }
            logger.debug(f"نمونه: {result['sample_data']['symbol']} - تغییر 24h: {result['sample_data']['change_24h']}%")
            
            # محاسبه میانگین تغییرات
            changes = []
            for d in usdt_symbols[:100]:
                try:
                    ch = float(d.get("priceChangePercent", 0))
                    changes.append(abs(ch))
                except Exception:
                    pass
            
            if changes:
                result["avg_volatility"] = round(sum(changes) / len(changes), 2)
                logger.debug(f"میانگین نوسانات: {result['avg_volatility']}%")
        
        result["success"] = True
        logger.info("✅ اتصال به بایننس با موفقیت برقرار شد")
        
        # نمایش نتیجه تست
        print("\n" + "="*60)
        print("📊 نتیجه تست اتصال به بایننس:")
        print(f"   وضعیت: {'✅ موفق' if result['success'] else '❌ ناموفق'}")
        print(f"   API وضعیت: {result['api_status']}")
        print(f"   FAPI وضعیت: {result['fapi_status']}")
        print(f"   تأخیر: {result['latency']}ms")
        print(f"   تعداد کل نمادها: {result['symbols_count']}")
        print(f"   تعداد نمادهای USDT: {result['usdt_count']}")
        if result.get("avg_volatility"):
            print(f"   میانگین نوسانات: {result['avg_volatility']}%")
        if result.get("sample_data"):
            print(f"   نمونه: {result['sample_data']['symbol']} = {result['sample_data']['change_24h']}%")
        print("="*60 + "\n")
        
    except requests.exceptions.Timeout:
        result["error"] = "تایم اوت - اتصال اینترنت خود را بررسی کنید یا از VPN استفاده کنید"
        logger.error(result["error"])
    except requests.exceptions.ConnectionError:
        result["error"] = "خطا در اتصال - ممکن است نیاز به VPN داشته باشید"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"خطای غیرمنتظره: {e}")
    
    return result
# ============================================================================
# بخش 5: کلاس حافظه عملکرد پیشرفته (PerformanceMemory) - کامل
# ============================================================================

class PerformanceMemory:
    """حافظه عملکرد کامل برای یادگیری تطبیقی"""
    
    def __init__(self, max_size: int = 200, short_term_size: int = 50):
        self.trades: deque = deque(maxlen=max(2000, max_size))
        self.short_term_trades: deque = deque(maxlen=max(100, short_term_size))
        self.signal_features: deque = deque(maxlen=max_size)
        self.param_performance: dict = {}
        self.performance_history: list = []
        self.last_analysis_time: float = 0
        self.analysis_interval: int = 3600
        self._load_history()
        self._load_archive_into_memory_if_needed()
        logger.debug(f"PerformanceMemory راه‌اندازی شد - ظرفیت: {max_size}")

    def _load_history(self):
        try:
            if os.path.exists(PATHS["PERFORMANCE_REPORT"]):
                with open(PATHS["PERFORMANCE_REPORT"], "r") as f:
                    data = json.load(f)
                    if "trades" in data:
                        for trade in data["trades"][-self.trades.maxlen:]:
                            self.trades.append(trade)
                            self.short_term_trades.append(trade)
                logger.info(f"{len(self.trades)} معامله از تاریخچه بارگذاری شد")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری تاریخچه: {e}")

    def _save_history(self):
        payload = {"trades": list(self.trades), "timestamp": time.time(), "memory_limit": self.trades.maxlen}
        _atomic_write_json(PATHS["PERFORMANCE_REPORT"], payload)
        try:
            archive = []
            if os.path.exists(PATHS["ARCHIVE_FILE"]):
                with open(PATHS["ARCHIVE_FILE"], "r", encoding="utf-8") as f:
                    obj = json.load(f)
                    archive = obj.get("trades", obj if isinstance(obj, list) else [])
            # append only the newest record; deduplicate by timestamp+symbol+direction
            seen = {(str(t.get("timestamp")), t.get("symbol"), t.get("direction"), t.get("which_target")) for t in archive[-100000:]}
            for t in list(self.trades)[-20:]:
                key = (str(t.get("timestamp")), t.get("symbol"), t.get("direction"), t.get("which_target"))
                if key not in seen:
                    archive.append(t); seen.add(key)
            archive = archive[-CONFIG.get("ARCHIVE_MAX_SIZE", 100000):]
            _atomic_write_json(PATHS["ARCHIVE_FILE"], {"trades": archive, "timestamp": time.time()})
        except Exception as e:
            logger.warning(f"Archive save failed: {e}")

    def _load_archive_into_memory_if_needed(self):
        try:
            p = PATHS["ARCHIVE_FILE"]
            if os.path.exists(p) and len(self.trades) < 20:
                with open(p, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                archive = obj.get("trades", obj if isinstance(obj, list) else [])
                for t in archive[-self.trades.maxlen:]:
                    self.trades.append(t)
                    if len(self.short_term_trades) < self.short_term_trades.maxlen:
                        self.short_term_trades.append(t)
                logger.info(f"📚 آرشیو دائمی بارگذاری شد: {len(archive)} معامله")
        except Exception as e:
            logger.warning(f"Archive load failed: {e}")

    def add_trade_result(self, trade_data: dict) -> None:
        """ذخیره نتیجه معامله با تمام جزئیات"""
        try:
            trade_record = {
                "timestamp": time.time(),
                "symbol": trade_data.get("symbol"),
                "direction": trade_data.get("direction"),
                "entry_price": trade_data.get("entry"),
                "exit_price": trade_data.get("exit"),
                "return_pct": trade_data.get("return_pct", 0.0),
                "win": trade_data.get("return_pct", 0.0) > 0,
                "features": trade_data.get("features", {}),
                "signal_confidence": trade_data.get("confidence", 0),
                "holding_time": trade_data.get("holding_time", 0),
                "max_favorable": trade_data.get("max_favorable", 0),
                "max_adverse": trade_data.get("max_adverse", 0),
                # outcome_label is deliberately separate from win: TIMEOUT is not a clean ML label.
                "which_target": trade_data.get("which_target"),
                "outcome_label": trade_data.get("outcome_label"),
                "auto_learned": bool(trade_data.get("auto_learned", False)),
                "pre_signal_change_15m": trade_data.get("pre_signal_change_15m"),
                "time_to_result_min": trade_data.get("time_to_result_min"),
                "mfe_pct": trade_data.get("mfe_pct"),
                "mae_pct": trade_data.get("mae_pct"),
            }
            self.trades.append(trade_record)
            self.short_term_trades.append(trade_record)
            self._save_history()
            self._update_param_stats(trade_record)
            
            win_emoji = "✅" if trade_record["win"] else "❌"
            logger.info(f"معامله ثبت شد: {trade_record['symbol']} {trade_record['direction']} {win_emoji} {trade_record['return_pct']:.2f}%")
            
        except Exception as e:
            logger.error(f"خطا در ثبت معامله: {e}")

    def _update_param_stats(self, trade: dict) -> None:
        """به‌روزرسانی آمار پارامترها"""
        try:
            features = trade.get("features", {})
            params = features.get("params_used", {})
            if params and trade.get("win", False):
                for key, value in params.items():
                    if key not in self.param_performance:
                        self.param_performance[key] = {"values": [], "wins": 0, "total": 0}
                    self.param_performance[key]["values"].append(value)
                    self.param_performance[key]["wins"] += 1
                    self.param_performance[key]["total"] += 1
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی آمار پارامترها: {e}")

    def get_winrate(self, window: Optional[int] = None) -> float:
        """محاسبه نرخ موفقیت در بازه مشخص"""
        try:
            if not self.trades:
                return 0.0
            window = window or len(self.trades)
            recent = list(self.trades)[-window:]
            if not recent:
                return 0.0
            wins = sum(1 for t in recent if t.get("win", False))
            return (wins / len(recent)) * 100.0
        except Exception as e:
            logger.error(f"خطا در محاسبه وین‌ریت: {e}")
            return 0.0

    def get_short_term_winrate(self) -> float:
        """نرخ موفقیت معاملات اخیر"""
        try:
            if not self.short_term_trades:
                return 0.0
            wins = sum(1 for t in self.short_term_trades if t.get("win", False))
            return (wins / len(self.short_term_trades)) * 100.0
        except Exception as e:
            logger.error(f"خطا در محاسبه وین‌ریت کوتاه‌مدت: {e}")
            return 0.0

    def get_average_return(self, window: Optional[int] = None) -> float:
        """میانگین بازده معاملات"""
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if not trades:
                return 0.0
            returns = [t.get("return_pct", 0) for t in trades]
            return sum(returns) / len(returns)
        except Exception as e:
            logger.error(f"خطا در محاسبه میانگین بازده: {e}")
            return 0.0

    def get_profit_factor(self, window: Optional[int] = None) -> float:
        """فاکتور سود (مجموع سودها / مجموع ضررها)"""
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            total_profit = sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) > 0)
            total_loss = abs(sum(t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) < 0))
            if total_loss == 0:
                return total_profit if total_profit > 0 else 1.0
            return total_profit / total_loss
        except Exception as e:
            logger.error(f"خطا در محاسبه فاکتور سود: {e}")
            return 1.0

    def get_sharpe_ratio(self, window: Optional[int] = None, risk_free_rate: float = 0.02) -> float:
        """نسبت شارپ - معیار عملکرد adjusted برای ریسک"""
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if len(trades) < 2:
                return 0.0
            returns = [t.get("return_pct", 0) for t in trades]
            avg_return = sum(returns) / len(returns)
            std_return = np.std(returns) if len(returns) > 1 else 1.0
            if std_return == 0:
                return 0.0
            annualized_return = avg_return * 252
            annualized_std = std_return * (252 ** 0.5)
            return (annualized_return - risk_free_rate) / annualized_std
        except Exception as e:
            logger.error(f"خطا در محاسبه نسبت شارپ: {e}")
            return 0.0

    def get_calmar_ratio(self, window: Optional[int] = None) -> float:
        """نسبت کالمار (بازده / حداکثر افت)"""
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if not trades:
                return 0.0
            returns = [t.get("return_pct", 0) for t in trades]
            avg_return = sum(returns) / len(returns)
            cumulative = 0
            peak = 0
            max_drawdown = 0
            for r in returns:
                cumulative += r
                if cumulative > peak:
                    peak = cumulative
                drawdown = (peak - cumulative) if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            if max_drawdown == 0:
                return avg_return * 100 if avg_return > 0 else 0
            return avg_return / max_drawdown
        except Exception as e:
            logger.error(f"خطا در محاسبه نسبت کالمار: {e}")
            return 0.0

    def get_expectancy(self, window: Optional[int] = None) -> float:
        """امید ریاضی (Expected Value) هر معامله"""
        try:
            trades = list(self.trades)
            if window:
                trades = trades[-window:]
            if not trades:
                return 0.0
            avg_win = 0.0
            avg_loss = 0.0
            win_count = 0
            loss_count = 0
            for t in trades:
                ret = t.get("return_pct", 0)
                if ret > 0:
                    avg_win += ret
                    win_count += 1
                elif ret < 0:
                    avg_loss += ret
                    loss_count += 1
            if win_count > 0:
                avg_win /= win_count
            if loss_count > 0:
                avg_loss /= loss_count
            win_rate = win_count / len(trades) if trades else 0
            loss_rate = loss_count / len(trades) if trades else 0
            return (win_rate * avg_win) + (loss_rate * avg_loss)
        except Exception as e:
            logger.error(f"خطا در محاسبه امید ریاضی: {e}")
            return 0.0

    def get_feature_correlation(self, feature_name: str, window: Optional[int] = None) -> float:
        """محاسبه همبستگی بین یک ویژگی و موفقیت معاملات - با window می‌توان فقط N معامله‌ی اخیر را
        در نظر گرفت (نه کل تاریخچه)، تا وزن‌ها به رفتار قدیمی/رژیم بازار گذشته overfit نشوند"""
        try:
            min_samples = CONFIG.get("MIN_TRADES_FOR_CORRELATION", 15)
            trades_source = list(self.trades)[-window:] if window else list(self.trades)
            if len(trades_source) < min_samples:
                return 0.0
            feature_values = []
            outcomes = []
            for trade in trades_source:
                feat_val = trade.get("features", {}).get(feature_name)
                if feat_val is not None and isinstance(feat_val, (int, float)):
                    feature_values.append(float(feat_val))
                    outcomes.append(1 if trade.get("win", False) else 0)
            if len(feature_values) < min_samples:
                return 0.0
            feature_values = np.array(feature_values)
            outcomes = np.array(outcomes)
            if np.std(feature_values) == 0 or np.std(outcomes) == 0:
                return 0.0
            corr = np.corrcoef(feature_values, outcomes)[0, 1]
            return float(corr) if not np.isnan(corr) else 0.0
        except Exception as e:
            logger.error(f"خطا در محاسبه همبستگی {feature_name}: {e}")
            return 0.0

    def get_feature_importance(self) -> dict:
        """محاسبه اهمیت هر ویژگی در موفقیت معاملات"""
        try:
            importance = {}
            all_features = set()
            for trade in self.trades:
                all_features.update(trade.get("features", {}).keys())
            for feature in all_features:
                corr = self.get_feature_correlation(feature)
                importance[feature] = abs(corr)
            return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        except Exception as e:
            logger.error(f"خطا در محاسبه اهمیت ویژگی‌ها: {e}")
            return {}

    def get_best_params_history(self, trades_override: Optional[list] = None) -> dict:
        """استخراج تاریخچه پارامترهای موفق - در صورت پاس‌دادن trades_override (مثلاً فقط بخش train
        در اعتبارسنجی walk-forward)، فقط همون زیرمجموعه بررسی می‌شود، نه کل تاریخچه"""
        param_history: dict = {}
        try:
            trades_source = trades_override if trades_override is not None else self.trades
            for trade in trades_source:
                features = trade.get("features", {})
                params = features.get("params_used", {})
                if params and trade.get("win", False):
                    for key, value in params.items():
                        if key not in param_history:
                            param_history[key] = []
                        param_history[key].append(value)
        except Exception as e:
            logger.error(f"خطا در استخراج تاریخچه پارامترها: {e}")
        return param_history

    def get_optimal_params(self, param_name: str) -> Optional[float]:
        """دریافت مقدار بهینه برای یک پارامتر خاص"""
        try:
            if param_name not in self.param_performance:
                return None
            stats = self.param_performance[param_name]
            if not stats["values"]:
                return None
            return float(np.median(stats["values"]))
        except Exception as e:
            logger.error(f"خطا در دریافت پارامتر بهینه {param_name}: {e}")
            return None

    def get_performance_trend(self, window: int = 20) -> str:
        """تحلیل روند عملکرد (صعودی/نزولی/ثابت)"""
        try:
            if len(self.performance_history) < window:
                return "INSUFFICIENT_DATA"
            recent = self.performance_history[-window:]
            winrates = [p.get("winrate_short", 0) for p in recent]
            if len(winrates) < 3:
                return "STABLE"
            x = list(range(len(winrates)))
            slope = np.polyfit(x, winrates, 1)[0]
            if slope > 0.5:
                return "IMPROVING"
            elif slope < -0.5:
                return "DECLINING"
            else:
                return "STABLE"
        except Exception as e:
            logger.error(f"خطا در تحلیل روند عملکرد: {e}")
            return "UNKNOWN"

    def get_market_regime_performance(self) -> dict:
        """عملکرد در رژیم‌های مختلف بازار"""
        regime_performance = {}
        try:
            for trade in self.trades:
                features = trade.get("features", {})
                regime = features.get("market_regime", "UNKNOWN")
                win = trade.get("win", False)
                if regime not in regime_performance:
                    regime_performance[regime] = {"wins": 0, "total": 0}
                regime_performance[regime]["total"] += 1
                if win:
                    regime_performance[regime]["wins"] += 1
            for regime in regime_performance:
                total = regime_performance[regime]["total"]
                wins = regime_performance[regime]["wins"]
                regime_performance[regime]["winrate"] = (wins / total * 100) if total > 0 else 0
        except Exception as e:
            logger.error(f"خطا در محاسبه عملکرد رژیم بازار: {e}")
        return regime_performance

    def get_summary(self) -> dict:
        """گزارش خلاصه از وضعیت"""
        return {
            "total_trades": len(self.trades),
            "short_term_trades": len(self.short_term_trades),
            "long_term_winrate": self.get_winrate(),
            "short_term_winrate": self.get_short_term_winrate(),
            "profit_factor": self.get_profit_factor(),
            "sharpe_ratio": self.get_sharpe_ratio(),
            "calmar_ratio": self.get_calmar_ratio(),
            "expectancy": self.get_expectancy(),
            "performance_trend": self.get_performance_trend(),
            "best_features": list(self.get_feature_importance().keys())[:5],
            "market_regimes": self.get_market_regime_performance()
        }

    def get_entry_timing_stats(self) -> dict:
        """تحلیل کیفیت زمان‌بندی ورود: قبل از سیگنال چقدر حرکت شده، احتمال رسیدن به TP1،
        میانگین زمان رسیدن به هدف، و اینکه معاملات بازنده چقدر به TP1 نزدیک شده بودند (MFE).
        این دقیقاً زنجیره Trigger → Entry Timing → TP1 Probability → Time-to-TP است."""
        try:
            auto_trades = [t for t in self.trades if t.get("auto_learned") and t.get("pre_signal_change_15m") is not None]
            if len(auto_trades) < 5:
                return {"available": False, "sample_size": len(auto_trades)}
            
            pre_moves = [abs(t["pre_signal_change_15m"]) for t in auto_trades]
            tp1_hits = [t for t in auto_trades if t.get("which_target") == "TP1"]
            sl_hits = [t for t in auto_trades if t.get("which_target") == "SL"]
            times_to_result = [t["time_to_result_min"] for t in auto_trades if t.get("time_to_result_min")]
            mfe_on_losses = [t["mfe_pct"] for t in sl_hits if t.get("mfe_pct") is not None]
            
            return {
                "available": True,
                "sample_size": len(auto_trades),
                "avg_pre_signal_move_pct": float(np.mean(pre_moves)) if pre_moves else None,
                "tp1_hit_rate_pct": (len(tp1_hits) / len(auto_trades)) * 100,
                "sl_hit_rate_pct": (len(sl_hits) / len(auto_trades)) * 100,
                "avg_time_to_result_min": float(np.mean(times_to_result)) if times_to_result else None,
                # میانگین اینکه معاملات بازنده چقدر (درصد) به سمت TP1 پیش رفته بودند قبل از برگشت و خوردن SL
                # عدد بالا (مثلاً نزدیک به فاصله‌ی TP1) یعنی سیگنال‌ها به‌طرز نزدیکی SL می‌خورند - نشانه‌ی ورود دیرهنگام
                "avg_mfe_on_losses_pct": float(np.mean(mfe_on_losses)) if mfe_on_losses else None,
            }
        except Exception as e:
            logger.error(f"خطا در محاسبه آمار زمان‌بندی ورود: {e}")
            return {"available": False, "sample_size": 0}

    def clear(self) -> None:
        """پاک کردن تمام حافظه"""
        self.trades.clear()
        self.short_term_trades.clear()
        self.signal_features.clear()
        self.param_performance.clear()
        self.performance_history.clear()
        logger.info("حافظه عملکرد پاک شد")
# ============================================================================
# بخش 6: کلاس بهینه‌ساز پارامتر (AdaptiveParameterOptimizer) - کامل
# ============================================================================

class AdaptiveParameterOptimizer:
    """بهینه‌ساز خودکار پارامترها بر اساس عملکرد گذشته"""
    
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.last_update_time: int = 0
        self.learning_rate: float = 0.1
        self.momentum: float = 0.9
        self.previous_updates: dict = {}
        self.performance_history: list = []
        # مهم: param_constraints باید قبل از _load_saved_params ساخته شود، چون آن تابع
        # به self.param_constraints نیاز دارد - قبلاً برعکس بود و همیشه silently fail می‌شد
        # (توسط try/except قورت داده می‌شد، پس پارامترهای ذخیره‌شده هیچ‌وقت واقعاً بارگذاری نمی‌شدند)
        self.param_constraints = {
            "ATR_MULT_SL": (1.0, 4.0),
            "EMA_SHORT": (5, 50),
            "EMA_MED": (20, 200),
            "RISK_PERCENT": (0.5, 3.0),
        }
        self.optimized_params: dict = self._load_saved_params()
        logger.debug("AdaptiveParameterOptimizer راه‌اندازی شد")

    def _load_saved_params(self) -> dict:
        try:
            if os.path.exists(PATHS["OPTIMIZED_PARAMS_FILE"]):
                with open(PATHS["OPTIMIZED_PARAMS_FILE"], "r") as f:
                    loaded = json.load(f)
                    validated = {}
                    for key, value in loaded.items():
                        if key in self.param_constraints:
                            min_val, max_val = self.param_constraints[key]
                            if isinstance(value, (int, float)):
                                clamped = max(min_val, min(max_val, value))
                                validated[key] = int(clamped) if isinstance(value, int) else clamped
                        else:
                            validated[key] = value
                    logger.info(f"پارامترهای ذخیره شده بارگذاری شد: {validated}")
                    return validated
        except Exception as e:
            logger.warning(f"خطا در بارگذاری پارامترها: {e}")
        return self._get_default_params()

    def _get_default_params(self) -> dict:
        return {
            "ATR_MULT_SL": CONFIG.get("ATR_MULT_SL", 2.0),
            "EMA_SHORT": CONFIG.get("EMA_SHORT", 20),
            "EMA_MED": CONFIG.get("EMA_MED", 50),
            "RISK_MULTIPLIER": 1.0,
            "LEARNING_RATE": 0.1,
        }

    def _save_params(self) -> None:
        if _atomic_write_json(PATHS["OPTIMIZED_PARAMS_FILE"], self.optimized_params):
            logger.debug("پارامترهای بهینه شده ذخیره شد")

    def optimize(self, force: bool = False) -> dict:
        """اجرای فرآیند بهینه‌سازی پارامترها"""
        try:
            current_hour = int(time.time() / 3600)
            
            if not force and (current_hour - self.last_update_time) < CONFIG["ADAPTIVE_UPDATE_INTERVAL"]:
                logger.debug("زمان کافی برای بهینه‌سازی مجدد نگذشته است")
                return self.optimized_params
            
            if len(self.memory.trades) < CONFIG["MIN_TRADES_FOR_LEARNING"]:
                logger.info(f"داده کافی برای بهینه‌سازی وجود ندارد (حداقل {CONFIG['MIN_TRADES_FOR_LEARNING']} معامله)")
                return self.optimized_params
            
            logger.info("🔄 شروع بهینه‌سازی خودکار پارامترها...")
            old_params = self.optimized_params.copy()

            # اعتبارسنجی Walk-Forward: قبل از هر چیز چک می‌کنیم که عملکرد اخیر (بخش تست)
            # به‌طرز مشکوکی بدتر از بخش قدیمی‌تر (train) نباشد - نشانه‌ی overfit شدن به نویز اخیر یا
            # شرایط بازار که دیگر برقرار نیست. در این حالت بهینه‌سازی را رد می‌کنیم.
            trades_sorted = sorted(self.memory.trades, key=lambda t: t.get("timestamp", 0))
            split_idx = int(len(trades_sorted) * CONFIG.get("WF_TRAIN_RATIO", 0.7))
            train_trades = trades_sorted[:split_idx]
            test_trades = trades_sorted[split_idx:]
            min_wf_test = CONFIG.get("MIN_WF_TEST_TRADES", 8)
            wf_active = len(test_trades) >= min_wf_test and len(train_trades) >= min_wf_test

            if wf_active:
                train_wr = (sum(1 for t in train_trades if t.get("win")) / len(train_trades)) * 100.0
                test_wr = (sum(1 for t in test_trades if t.get("win")) / len(test_trades)) * 100.0
                if test_wr < train_wr - 15:
                    logger.warning(
                        f"⚠️ Walk-forward: وین‌ریت بخش تست ({test_wr:.1f}%) به‌طرز قابل‌توجهی پایین‌تر از "
                        f"بخش train ({train_wr:.1f}%) است - بهینه‌سازی این دور رد شد تا از overfitting جلوگیری شود."
                    )
                    self.last_update_time = current_hour
                    return self.optimized_params
                logger.debug(f"Walk-forward OK - train winrate: {train_wr:.1f}% | test winrate: {test_wr:.1f}%")
            
            # استخراج تاریخچه پارامترهای موفق - فقط از بخش train (نه کل داده)، تا خود انتخاب پارامتر
            # بهینه هم به داده‌ی test "نگاه" نکرده باشد (نشت اعتبارسنجی/validation leakage)
            param_history = self.memory.get_best_params_history(train_trades if wf_active else None)
            
            # بهینه‌سازی ATR_MULT_SL
            if "ATR_MULT_SL" in param_history and len(param_history["ATR_MULT_SL"]) > 5:
                optimal_atr = np.median(param_history["ATR_MULT_SL"])
                self.optimized_params["ATR_MULT_SL"] = self._apply_learning_rate("ATR_MULT_SL", optimal_atr)
                logger.info(f"   📊 ATR_MULT_SL: {self.optimized_params['ATR_MULT_SL']:.2f}")
            
            # بهینه‌سازی EMA_SHORT
            if "EMA_SHORT" in param_history and len(param_history["EMA_SHORT"]) > 5:
                optimal_ema_s = int(np.median(param_history["EMA_SHORT"]))
                self.optimized_params["EMA_SHORT"] = self._apply_learning_rate("EMA_SHORT", optimal_ema_s, is_int=True)
                logger.info(f"   📊 EMA_SHORT: {self.optimized_params['EMA_SHORT']}")
            
            # بهینه‌سازی EMA_MED
            if "EMA_MED" in param_history and len(param_history["EMA_MED"]) > 5:
                optimal_ema_m = int(np.median(param_history["EMA_MED"]))
                self.optimized_params["EMA_MED"] = self._apply_learning_rate("EMA_MED", optimal_ema_m, is_int=True)
                logger.info(f"   📊 EMA_MED: {self.optimized_params['EMA_MED']}")
            
            # بهینه‌سازی ریسک
            self._optimize_risk_parameters()
            
            self.last_update_time = current_hour
            self._save_params()
            
            # ذخیره تاریخچه
            self.performance_history.append({
                "timestamp": current_hour,
                "params": self.optimized_params.copy(),
                "winrate": self.memory.get_winrate(20),
            })
            
            if len(self.performance_history) > 50:
                self.performance_history = self.performance_history[-50:]
            
            return self.optimized_params
            
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی: {e}")
            return self.optimized_params

    def _apply_learning_rate(self, param_name: str, target_value, is_int: bool = False):
        """اعمال نرخ یادگیری تطبیقی با مومنتوم"""
        try:
            current = self.optimized_params.get(param_name)
            if current is None:
                return target_value
            
            change = target_value - current
            
            if param_name in self.previous_updates:
                change = change * (1 - self.momentum) + self.previous_updates[param_name] * self.momentum
            
            self.previous_updates[param_name] = change
            new_value = current + change * self.learning_rate
            
            if param_name in self.param_constraints:
                min_val, max_val = self.param_constraints[param_name]
                new_value = max(min_val, min(max_val, new_value))
            
            return int(new_value) if is_int else new_value
        except Exception as e:
            logger.error(f"خطا در اعمال نرخ یادگیری: {e}")
            return target_value

    def _optimize_risk_parameters(self) -> None:
        """بهینه‌سازی پارامترهای ریسک"""
        try:
            winrate = self.memory.get_winrate(20)
            profit_factor = self.memory.get_profit_factor(20)
            sharpe = self.memory.get_sharpe_ratio(20)
            
            confidence_score = min(1.0, max(0.0, (winrate - 40) / 40))
            
            if winrate > 60 and profit_factor > 1.5 and sharpe > 1.0:
                multiplier = min(1.5, 1.0 + (winrate - 60) / 100 + (profit_factor - 1.5) / 5)
            elif winrate < 40 or profit_factor < 0.8:
                multiplier = max(0.3, 0.7 * confidence_score)
            else:
                multiplier = 1.0
            
            short_term_winrate = self.memory.get_short_term_winrate()
            if short_term_winrate < 40:
                multiplier *= 0.7
            elif short_term_winrate > 70:
                multiplier *= 1.2
            
            multiplier = max(0.3, min(2.0, multiplier))
            self.optimized_params["RISK_MULTIPLIER"] = multiplier
            
            base_risk = CONFIG.get("RISK_PERCENT", 1.0)
            new_risk = base_risk * multiplier
            new_risk = max(CONFIG.get("MIN_RISK_PERCENT", 0.5), min(CONFIG.get("MAX_RISK_PERCENT", 2.0), new_risk))
            self.optimized_params["RISK_PERCENT"] = new_risk
            
            logger.info(f"   📊 ریسک جدید: {new_risk:.2f}% (ضریب: {multiplier:.2f})")
            logger.info(f"      (Winrate: {winrate:.1f}% | PF: {profit_factor:.2f} | Sharpe: {sharpe:.2f})")
            
        except Exception as e:
            logger.error(f"خطا در بهینه‌سازی ریسک: {e}")

    def apply_optimized_params(self) -> None:
        """اعمال پارامترهای بهینه شده به CONFIG (با قفل، تا با خواندن هم‌زمان در حلقه اصلی تداخل نکند)"""
        try:
            if not self.optimized_params:
                return
            
            with CONFIG_LOCK:
                if "ATR_MULT_SL" in self.optimized_params:
                    CONFIG["ATR_MULT_SL"] = self.optimized_params["ATR_MULT_SL"]
                
                if "EMA_SHORT" in self.optimized_params:
                    CONFIG["EMA_SHORT"] = self.optimized_params["EMA_SHORT"]
                
                if "EMA_MED" in self.optimized_params:
                    CONFIG["EMA_MED"] = self.optimized_params["EMA_MED"]
                
                if "RISK_PERCENT" in self.optimized_params:
                    CONFIG["RISK_PERCENT"] = self.optimized_params["RISK_PERCENT"]
            
            logger.info("✅ پارامترهای بهینه شده اعمال شدند:")
            logger.info(f"   ATR_MULT_SL: {CONFIG['ATR_MULT_SL']:.2f}")
            logger.info(f"   EMA_SHORT: {CONFIG['EMA_SHORT']}")
            logger.info(f"   EMA_MED: {CONFIG['EMA_MED']}")
            logger.info(f"   RISK_PERCENT: {CONFIG['RISK_PERCENT']:.2f}%")
            
        except Exception as e:
            logger.error(f"خطا در اعمال پارامترهای بهینه شده: {e}")

    def optimize_regime_thresholds(self) -> None:
        """خودکار تنظیم می‌کند که هر رژیم بازار (VOLATILE/TRENDING/UNKNOWN) چقدر آستانه‌ی اطمینان
        اضافه نیاز دارد - بر اساس اینکه وین‌ریت واقعی آن رژیم چقدر از میانگین کل عقب‌تر است.
        این جایگزین دستی‌کاری REGIME_CONFIDENCE_ADJUSTMENT است که قبلاً با دست انجام می‌شد.

        دو لایه‌ی محافظتی دارد (درسی که از اشتباه قبلی گرفته شد - نتیجه‌گیری با نمونه‌ی 7 تایی):
        1. حداقل نمونه‌ی نسبتاً بزرگ برای هر رژیم (REGIME_MIN_TRADES_FOR_ADJUST) قبل از هر تغییری
        2. تغییر تدریجی و پله‌ای (REGIME_ADJUSTMENT_STEP) به‌جای پرش مستقیم به مقدار هدف،
           تا حتی اگر یک محاسبه‌ی لحظه‌ای پرت باشد، اثرش روی کل سیستم فقط تدریجی ظاهر شود"""
        try:
            min_samples = CONFIG.get("REGIME_MIN_TRADES_FOR_ADJUST", 25)
            max_adjustment = CONFIG.get("REGIME_MAX_ADJUSTMENT", 2.5)
            step = CONFIG.get("REGIME_ADJUSTMENT_STEP", 0.3)
            sensitivity = CONFIG.get("REGIME_ADJUSTMENT_SENSITIVITY", 0.15)
            
            regime_perf = self.memory.get_market_regime_performance()
            overall_winrate = self.memory.get_winrate()
            if not overall_winrate:
                return
            
            current_adj = CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}).copy()
            changed = False
            
            for regime, stats in regime_perf.items():
                if regime in ("RANGING",):
                    continue  # RANGING از قبل و به‌طور کامل در enhanced_analysis حذف می‌شود
                total = stats.get("total", 0)
                if total < min_samples:
                    continue
                
                regime_wr = stats.get("winrate", 0.0)
                gap = overall_winrate - regime_wr  # مثبت یعنی این رژیم بدتر از میانگین کل است
                target_adj = max(0.0, min(max_adjustment, gap * sensitivity))
                current = current_adj.get(regime, 0.0)
                
                if abs(target_adj - current) < 0.05:
                    continue
                
                new_adj = current + step if target_adj > current else current - step
                new_adj = max(0.0, min(max_adjustment, new_adj))
                # اگر فاصله تا هدف از step کمتر بود، مستقیم به هدف برس (نه رد شدن از آن)
                if abs(target_adj - current) < step:
                    new_adj = target_adj
                
                current_adj[regime] = round(new_adj, 2)
                changed = True
                logger.info(
                    f"🎯 آستانه‌ی رژیم {regime} خودکار به‌روزرسانی شد: {current:.2f} → {new_adj:.2f} "
                    f"(وین‌ریت رژیم: {regime_wr:.0f}% | میانگین کل: {overall_winrate:.0f}% | نمونه: {total})"
                )
            
            if changed:
                with CONFIG_LOCK:
                    CONFIG["REGIME_CONFIDENCE_ADJUSTMENT"] = current_adj
                    
        except Exception as e:
            logger.error(f"خطا در تنظیم خودکار آستانه‌ی رژیم: {e}")


# ============================================================================
# بخش 7: کلاس یادگیری وزن ویژگی (FeatureWeightLearner) - کامل
# ============================================================================

class FeatureWeightLearner:
    """یادگیری وزن ویژگی‌ها بر اساس موفقیت آن‌ها"""
    
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.feature_weights: dict = {
            "trend_alignment": 1.0,
            "volume_confirmation": 1.0,
            "multi_tf_alignment": 1.0,
            "price_action_quality": 1.0,
            "backtest_winrate": 1.0,
            "rsi_momentum": 1.0,
            "volatility_regime": 1.0,
            "adx_strength": 1.0,
            "cci_signal": 1.0,
            "williams_signal": 1.0,
            "mfi_signal": 1.0,
            "supertrend_alignment": 1.0,
        }
        self.short_term_weights: dict = self.feature_weights.copy()
        self.weights_history: list = []
        self.learning_rate: float = 0.05
        self.momentum: float = 0.50
        self.weight_changes: dict = {}
        self.correlation_threshold_positive: float = 0.15
        self.correlation_threshold_negative: float = -0.08
        self._load_weights()
        logger.debug("FeatureWeightLearner راه‌اندازی شد")

    def _load_weights(self):
        try:
            if os.path.exists(PATHS["FEATURE_WEIGHTS_FILE"]):
                with open(PATHS["FEATURE_WEIGHTS_FILE"], "r") as f:
                    saved = json.load(f)
                # فایل‌های قدیمی وزن‌های بسیار تهاجمی داشتند؛ برای نسخه جدید عمداً reset می‌شوند.
                if isinstance(saved, dict) and saved.get("version") == 2 and isinstance(saved.get("weights"), dict):
                    for key, value in saved["weights"].items():
                        if key in self.feature_weights and isinstance(value, (int, float)):
                            self.feature_weights[key] = max(0.50, min(1.50, float(value)))
                    logger.debug(f"وزن‌های ویژگی نسخه 2 بارگذاری شد: {self.feature_weights}")
                else:
                    logger.info("🧠 وزن‌های قدیمی شناسایی شد؛ وزن‌ها برای جلوگیری از انتقال نویز روی 1.0 reset شدند")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری وزن ویژگی‌ها: {e}")

    def _save_weights(self):
        try:
            _atomic_write_json(PATHS["FEATURE_WEIGHTS_FILE"], {"version": 2, "weights": self.feature_weights})
            self.weights_history.append({
                "timestamp": time.time(),
                "weights": self.feature_weights.copy()
            })
            if len(self.weights_history) > 100:
                self.weights_history = self.weights_history[-100:]
        except Exception as e:
            logger.error(f"خطا در ذخیره وزن ویژگی‌ها: {e}")

    def update_weights(self) -> None:
        """به‌روزرسانی وزن ویژگی‌ها بر اساس همبستگی با موفقیت"""
        try:
            if len(self.memory.trades) < CONFIG.get("MIN_TRADES_FOR_CORRELATION", 15):
                logger.debug("داده کافی برای به‌روزرسانی وزن ویژگی‌ها وجود ندارد")
                return
            
            logger.info("🎓 شروع به‌روزرسانی وزن ویژگی‌ها...")
            old_weights = self.feature_weights.copy()
            window = CONFIG.get("LEARNING_WINDOW", 100)
            
            for feature_name in list(self.feature_weights.keys()):
                correlation = self.memory.get_feature_correlation(feature_name, window=window)
                current = self.feature_weights[feature_name]

                # تغییر وزن فقط از همبستگی پنجره اخیر و با سقف 5% در هر دور.
                # momentum قبلی باعث می‌شد تغییرات انباشته شوند و وزن‌ها به 2.5/0.2 پرتاب شوند.
                if correlation > self.correlation_threshold_positive:
                    raw_delta = self.learning_rate * correlation
                elif correlation < self.correlation_threshold_negative:
                    raw_delta = self.learning_rate * correlation
                else:
                    raw_delta = 0.0

                max_step = 0.05 * max(0.5, current)
                raw_delta = max(-max_step, min(max_step, raw_delta))
                new_weight = current + raw_delta
                new_weight = max(0.50, min(1.50, new_weight))

                # EMA بسیار آرام؛ بدون افزودن دوباره delta قبلی
                new_weight = current * (1.0 - self.momentum) + new_weight * self.momentum
                change = new_weight - current
                self.weight_changes[feature_name] = change
                self.feature_weights[feature_name] = new_weight
                
                status = "📈" if new_weight > old_weights[feature_name] else "📉" if new_weight < old_weights[feature_name] else "➖"
                logger.info(f"   {status} {feature_name}: {old_weights[feature_name]:.2f} → {new_weight:.2f} (corr: {correlation:.2f})")
            
            self._save_weights()
            
            total_change = 0
            for key in self.feature_weights:
                if key in old_weights:
                    change = abs(self.feature_weights[key] - old_weights[key]) / max(0.1, old_weights[key])
                    total_change += change
            improvement = (total_change / len(self.feature_weights)) * 100
            
            logger.info(f"✅ وزن ویژگی‌ها به‌روزرسانی شد. میزان تغییر کلی: {improvement:.2f}%")
            
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی وزن ویژگی‌ها: {e}")

    def _get_current_sharpen_exponent(self) -> float:
        """تشدید وزن‌ها فقط به‌مرور و متناسب با تعداد معاملات فعال می‌شود - با نمونه‌ی کم (زیر
        WEIGHT_SHARPEN_MIN_TRADES)، خود وزن‌ها هنوز نویزی‌اند و تشدیدشان نویز را تقویت می‌کند نه سیگنال واقعی.
        این تابع به‌جای یک توان ثابت، بر اساس بلوغ داده، به‌آرامی از 1.0 (بدون تشدید) به سمت حداکثر می‌رود."""
        n = len(self.memory.trades)
        min_t = CONFIG.get("WEIGHT_SHARPEN_MIN_TRADES", 100)
        full_t = CONFIG.get("WEIGHT_SHARPEN_FULL_TRADES", 300)
        max_exp = min(CONFIG.get("WEIGHT_SHARPEN_EXPONENT_MAX", 2.0), 1.35)
        if n < min_t:
            return 1.0
        if n >= full_t:
            return max_exp
        progress = (n - min_t) / max(1, (full_t - min_t))
        return 1.0 + progress * (max_exp - 1.0)

    def calculate_weighted_confidence(self, signal_features: dict) -> float:
        """محاسبه امتیاز اطمینان با وزن‌دهی یادگیری شده - وزن‌ها متناسب با بلوغ داده (تعداد معاملات)
        تشدید می‌شوند، نه با یک توان ثابت: با نمونه‌ی کم اصلاً تشدید نمی‌شود (خطر تقویت نویز)،
        و هرچه داده بیشتر جمع شود، فاصله‌ی بین فیچرهای قوی/ضعیف بیشتر در امتیاز نهایی احساس می‌شود"""
        try:
            total_score = 0.0
            total_weight = 0.0
            sharpen_exp = self._get_current_sharpen_exponent()
            
            for feature_name, weight in self.feature_weights.items():
                feature_value = float(signal_features.get(feature_name, 0.0))
                effective_weight = weight ** sharpen_exp
                
                if weight > 1.5:
                    feature_value = min(1.0, feature_value * 1.1)
                elif weight < 0.5:
                    feature_value = max(0.0, feature_value * 0.9)
                
                total_score += feature_value * effective_weight
                total_weight += effective_weight
            
            if total_weight == 0:
                return 0.0
            
            return (total_score / total_weight) * 10.0
            
        except Exception as e:
            logger.error(f"خطا در محاسبه اطمینان وزنی: {e}")
            return 5.0


# ============================================================================
# بخش 7.5: مدل یادگیری ماشین واقعی (اختیاری - فقط با scikit-learn)
# ============================================================================

class MLConfidenceModel:
    """ML AutoPilot v3 for noisy, small tabular trading data.

    Design goals:
      - XGBoost-first model zoo, but never blindly trust one algorithm.
      - Expanding walk-forward evaluation with a purge gap to reduce horizon leakage.
      - Brier + AUC + stability determine the winner.
      - Missing feature values are imputed instead of throwing away otherwise useful trades.
      - Bad retrains are rejected; the previous good model remains live.
      - Corrupt model files are quarantined and rebuilt automatically.
      - ML remains a meta-filter: it can influence the score only after out-of-sample
        evidence shows it is better than chance and sufficiently stable.
    """

    FEATURE_NAMES = [
        "trend_alignment", "volume_confirmation", "multi_tf_alignment",
        "price_action_quality", "backtest_winrate", "rsi_momentum",
        "volatility_regime", "adx_strength", "cci_signal", "williams_signal",
        "mfi_signal", "supertrend_alignment",
    ]
    MODEL_VERSION = 3

    def __init__(self, memory: "PerformanceMemory"):
        self.memory = memory
        self.model = None
        self.is_trained = False
        self.trained_on_n_trades = 0
        self.last_test_auc = None
        self.last_test_accuracy = None
        self.last_brier = None
        self.wf_auc_mean = None
        self.wf_auc_std = None
        self.wf_folds = 0
        self.selected_model_name = None
        self.last_train_time = 0.0
        self.model_version = self.MODEL_VERSION
        self.dataset_n = 0
        self.class_balance = None
        self.health = "INIT"
        if SKLEARN_AVAILABLE:
            self._load_model()

    def _backup_model_file(self):
        try:
            p = PATHS["ML_MODEL_FILE"]
            if os.path.exists(p):
                shutil.copy2(p, p + ".bak")
        except Exception as e:
            logger.debug(f"ML backup failed: {e}")

    def _quarantine_corrupt_model(self):
        try:
            p = PATHS["ML_MODEL_FILE"]
            if os.path.exists(p):
                bad = p + f".bad.{int(time.time())}"
                os.replace(p, bad)
                logger.warning(f"🤖 ML model quarantined: {bad}")
        except Exception as e:
            logger.debug(f"ML quarantine failed: {e}")

    def _load_model(self):
        try:
            p = PATHS["ML_MODEL_FILE"]
            if not os.path.exists(p):
                return
            saved = joblib.load(p)
            if saved.get("model_version") != self.MODEL_VERSION:
                logger.info("🤖 ML model version changed; rebuilding automatically")
                return
            model = saved.get("model")
            if model is None:
                return
            self.model = model
            self.trained_on_n_trades = int(saved.get("trained_on_n_trades", 0))
            self.dataset_n = int(saved.get("dataset_n", self.trained_on_n_trades))
            self.last_test_auc = saved.get("last_test_auc")
            self.last_test_accuracy = saved.get("last_test_accuracy")
            self.last_brier = saved.get("last_brier")
            self.wf_auc_mean = saved.get("wf_auc_mean")
            self.wf_auc_std = saved.get("wf_auc_std")
            self.wf_folds = int(saved.get("wf_folds", 0))
            self.selected_model_name = saved.get("selected_model_name")
            self.class_balance = saved.get("class_balance")
            self.health = saved.get("health", "LOADED")
            self.is_trained = True
            logger.info(f"🤖 ML AutoPilot v3 loaded | {self.selected_model_name} | WF AUC={self.wf_auc_mean}")
        except Exception as e:
            logger.warning(f"🤖 ML model load failed; auto-recovering: {e}")
            self._quarantine_corrupt_model()
            self.model = None
            self.is_trained = False

    def _save_model(self):
        if self.model is None:
            return
        try:
            self._backup_model_file()
            payload = {
                "model_version": self.MODEL_VERSION,
                "model": self.model,
                "trained_on_n_trades": self.trained_on_n_trades,
                "dataset_n": self.dataset_n,
                "last_test_auc": self.last_test_auc,
                "last_test_accuracy": self.last_test_accuracy,
                "last_brier": self.last_brier,
                "wf_auc_mean": self.wf_auc_mean,
                "wf_auc_std": self.wf_auc_std,
                "wf_folds": self.wf_folds,
                "selected_model_name": self.selected_model_name,
                "class_balance": self.class_balance,
                "health": self.health,
            }
            tmp = PATHS["ML_MODEL_FILE"] + ".tmp"
            joblib.dump(payload, tmp, compress=3)
            os.replace(tmp, PATHS["ML_MODEL_FILE"])
        except Exception as e:
            logger.error(f"🤖 ML save failed; live model kept: {e}")
            try:
                if os.path.exists(PATHS["ML_MODEL_FILE"] + ".tmp"):
                    os.remove(PATHS["ML_MODEL_FILE"] + ".tmp")
            except Exception:
                pass

    def _build_dataset(self):
        X, y = [], []
        for trade in self.memory.trades:
            label = trade.get("outcome_label")
            if label not in ("TP1", "TP2", "TP3", "SL"):
                continue
            feats = trade.get("features") or {}
            row = []
            for name in self.FEATURE_NAMES:
                v = feats.get(name, np.nan)
                try:
                    v = float(v)
                    if not np.isfinite(v):
                        v = np.nan
                except Exception:
                    v = np.nan
                row.append(v)
            X.append(row)
            y.append(1 if str(label).startswith("TP") else 0)
        if not X:
            return np.empty((0, len(self.FEATURE_NAMES)), dtype=float), np.empty(0, dtype=int)
        return np.asarray(X, dtype=float), np.asarray(y, dtype=int)

    def should_retrain(self) -> bool:
        if not SKLEARN_AVAILABLE:
            return False
        X, y = self._build_dataset()
        n = len(y)
        min_n = CONFIG.get("ML_MIN_TRADES_TO_TRAIN", 60)
        if n < min_n or len(np.unique(y)) < 2:
            return False
        if not self.is_trained:
            return True
        return (n - self.trained_on_n_trades) >= CONFIG.get("ML_RETRAIN_INTERVAL", 25)

    @staticmethod
    def _make_models():
        models = {
            "logistic": Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(C=0.35, max_iter=1500, class_weight="balanced", random_state=42)),
            ]),
            "hist_gradient": Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", HistGradientBoostingClassifier(
                    max_iter=160, max_leaf_nodes=7, learning_rate=0.035,
                    l2_regularization=2.0, min_samples_leaf=12,
                    early_stopping=True, random_state=42
                )),
            ]),
            "extra_trees": Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", ExtraTreesClassifier(
                    n_estimators=300, max_depth=5, min_samples_leaf=5,
                    max_features=0.75, class_weight="balanced", random_state=42, n_jobs=1
                )),
            ]),
        }
        if XGBOOST_AVAILABLE:
            models["xgboost"] = Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", XGBClassifier(
                    n_estimators=220,
                    max_depth=3,
                    learning_rate=0.035,
                    min_child_weight=5,
                    subsample=0.82,
                    colsample_bytree=0.80,
                    reg_alpha=0.25,
                    reg_lambda=4.0,
                    gamma=0.05,
                    objective="binary:logistic",
                    eval_metric="logloss",
                    tree_method="hist",
                    n_jobs=1,
                    random_state=42,
                )),
            ])
        if CATBOOST_AVAILABLE:
            models["catboost"] = Pipeline([
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("model", CatBoostClassifier(iterations=300, depth=5, learning_rate=0.03,
                    loss_function="Logloss", eval_metric="AUC", verbose=False, random_seed=42,
                    l2_leaf_reg=5.0, thread_count=1)),
            ])
        return models

    @staticmethod
    def _fit_calibrated(base, X, y):
        # For tiny datasets, a plain model is safer than an unstable calibration split.
        n = len(y)
        if n < 90:
            base.fit(X, y)
            return base
        splits = min(3, max(2, n // 40))
        return CalibratedClassifierCV(base, method="sigmoid", cv=TimeSeriesSplit(n_splits=splits)).fit(X, y)

    def _walk_forward(self, X, y):
        min_train = CONFIG.get("ML_MIN_TRAIN_SAMPLES", 60)
        block = CONFIG.get("ML_TEST_BLOCK", 20)
        gap = CONFIG.get("ML_WF_GAP", 8)
        results = {name: {"auc": [], "brier": [], "accuracy": []} for name in self._make_models()}
        n = len(y)
        if n < min_train + block * 3 + gap:
            return results
        for train_end in range(min_train, n - block + 1, block):
            test_start = train_end + gap
            test_end = min(test_start + block, n)
            if test_end > n or test_start >= n:
                continue
            Xtr, ytr = X[:train_end], y[:train_end]
            Xte, yte = X[test_start:test_end], y[test_start:test_end]
            if len(np.unique(ytr)) < 2 or len(np.unique(yte)) < 2:
                continue
            for name, base in self._make_models().items():
                try:
                    fitted = self._fit_calibrated(base, Xtr, ytr)
                    proba = fitted.predict_proba(Xte)[:, 1]
                    pred = (proba >= 0.5).astype(int)
                    results[name]["auc"].append(float(roc_auc_score(yte, proba)))
                    results[name]["brier"].append(float(brier_score_loss(yte, proba)))
                    results[name]["accuracy"].append(float(accuracy_score(yte, pred)))
                except Exception as e:
                    logger.debug(f"ML WF {name} failed: {e}")
        return results

    @staticmethod
    def _score_candidate(auc_mean, auc_std, brier_mean):
        # AUC is primary; stability and probability calibration matter too.
        return float(auc_mean - 0.55 * auc_std - 0.30 * max(0.0, brier_mean - 0.20))

    def train(self, force: bool = False) -> Optional[dict]:
        if not SKLEARN_AVAILABLE:
            self.health = "NO_SKLEARN"
            return None
        if not force and not self.should_retrain():
            return None
        try:
            X, y = self._build_dataset()
            n = len(y)
            min_n = CONFIG.get("ML_MIN_TRADES_TO_TRAIN", 60)
            if n < min_n or len(np.unique(y)) < 2:
                self.health = "WAITING_FOR_VALID_DATA"
                logger.info(f"🤖 ML: valid samples {n}/{min_n}")
                return None

            wf = self._walk_forward(X, y)
            candidates = []
            for name, m in wf.items():
                if len(m["auc"]) >= CONFIG.get("ML_MIN_WF_FOLDS", 3):
                    auc_mean = float(np.mean(m["auc"]))
                    auc_std = float(np.std(m["auc"]))
                    brier = float(np.mean(m["brier"]))
                    acc = float(np.mean(m["accuracy"]))
                    score = self._score_candidate(auc_mean, auc_std, brier)
                    candidates.append((score, name, auc_mean, auc_std, brier, acc, len(m["auc"])))
            if not candidates:
                self.health = "NO_VALID_WF"
                logger.warning("🤖 ML: no valid walk-forward candidate; previous model remains live")
                return None

            candidates.sort(key=lambda z: (-z[0], -z[2], z[3], z[4]))
            _, best_name, wf_auc, wf_std, wf_brier, wf_acc, folds = candidates[0]

            # Holdout is the newest block and is never used for fitting the reported test score.
            block = CONFIG.get("ML_TEST_BLOCK", 20)
            gap = CONFIG.get("ML_WF_GAP", 8)
            test_start = max(CONFIG.get("ML_MIN_TRAIN_SAMPLES", 60), n - block)
            train_end = max(CONFIG.get("ML_MIN_TRAIN_SAMPLES", 60), test_start - gap)
            if train_end >= n:
                train_end = max(CONFIG.get("ML_MIN_TRAIN_SAMPLES", 60), n - block)
            base = self._make_models()[best_name]
            test_model = self._fit_calibrated(base, X[:train_end], y[:train_end])
            X_test, y_test = X[test_start:], y[test_start:]
            if len(X_test) > 0 and len(np.unique(y_test)) > 1:
                test_proba = test_model.predict_proba(X_test)[:, 1]
                test_pred = (test_proba >= 0.5).astype(int)
                last_auc = float(roc_auc_score(y_test, test_proba))
                last_acc = float(accuracy_score(y_test, test_pred))
                last_brier = float(brier_score_loss(y_test, test_proba))
            else:
                last_auc = None
                last_acc = None
                last_brier = None

            # Train operational model on all data only after the candidate has passed WF.
            operational = self._fit_calibrated(self._make_models()[best_name], X, y)

            # Sanity-check operational model before replacing the live model.
            probe = operational.predict_proba(X[-min(5, n):])[:, 1]
            if not np.all(np.isfinite(probe)):
                raise ValueError("operational model produced non-finite probabilities")

            self.model = operational
            self.is_trained = True
            self.trained_on_n_trades = n
            self.dataset_n = n
            self.last_test_auc = round(last_auc, 3) if last_auc is not None else None
            self.last_test_accuracy = round(last_acc, 3) if last_acc is not None else None
            self.last_brier = round(last_brier, 4) if last_brier is not None else round(wf_brier, 4)
            self.wf_auc_mean = round(wf_auc, 3)
            self.wf_auc_std = round(wf_std, 3)
            self.wf_folds = folds
            self.selected_model_name = best_name
            self.class_balance = {"wins": int(np.sum(y == 1)), "losses": int(np.sum(y == 0))}
            self.last_train_time = time.time()

            active_std = min(0.10, float(CONFIG.get("ML_MAX_WF_AUC_STD", 0.20)))
            stable = (wf_auc >= CONFIG.get("ML_MIN_WF_AUC", 0.56) and
                      wf_std <= active_std and
                      (last_brier is None or last_brier <= CONFIG.get("ML_REQUIRE_BRIER_MAX", 0.29)))
            self.health = "ACTIVE" if stable else ("PROVISIONAL" if CONFIG.get("ML_ALLOW_PROVISIONAL_MODEL", True) else "OBSERVE_ONLY")
            self._save_model()

            logger.info(
                f"🤖 ML AutoPilot v3: {n} samples | {best_name} | "
                f"WF AUC={wf_auc:.3f}±{wf_std:.3f} | folds={folds} | Brier={wf_brier:.4f} | health={self.health}"
            )
            return {
                "n_trades": n,
                "test_accuracy": self.last_test_accuracy,
                "test_auc": self.last_test_auc,
                "wf_auc": self.wf_auc_mean,
                "wf_auc_std": self.wf_auc_std,
                "wf_folds": folds,
                "brier": self.last_brier,
                "model": best_name,
                "health": self.health,
            }
        except Exception as e:
            logger.exception(f"🤖 ML AutoPilot training failed; keeping previous model: {e}")
            self.health = "ERROR_ROLLBACK"
            return None

    def predict_win_probability(self, features: dict) -> Optional[float]:
        if not self.is_trained or self.model is None:
            return None
        try:
            row = []
            for name in self.FEATURE_NAMES:
                v = features.get(name, np.nan)
                try:
                    v = float(v)
                    if not np.isfinite(v):
                        v = np.nan
                except Exception:
                    v = np.nan
                row.append(v)
            p = float(self.model.predict_proba([row])[0][1])
            return p if np.isfinite(p) else None
        except Exception as e:
            logger.debug(f"ML prediction failed: {e}")
            return None

    def get_influence_weight(self) -> float:
        """Graded ML influence: never lets one noisy WF fold disable a useful model.

        ACTIVE models get the normal ramp. PROVISIONAL models get a small capped
        influence when their walk-forward evidence is directionally useful. If the
        model becomes genuinely weak, influence falls back to zero automatically.
        """
        if not self.is_trained or self.wf_auc_mean is None:
            return 0.0

        min_auc = float(CONFIG.get("ML_MIN_AUC_FOR_INFLUENCE", 0.56))
        full_auc = float(CONFIG.get("ML_FULL_AUC_FOR_INFLUENCE", 0.66))
        wf_auc = float(self.wf_auc_mean)
        wf_std = float(self.wf_auc_std or 0.0)
        folds = int(self.wf_folds or 0)
        brier = float(self.last_brier) if self.last_brier is not None else 0.30

        if folds < int(CONFIG.get("ML_MIN_WF_FOLDS", 3)):
            return 0.0
        if wf_auc < min_auc:
            return 0.0
        if brier > float(CONFIG.get("ML_REQUIRE_BRIER_MAX", 0.29)):
            return 0.0

        # A very unstable model is not trusted, but moderate instability only
        # reduces its weight instead of hard-disabling it.
        std_cap = float(CONFIG.get("ML_MAX_WF_AUC_STD", 0.20))
        stability = max(0.0, min(1.0, 1.0 - (wf_std / max(std_cap, 1e-6))))

        quality = max(0.0, min(1.0, (wf_auc - min_auc) / max(0.01, full_auc - min_auc)))
        maturity = min(1.0, float(self.trained_on_n_trades) / max(1, int(CONFIG.get("ML_FULL_MATURITY_TRADES", 400))))

        # Latest unseen test is a warning signal, not a single-point kill switch.
        holdout_factor = 1.0
        if self.last_test_auc is not None:
            if self.last_test_auc < 0.50:
                holdout_factor = 0.35
            elif self.last_test_auc < min_auc:
                holdout_factor = 0.65

        if self.health == "PROVISIONAL":
            base = float(CONFIG.get("ML_PROVISIONAL_INFLUENCE", 0.05))
            return min(float(CONFIG.get("ML_MAX_INFLUENCE", 0.15)), base * max(0.35, quality) * max(0.40, stability) * holdout_factor)

        return min(float(CONFIG.get("ML_MAX_INFLUENCE", 0.15)),
                   maturity * quality * max(0.40, stability) * holdout_factor * float(CONFIG.get("ML_MAX_INFLUENCE", 0.15)))

class SelfHealingAutoPilot:
    """لایه‌ی مستقل ایمنی: تشخیص افت اخیر، تکرار نماد، جهت غالب، رژیم ضعیف و rollback.
    هیچ تنظیمی را بدون snapshot و sanity-check تغییر نمی‌دهد."""
    def __init__(self, memory):
        self.memory = memory
        self.last_run = 0.0
        self.state = self._load()
        self.lock = threading.Lock()
        os.makedirs(PATHS["CONFIG_BACKUP_DIR"], exist_ok=True)

    def _load(self):
        try:
            with open(PATHS["AUTOPILOT_STATE"], "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {"last_good": {}, "last_good_wr": None, "last_good_pf": None}

    def _save(self): _atomic_write_json(PATHS["AUTOPILOT_STATE"], self.state)

    def snapshot(self, tag="auto"):
        try:
            ts=int(time.time()); path=os.path.join(PATHS["CONFIG_BACKUP_DIR"], f"{tag}_{ts}.json")
            _atomic_write_json(path, {"config": dict(CONFIG), "state": self.state, "time": ts})
            return path
        except Exception: return None

    def metrics(self, trades=None):
        tr=list(trades if trades is not None else self.memory.trades)
        if not tr: return {"wr":0,"pf":1,"n":0}
        wr=sum(bool(t.get("win")) for t in tr)/len(tr)
        gp=sum(max(0,float(t.get("return_pct",0))) for t in tr)
        gl=abs(sum(min(0,float(t.get("return_pct",0))) for t in tr))
        return {"wr":wr,"pf":gp/gl if gl else 99.0,"n":len(tr)}

    def regime_adjust(self):
        regimes={}
        for t in list(self.memory.trades)[-CONFIG["REGIME_WINDOW"]:]:
            r=t.get("features",{}).get("market_regime","UNKNOWN"); regimes.setdefault(r,[]).append(t)
        changed=False; adj=CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT",{}).copy(); base=CONFIG["MIN_CONFIDENCE_SCORE"]
        for r, tr in regimes.items():
            if len(tr)<CONFIG["REGIME_MIN_TRADES_FOR_ADJUST"]: continue
            wr=sum(bool(t.get("win")) for t in tr)/len(tr)
            cur=float(adj.get(r,0))
            if wr < CONFIG["REGIME_BAD_WINRATE"]:
                cur=min(CONFIG["REGIME_MAX_ADJUSTMENT"], cur+CONFIG["REGIME_ADJUSTMENT_STEP"]); changed=True
            elif wr > CONFIG["REGIME_GOOD_WINRATE"]:
                cur=max(0.0, cur-CONFIG["REGIME_ADJUSTMENT_STEP"]); changed=True
            adj[r]=round(min(0.45, max(0.0, cur)),2)
        if changed: CONFIG["REGIME_CONFIDENCE_ADJUSTMENT"]=adj
        return changed

    def run(self, force=False):
        with self.lock:
            now=time.time()
            if not force and now-self.last_run<CONFIG["AUTO_HEAL_INTERVAL_SEC"]: return
            self.last_run=now
            tr=list(self.memory.trades); m=self.metrics(tr)
            if len(tr)<CONFIG["AUTO_HEAL_MIN_TRADES"]: return
            self.snapshot("before_autopilot")
            recent=tr[-CONFIG["RECENT_PERFORMANCE_WINDOW"]:]; rm=self.metrics(recent)
            # If the recent regime is healthy, keep a last-known-good snapshot.
            if rm["pf"] >= 1.02 and rm["wr"] >= 0.52:
                self.state["last_good"] = {
                    "MIN_CONFIDENCE_SCORE": CONFIG["MIN_CONFIDENCE_SCORE"],
                    "PUMP_THRESHOLD": CONFIG["PUMP_THRESHOLD"],
                    "DUMP_THRESHOLD": CONFIG["DUMP_THRESHOLD"],
                    "REGIME_CONFIDENCE_ADJUSTMENT": dict(CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {})),
                }
                self.state["last_good_wr"] = rm["wr"]; self.state["last_good_pf"] = rm["pf"]
            # adaptive safety: tighten when recent evidence materially deteriorates.
            if rm["pf"] < 0.90 or rm["wr"] < 0.45:
                last_wr=self.state.get("last_good_wr"); last_pf=self.state.get("last_good_pf")
                if last_wr is not None and last_pf is not None and (last_wr-rm["wr"]>=CONFIG["ROLLBACK_IF_WR_DROP"] or last_pf-rm["pf"]>=CONFIG["ROLLBACK_IF_PF_DROP"]):
                    good=self.state.get("last_good", {})
                    for k,v in good.items(): CONFIG[k]=v
                    logger.warning("🛡️ AutoPilot: افت شدید تشخیص داده شد؛ تنظیمات به آخرین وضعیت سالم rollback شد")
                else:
                    CONFIG["MIN_CONFIDENCE_SCORE"]=min(6.6, CONFIG["MIN_CONFIDENCE_SCORE"]+0.10)
                    CONFIG["PUMP_THRESHOLD"]=min(2.2, CONFIG["PUMP_THRESHOLD"]+0.1)
                    CONFIG["DUMP_THRESHOLD"]=-CONFIG["PUMP_THRESHOLD"]
            elif rm["pf"] > 1.08 and rm["wr"] > 0.54:
                CONFIG["MIN_CONFIDENCE_SCORE"]=max(6.0, CONFIG["MIN_CONFIDENCE_SCORE"]-0.10)
            self.regime_adjust()
            self.state["last_metrics"]=m; self.state["recent_metrics"]=rm
            self.state["config"]={k:CONFIG.get(k) for k in ("MIN_CONFIDENCE_SCORE","PUMP_THRESHOLD","DUMP_THRESHOLD","REGIME_CONFIDENCE_ADJUSTMENT")}
            self._save()

    def symbol_blocked(self, symbol, direction):
        now=time.time(); window=CONFIG["DEDUP_WINDOW_SEC"]
        recent=[t for t in list(self.memory.trades) if t.get("symbol")==symbol and t.get("direction")==direction and now-float(t.get("timestamp",0))<window]
        return len(recent)>=CONFIG["MAX_PENDING_PER_SYMBOL"]

    def consecutive_losses(self):
        n=0
        for t in reversed(list(self.memory.trades)):
            if t.get("win"): break
            n+=1
        return n

    def emergency_gate(self, symbol, direction):
        if self.consecutive_losses()>=CONFIG["MAX_CONSECUTIVE_LOSSES"]: return False, "consecutive_losses"
        if self.symbol_blocked(symbol,direction): return False, "symbol_cooldown"
        return True, "ok"

class PatternRecognizer:
    """تشخیص الگوهای تکراری موفق و ناموفق"""
    
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.successful_patterns: list = []
        self.failed_patterns: list = []
        self.pattern_weights: dict = {"successful": {}, "failed": {}}
        self.match_statistics: dict = {"total_matches": 0, "successful_matches": 0}
        self.similarity_threshold_success: float = 0.65
        self.similarity_threshold_fail: float = 0.55
        self.max_patterns: int = 50
        self._load_patterns()
        logger.debug("PatternRecognizer راه‌اندازی شد")

    def _load_patterns(self):
        try:
            if os.path.exists(PATHS["PATTERNS_FILE"]):
                with open(PATHS["PATTERNS_FILE"], "r") as f:
                    data = json.load(f)
                    self.successful_patterns = data.get("successful_patterns", [])
                    self.failed_patterns = data.get("failed_patterns", [])
                    self.pattern_weights = data.get("pattern_weights", {"successful": {}, "failed": {}})
                    self.match_statistics = data.get("match_statistics", {"total_matches": 0, "successful_matches": 0})
                logger.info(f"{len(self.successful_patterns)} الگوی موفق و {len(self.failed_patterns)} الگوی ناموفق بارگذاری شد")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری الگوها: {e}")

    def _save_patterns(self):
        try:
            data = {
                "successful_patterns": self.successful_patterns,
                "failed_patterns": self.failed_patterns,
                "pattern_weights": self.pattern_weights,
                "match_statistics": self.match_statistics,
                "timestamp": time.time()
            }
            _atomic_write_json(PATHS["PATTERNS_FILE"], data)
        except Exception as e:
            logger.error(f"خطا در ذخیره الگوها: {e}")

    def learn_patterns(self) -> None:
        """یادگیری الگوهای موفق و ناموفق - فقط از بازه‌ی اخیر (LEARNING_WINDOW)، نه کل تاریخچه.
        همچنین شمارنده‌های الگو هر بار از نو ساخته می‌شوند (نه تجمعی)، چون قبلاً هر بار که این تابع
        صدا زده می‌شد، معاملات قدیمی دوباره و دوباره به شمارنده اضافه می‌شدند و متورم می‌شدند."""
        try:
            if len(self.memory.trades) < 20:
                logger.debug("داده کافی برای یادگیری الگوها وجود ندارد")
                return
            
            logger.info("🔄 شروع یادگیری الگوهای موفق و ناموفق...")
            
            window = CONFIG.get("LEARNING_WINDOW", 100)
            recent_trades = list(self.memory.trades)[-window:]
            
            # بازسازی کامل شمارنده‌ها از صفر برای این بازه - نه افزودن روی مقادیر قبلی
            self.pattern_weights = {"successful": {}, "failed": {}}
            
            successful_patterns = []
            failed_patterns = []
            
            for trade in recent_trades:
                pattern = self._extract_pattern(trade)
                if trade.get("win", False):
                    successful_patterns.append(pattern)
                    self._update_pattern_weight(pattern, "successful")
                else:
                    failed_patterns.append(pattern)
                    self._update_pattern_weight(pattern, "failed")
            
            self.successful_patterns = successful_patterns[-self.max_patterns:]
            self.failed_patterns = failed_patterns[-self.max_patterns:]
            self._save_patterns()
            
            logger.info(f"✅ یادگیری الگوها کامل شد: {len(self.successful_patterns)} الگوی موفق, {len(self.failed_patterns)} الگوی ناموفق")
            
        except Exception as e:
            logger.error(f"خطا در یادگیری الگوها: {e}")

    def _extract_pattern(self, trade: dict) -> dict:
        """استخراج الگو از معامله"""
        features = trade.get("features", {})
        return {
            "trend": features.get("trend_type", ""),
            "volatility": features.get("volatility", 0.0),
            "volume_ratio": features.get("volume_ratio", 0.0),
            "rsi": features.get("rsi", 50.0),
            "pattern": features.get("price_action", ""),
            "market_regime": features.get("market_regime", "UNKNOWN"),
        }

    def _update_pattern_weight(self, pattern: dict, category: str) -> None:
        """به‌روزرسانی وزن الگوها"""
        key = f"{pattern['trend']}_{pattern.get('market_regime', 'UNKNOWN')}_{pattern.get('pattern', 'NONE')}"
        if key not in self.pattern_weights[category]:
            self.pattern_weights[category][key] = {"count": 0}
        self.pattern_weights[category][key]["count"] += 1

    def _calculate_similarity(self, pattern1: dict, pattern2: dict) -> float:
        """محاسبه شباهت بین دو الگو"""
        try:
            weights = {
                "trend": 0.25,
                "market_regime": 0.15,
                "pattern": 0.20,
                "volatility": 0.10,
                "volume_ratio": 0.10,
                "rsi": 0.20,
            }
            
            total_score = 0.0
            total_weight = 0.0
            
            for feature, weight in weights.items():
                total_weight += weight
                val1 = pattern1.get(feature)
                val2 = pattern2.get(feature)
                
                if feature in ("trend", "market_regime", "pattern"):
                    if val1 == val2:
                        total_score += weight
                else:
                    try:
                        num1 = float(val1) if val1 is not None else 0
                        num2 = float(val2) if val2 is not None else 0
                        if num1 == 0 and num2 == 0:
                            total_score += weight
                        elif max(abs(num1), abs(num2)) > 0:
                            diff_pct = abs(num1 - num2) / max(abs(num1), abs(num2), 0.001)
                            similarity = max(0, 1 - diff_pct)
                            total_score += similarity * weight
                    except Exception:
                        pass
            
            return total_score / total_weight if total_weight > 0 else 0.0
            
        except Exception as e:
            logger.error(f"خطا در محاسبه شباهت: {e}")
            return 0.0

    def matches_successful_pattern(self, current_features: dict) -> bool:
        """بررسی تطابق با الگوهای موفق گذشته"""
        try:
            current_pattern = {
                "trend": current_features.get("trend_type", ""),
                "volatility": current_features.get("volatility", 0.0),
                "volume_ratio": current_features.get("volume_ratio", 0.0),
                "rsi": current_features.get("rsi", 50.0),
                "pattern": current_features.get("price_action", ""),
                "market_regime": current_features.get("market_regime", "UNKNOWN"),
            }
            
            best_similarity = 0.0
            for pattern in self.successful_patterns:
                similarity = self._calculate_similarity(current_pattern, pattern)
                key = f"{pattern['trend']}_{pattern.get('market_regime', 'UNKNOWN')}_{pattern.get('pattern', 'NONE')}"
                weight_factor = min(1.5, 1 + (self.pattern_weights["successful"].get(key, {}).get("count", 0) / 20))
                adjusted_similarity = similarity * weight_factor
                if adjusted_similarity > best_similarity:
                    best_similarity = adjusted_similarity
            
            self.match_statistics["total_matches"] += 1
            is_match = best_similarity > self.similarity_threshold_success
            if is_match:
                self.match_statistics["successful_matches"] += 1
            
            return is_match
            
        except Exception as e:
            logger.error(f"خطا در بررسی الگوی موفق: {e}")
            return False

    def matches_failed_pattern(self, current_features: dict) -> bool:
        """بررسی تطابق با الگوهای ناموفق گذشته"""
        try:
            current_pattern = {
                "trend": current_features.get("trend_type", ""),
                "volatility": current_features.get("volatility", 0.0),
                "volume_ratio": current_features.get("volume_ratio", 0.0),
                "rsi": current_features.get("rsi", 50.0),
                "pattern": current_features.get("price_action", ""),
                "market_regime": current_features.get("market_regime", "UNKNOWN"),
            }
            
            for pattern in self.failed_patterns:
                similarity = self._calculate_similarity(current_pattern, pattern)
                if similarity > self.similarity_threshold_fail:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"خطا در بررسی الگوی ناموفق: {e}")
            return False
# ============================================================================
# بخش 9: خودآموزی خودکار (Auto-Learning System) - کامل
# ============================================================================

class AutoLearningSystem:
    """سیستم خودآموزی - از سیگنال‌هایی که می‌دهد یاد می‌گیرد"""
    
    def __init__(self, memory: PerformanceMemory):
        self.memory = memory
        self.learning_queue: deque = deque(maxlen=100)
        self.learning_thread: Optional[threading.Thread] = None
        self.running = False
        self._load_queue()
        logger.debug("AutoLearningSystem راه‌اندازی شد")

    def _load_queue(self):
        try:
            if os.path.exists(PATHS["AUTO_LEARN_QUEUE"]):
                with open(PATHS["AUTO_LEARN_QUEUE"], "r") as f:
                    data = json.load(f)
                    for item in data:
                        self.learning_queue.append(item)
                logger.info(f"{len(self.learning_queue)} سیگنال در صف یادگیری")
        except Exception as e:
            logger.warning(f"خطا در بارگذاری صف یادگیری: {e}")

    def _save_queue(self):
        _atomic_write_json(PATHS["AUTO_LEARN_QUEUE"], list(self.learning_queue))

    def add_signal_for_learning(self, signal: dict):
        """اضافه کردن سیگنال به صف یادگیری"""
        if not CONFIG.get("AUTO_LEARN_ENABLED", True):
            return
        
        try:
            symbol = signal.get("symbol")
            # جلوگیری از چند سیگنال هم‌پوشان برای یک نماد در بازه‌ی کوتاه (مثلاً دو چرخه‌ی پشت‌سرهم
            # هر دو روی همون پامپ/دامپ تریگر بشن) - این نمونه‌ها به‌شدت به هم وابسته‌اند و
            # وزن آماری کاذب به یک رویداد واحد می‌دن
            dedup_window = CONFIG.get("AUTO_LEARN_DEDUP_WINDOW_SEC", 600)
            now = time.time()
            for item in self.learning_queue:
                if item.get("symbol") == symbol and (now - item.get("timestamp", 0)) < dedup_window:
                    logger.debug(f"⏭️ {symbol} به‌تازگی در صف یادگیری هست، از تکرار صرف‌نظر شد")
                    return
            
            self.learning_queue.append({
                "signal": signal,
                "timestamp": now,
                "symbol": symbol,
                "direction": signal.get("direction"),
                "entry": signal.get("entry"),
                "confidence": signal.get("confidence", 0),
                "retry_count": 0,
            })
            self._save_queue()
            logger.info(f"📚 {symbol} به صف خودآموزی اضافه شد (صف: {len(self.learning_queue)})")
        except Exception as e:
            logger.error(f"خطا در افزودن سیگنال به صف: {e}")

    def _simulate_outcome(self, signal_data: dict):
        """شبیه‌سازی خودکار نتیجه معامله - با همان منطق برخورد SL/TP در طول مسیر که در بک‌تست استفاده می‌شود
        (نه فقط مقایسه قیمت لحظه‌ای)، تا تعریف برد/باخت با بک‌تست یکسان باشد.
        از signal_candle_ts (زمان دقیق کندل سیگنال) استفاده می‌کند تا دقیقاً همان کندل‌های
        *بعد از* لحظه‌ی صدور سیگنال را بررسی کند - نه یک بازه‌ی تقریبی بر اساس زمان پردازش صف که
        بسته به سرعت پردازش می‌توانست چند دقیقه جابه‌جا باشد.
        در صورت شکست، به‌جای None ساده، دیکشنری {"_unresolved": True, "reason": ...} برمی‌گرداند
        تا دلیل دقیق در لاگ/صف مشخص باشد و بشود بین «داده هنوز آماده نیست» و «خطای واقعی» فرق گذاشت."""
        try:
            signal = signal_data.get("signal", {})
            symbol = signal.get("symbol")
            direction = signal.get("direction")
            entry = signal.get("entry")
            sl = signal.get("sl")
            tps = signal.get("tps") or []
            
            if not symbol or not entry or sl is None or not tps:
                return {"_unresolved": True, "reason": "incomplete_signal", "symbol": symbol}
            
            hold_candles = get_max_hold_candles()
            minutes_per_candle = _interval_to_minutes(CONFIG.get("KLINE_INTERVAL", "1h")) or 60
            
            candle_ts = signal.get("signal_candle_ts")
            if candle_ts:
                # مسیر دقیق: فقط کندل‌های بعد از لحظه‌ی سیگنال را می‌بینیم
                signal_time = pd.to_datetime(float(candle_ts), unit="s")
                df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=hold_candles + 20, use_cache=False)
                if df is None or df.empty:
                    return {"_unresolved": True, "reason": "fetch_failed", "symbol": symbol}
                path = df[df.index > signal_time]
                if len(path) < hold_candles:
                    # هنوز کندل‌های کافی بعد از سیگنال بسته نشده‌اند - دوباره امتحان می‌شود
                    return {"_unresolved": True, "reason": "not_enough_elapsed_candles", "symbol": symbol}
                path = path.head(hold_candles)
            else:
                # سازگاری با سیگنال‌های قدیمی‌تر که signal_candle_ts ندارند (تخمینی)
                df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=hold_candles + 15)
                if df is None or len(df) < hold_candles:
                    return {"_unresolved": True, "reason": "fetch_failed_legacy", "symbol": symbol}
                path = df.tail(hold_candles)
            
            is_long = bool(direction and "LONG" in direction)
            future_price = float(path["close"].iloc[-1]) if len(path) > 0 else float(df["close"].iloc[-1])
            slippage = CONFIG.get("SLIPPAGE_PCT", 0.0005)
            result = None
            exit_price = None
            which_target = "TIMEOUT"
            candles_to_result = None
            
            # ردیابی حداکثر پیشروی به نفع (MFE) و علیه (MAE) پوزیشن در طول مسیر - حتی روی معاملات بازنده،
            # این نشون می‌ده قیمت چقدر به TP1 نزدیک شده بود (برای تحلیل کیفیت زمان‌بندی ورود)
            mfe_pct = 0.0
            mae_pct = 0.0
            
            for candle_num, (_, row) in enumerate(path.iterrows(), start=1):
                hi, lo = row["high"], row["low"]
                if is_long:
                    favorable = (hi - entry) / entry * 100
                    adverse = (entry - lo) / entry * 100
                else:
                    favorable = (entry - lo) / entry * 100
                    adverse = (hi - entry) / entry * 100
                mfe_pct = max(mfe_pct, favorable)
                mae_pct = max(mae_pct, adverse)
                
                if not CONFIG.get("AUTO_LEARN_PATH_BASED", True) or result is not None:
                    continue
                
                if is_long:
                    if lo <= sl:
                        result = "loss"
                        exit_price = sl * (1 - slippage)
                        which_target = "SL"
                        candles_to_result = candle_num
                    else:
                        hit_tps = [(idx, tp) for idx, tp in enumerate(tps) if hi >= tp]
                        if hit_tps:
                            # همیشه اولین هدف (TP1) گزارش می‌شود، حتی اگر تو همون کندل TP2/TP3 هم لمس شده باشند
                            # چون در استراتژی تک‌خروجی، خروج واقعی در TP1 اتفاق می‌افتد
                            best_idx, exit_price = min(hit_tps, key=lambda x: x[0])
                            result = "win"
                            which_target = f"TP{best_idx + 1}"
                            candles_to_result = candle_num
                else:
                    if hi >= sl:
                        result = "loss"
                        exit_price = sl * (1 + slippage)
                        which_target = "SL"
                        candles_to_result = candle_num
                    else:
                        hit_tps = [(idx, tp) for idx, tp in enumerate(tps) if lo <= tp]
                        if hit_tps:
                            best_idx, exit_price = min(hit_tps, key=lambda x: x[0])
                            result = "win"
                            which_target = f"TP{best_idx + 1}"
                            candles_to_result = candle_num
            
            if result is None:
                # نه SL و نه TP طی بازه برخورد نکرد -> بر اساس قیمت پایانی مسیر تصمیم بگیر (مثل بک‌تست)
                exit_price = future_price
                result = "win" if ((future_price > entry) == is_long) else "loss"
                which_target = "TIMEOUT"
                candles_to_result = len(path)
            
            if is_long:
                return_pct = (exit_price - entry) / entry * 100
            else:
                return_pct = (entry - exit_price) / entry * 100
            
            # کسر کمیسیون رفت‌وبرگشت (باز+بسته شدن پوزیشن) تا بازده گزارش‌شده خالص باشد نه ناخالص
            return_pct -= CONFIG["COMMISSION_PCT"] * 2 * 100
            
            is_win = result == "win"
            
            trade_result = {
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "exit": exit_price,
                "return_pct": return_pct,
                "win": is_win,
                "which_target": which_target,
                "outcome_label": which_target if which_target in ("TP1", "TP2", "TP3", "SL") else "TIMEOUT",
                "time_to_result_min": (candles_to_result * minutes_per_candle) if candles_to_result else None,
                "mfe_pct": round(mfe_pct, 3),
                "mae_pct": round(mae_pct, 3),
                "pre_signal_change_15m": signal.get("pre_signal_change_15m"),
                "features": signal.get("learning_features", {}),
                "signal_confidence": signal.get("confidence", 0),
                "auto_learned": True,
            }
            
            return trade_result
            
        except Exception as e:
            logger.error(f"خطا در شبیه‌سازی نتیجه {signal_data.get('symbol')}: {e}")
            return {"_unresolved": True, "reason": f"exception: {e}", "symbol": signal_data.get("symbol")}

    def _process_learning_queue(self):
        """پردازش صف یادگیری - در هر دور، همه‌ی آیتم‌های رسیده به زمان را پردازش می‌کند (نه فقط یکی)،
        و اگر داده موقتاً در دسترس نبود (مثلاً خطای شبکه)، به‌جای حذف بی‌صدا، چند بار تلاش مجدد می‌کند"""
        logger.info("شروع پردازش صف یادگیری...")
        max_retries = CONFIG.get("AUTO_LEARN_MAX_RETRIES", 3)
        
        while self.running:
            try:
                if len(self.learning_queue) == 0:
                    time.sleep(30)
                    continue
                
                minutes_per_candle = _interval_to_minutes(CONFIG.get("KLINE_INTERVAL", "1h")) or 60
                # کمی زمان اضافه (۱۰٪) تا مطمئن شویم آخرین کندل موردنیاز کاملاً بسته شده است
                wait_seconds = int(get_max_hold_candles() * minutes_per_candle * 60 * 1.1)
                now = time.time()
                
                # چون صف به ترتیب زمان مرتب است (قدیمی‌ترین اول)، تا وقتی جلوترین آیتم به زمانش
                # نرسیده، مطمئنیم بقیه هم نرسیده‌اند - ولی همه‌ی آیتم‌های *رسیده* را در همین دور پردازش می‌کنیم
                processed_count = 0
                # سقف مطلق: صرف‌نظر از تعداد retry، هیچ آیتمی نباید بیش از این مدت در صف بماند.
                # این یک لایه‌ی محافظتی اضافه است در برابر هر باگ ناشناخته‌ای که ممکن است باعث
                # گیرکردن دائمی یک آیتم خاص شود (مشاهده شده در عمل با برخی نمادها).
                hard_expiry_seconds = wait_seconds * 6
                
                while len(self.learning_queue) > 0:
                    signal_data = self.learning_queue[0]
                    signal_time = signal_data.get("timestamp", 0)
                    age = now - signal_time
                    
                    if age >= hard_expiry_seconds:
                        self.learning_queue.popleft()
                        logger.error(f"🔴 {signal_data.get('symbol')} پس از {age/60:.0f} دقیقه (سقف مطلق) بدون پردازش از صف حذف شد - این نشانه‌ی یک باگ است، لطفاً debug.log را چک کنید")
                        continue
                    
                    if age < wait_seconds:
                        break  # جلوترین آیتم هنوز زمانش نرسیده -> بقیه هم نرسیده‌اند
                    
                    self.learning_queue.popleft()
                    result = self._simulate_outcome(signal_data)
                    
                    if result and not result.get("_unresolved"):
                        self.memory.add_trade_result(result)
                        win_emoji = "✅" if result["win"] else "❌"
                        logger.info(f"🎓 خودآموزی: {result['symbol']} {result['direction']} → {result['return_pct']:.2f}% {win_emoji}")
                        processed_count += 1
                        
                        # به‌روزرسانی سیستم یادگیری هر 5 معامله
                        if len(self.memory.trades) % 5 == 0 and len(self.memory.trades) > 0:
                            logger.info("به‌روزرسانی سیستم یادگیری بر اساس معاملات جدید...")
                            try:
                                weight_learner.update_weights()
                                pattern_recognizer.learn_patterns()
                                param_optimizer.optimize(force=True)
                                param_optimizer.apply_optimized_params()
                                ml_model.train()  # خودش تشخیص می‌دهد که آیا واقعاً وقت بازآموزی رسیده یا نه
                                param_optimizer.optimize_regime_thresholds()
                            except Exception as learn_err:
                                # این بخش نباید بتواند کل پردازش صف را متوقف کند
                                logger.error(f"خطا در به‌روزرسانی یادگیری (نادیده گرفته شد، صف ادامه می‌یابد): {learn_err}")
                    else:
                        # داده ناکافی/خطای شبکه - به‌جای حذف بی‌صدا، چند بار تلاش مجدد کن، با ثبت دلیل دقیق
                        reason = result.get("reason", "unknown") if result else "unknown"
                        retry_count = signal_data.get("retry_count", 0) + 1
                        if retry_count <= max_retries:
                            signal_data["retry_count"] = retry_count
                            signal_data["timestamp"] = now  # زمان را ریست کن تا کمی بعد دوباره امتحان شود
                            self.learning_queue.append(signal_data)
                            logger.warning(f"⚠️ {signal_data.get('symbol')} حل نشد ({reason}) - تلاش مجدد {retry_count}/{max_retries}")
                        else:
                            logger.warning(f"❌ {signal_data.get('symbol')} پس از {max_retries} تلاش رد شد ({reason}) و بدون ثبت نتیجه از صف حذف شد")
                
                if processed_count > 0:
                    self._save_queue()
                
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"خطا در پردازش صف یادگیری: {e}")
                time.sleep(60)

    def start(self):
        """راه‌اندازی سیستم خودآموزی"""
        if self.running:
            return
        self.running = True
        self.learning_thread = threading.Thread(target=self._run_queue_supervised, daemon=True)
        self.learning_thread.start()
        logger.info("🧠 سیستم خودآموزی خودکار راه‌اندازی شد")

    def _run_queue_supervised(self):
        """پوششی بیرونی دور _process_learning_queue - اگر به هر دلیل (حتی خطاهای پیش‌بینی‌نشده)
        خود تابع کرش کند، ترد به‌جای مردن بی‌صدا، دوباره راه‌اندازی می‌شود. این یک لایه‌ی محافظتی
        اضافه است، مکمل رفع مشکل انکودینگ خروجی، نه جایگزین آن."""
        while self.running:
            try:
                self._process_learning_queue()
            except Exception as e:
                logger.error(f"⚠️ ترد یادگیری به‌طور غیرمنتظره متوقف شد، در حال راه‌اندازی مجدد: {e}")
                time.sleep(10)

    def stop(self):
        self.running = False
        logger.info("سیستم خودآموزی متوقف شد")

    def is_healthy(self) -> bool:
        """چک اینکه ترد یادگیری واقعاً زنده است - برای هشدار زودهنگام در گزارش ساعتی"""
        return bool(self.learning_thread and self.learning_thread.is_alive())

    def get_queue_status(self) -> dict:
        """دریافت وضعیت صف یادگیری"""
        return {
            "queue_size": len(self.learning_queue),
            "is_running": self.running,
            "first_signal": self.learning_queue[0] if self.learning_queue else None
        }

    def get_pending_status(self, price_map: Dict[str, float]) -> dict:
        """بررسی سریع وضعیت لحظه‌ای سیگنال‌های در صف انتظار (هنوز نهایی نشده‌اند)
        بر اساس آخرین قیمت لحظه‌ای - برای گزارش ساعتی، بدون نیاز به درخواست شبکه اضافه.
        توجه: این فقط یک تخمین لحظه‌ای است (نه بررسی کامل مسیر)؛ نتیجه نهایی و قطعی
        هر معامله همچنان توسط _simulate_outcome پس از گذشت AUTO_LEARN_HOURS محاسبه می‌شود."""
        result = {"total_pending": len(self.learning_queue), "tp1_hit": 0, "sl_hit": 0, "still_open": 0, "unknown": 0, "items": [], "regime_counts": {}}
        try:
            for item in self.learning_queue:
                signal = item.get("signal", {})
                symbol = signal.get("symbol")
                direction = signal.get("direction", "")
                entry = signal.get("entry")
                sl = signal.get("sl")
                tps = signal.get("tps") or []
                regime = signal.get("market_regime", "UNKNOWN")
                result["regime_counts"][regime] = result["regime_counts"].get(regime, 0) + 1
                current_price = price_map.get(symbol)

                if current_price is None or entry is None or sl is None or not tps:
                    result["unknown"] += 1
                    continue

                is_long = "LONG" in direction
                tp1 = tps[0]
                status = "OPEN"
                if is_long:
                    if current_price <= sl:
                        status = "SL_HIT"
                    elif current_price >= tp1:
                        status = "TP1_HIT"
                else:
                    if current_price >= sl:
                        status = "SL_HIT"
                    elif current_price <= tp1:
                        status = "TP1_HIT"

                if status == "TP1_HIT":
                    result["tp1_hit"] += 1
                elif status == "SL_HIT":
                    result["sl_hit"] += 1
                else:
                    result["still_open"] += 1

                elapsed_min = int((time.time() - item.get("timestamp", time.time())) / 60)
                result["items"].append({
                    "symbol": symbol, "direction": direction, "status": status,
                    "confidence": item.get("confidence", 0), "elapsed_min": elapsed_min, "regime": regime
                })
        except Exception as e:
            logger.error(f"خطا در بررسی وضعیت صف انتظار: {e}")
        return result


# ============================================================================
# بخش 10: توابع کمکی (Utilities) - کامل
# ============================================================================

_KLINES_CACHE: Dict[Tuple[str, str, int], Tuple[pd.DataFrame, float]] = {}
_KLINES_CACHE_TTL = 60.0
LAST_SIGNAL_TIMES = {}

def _interval_to_minutes(s: str) -> Optional[int]:
    """تبدیل تایم‌فریم به دقیقه"""
    try:
        t = s.strip().lower()
        if t.endswith("min"):
            return int(t[:-3])
        if t.endswith("m") and not t.endswith(("am", "pm")):
            return int(t[:-1])
        if t.endswith("h"):
            return int(t[:-1]) * 60
        if t.endswith("d"):
            return int(t[:-1]) * 60 * 24
        if t.endswith("w"):
            return int(t[:-1]) * 60 * 24 * 7
        return int(t) if t.isdigit() else None
    except Exception as e:
        logger.error(f"خطا در تبدیل تایم‌فریم {s}: {e}")
        return None


def get_max_hold_candles() -> int:
    """حداکثر تعداد کندل نگه‌داشتن پوزیشن، بر اساس تایم‌فریم فعلی و MAX_HOLD_MINUTES محاسبه می‌شود -
    به این ترتیب چه بات با 15m اجرا بشه (اسکالپ) چه با 1h (سوئینگ)، مدت نگه‌داری واقعی همیشه متناسب می‌ماند
    (قبلاً این عدد ثابت 24 کندل بود که روی 15m می‌شد 6 ساعت، کاملاً ناسازگار با هدف اسکالپ 15-20 دقیقه‌ای)"""
    minutes_per_candle = _interval_to_minutes(CONFIG.get("KLINE_INTERVAL", "1h")) or 60
    return max(1, round(CONFIG.get("MAX_HOLD_MINUTES", 180) / minutes_per_candle))

def send_telegram_message(text: str, message_type: str = "message", retries: int = 3) -> bool:
    """ارسال مطمئن پیام تلگرام - با تلاش مجدد (retry+backoff) و بررسی واقعی فیلد "ok" پاسخ تلگرام
    (نه فقط کد HTTP، چون تلگرام گاهی 200 برمی‌گرداند ولی ok:false)"""
    token = CONFIG.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = CONFIG.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.error(f"❌ Telegram {message_type}: TOKEN یا CHAT_ID تنظیم نشده است")
        return False
    
    payload_text = str(text)[:4000]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, data={"chat_id": chat_id, "text": payload_text}, timeout=20)
            try:
                body = response.json()
            except Exception:
                body = {}
            if response.status_code == 200 and body.get("ok") is True:
                logger.debug(f"✅ Telegram {message_type} ارسال شد (تلاش {attempt}/{retries})")
                return True
            description = body.get("description", response.text[:300])
            logger.warning(f"⚠️ Telegram {message_type} ارسال نشد | HTTP={response.status_code} | تلاش {attempt}/{retries} | {description}")
            if response.status_code in (400, 401, 403):
                break  # خطای غیرقابل‌بازیابی (توکن نامعتبر و...) - تلاش مجدد فایده ندارد
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ Telegram {message_type}: timeout | تلاش {attempt}/{retries}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"⚠️ Telegram {message_type}: خطای اتصال | تلاش {attempt}/{retries}: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Telegram {message_type}: {e} | تلاش {attempt}/{retries}")
        if attempt < retries:
            time.sleep(2 * attempt)
    
    logger.error(f"❌ Telegram {message_type} پس از {retries} تلاش ارسال نشد")
    return False

def test_telegram_connection() -> bool:
    """تست واقعی اعتبار توکن/چت‌آیدی تلگرام در شروع برنامه، بدون ارسال پیام آزمایشی به چت"""
    token = CONFIG.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = CONFIG.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.error("❌ Telegram: TOKEN یا CHAT_ID تنظیم نشده است")
        return False
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        data = r.json()
        if r.status_code == 200 and data.get("ok"):
            logger.info(f"✅ اتصال Telegram Bot موفق است: @{data.get('result', {}).get('username', 'unknown')}")
            return True
        logger.error(f"❌ اتصال Telegram Bot ناموفق | HTTP={r.status_code} | {data.get('description', r.text[:300])}")
    except Exception as e:
        logger.error(f"❌ خطا در تست Telegram Bot: {e}")
    return False

def send_telegram_message_with_cooldown(symbol: str, direction: str, text: str, cooldown: int = 600) -> bool:
    """ارسال پیام تلگرام با محدودیت زمانی"""
    global LAST_SIGNAL_TIMES
    
    now = time.time()
    key = f"{symbol.upper()}_{direction.upper()}"
    
    if now - LAST_SIGNAL_TIMES.get(key, 0) < cooldown:
        return False
    
    LAST_SIGNAL_TIMES[key] = now
    return send_telegram_message(text)

def load_json_file(path: str):
    """بارگذاری امن فایل JSON"""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return json.loads(content) if content else None
    except json.JSONDecodeError:
        logger.warning(f"فایل JSON خراب: {path}")
        try:
            os.remove(path)
        except Exception:
            pass
        return None
    except Exception as e:
        logger.error(f"خطا در خواندن {path}: {e}")
    return None

def save_json_file(path: str, obj) -> bool:
    """ذخیره امن داده‌ها در فایل JSON"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        def convert(item):
            if isinstance(item, (np.integer, np.int64)):
                return int(item)
            if isinstance(item, (np.floating, np.float64)):
                return float(item)
            if isinstance(item, (np.bool_, bool)):
                return bool(item)
            if isinstance(item, (np.ndarray, pd.Series)):
                return item.tolist()
            if isinstance(item, pd.DataFrame):
                return item.to_dict(orient="records")
            if isinstance(item, dict):
                return {k: convert(v) for k, v in item.items()}
            if isinstance(item, (list, tuple)):
                return [convert(i) for i in item]
            if isinstance(item, datetime):
                return item.isoformat()
            return item
        
        return _atomic_write_json(path, convert(obj))
    except Exception as e:
        logger.error(f"خطا در ذخیره {path}: {e}")
        return False


# ============================================================================
# بخش 11: مدیریت داده (Data Management) - کامل
# ============================================================================

def load_history() -> dict:
    """بارگذاری تاریخچه معاملات"""
    data = load_json_file(PATHS["HISTORY_FILE"])
    return data if isinstance(data, dict) else {}

def save_history(history: dict) -> None:
    save_json_file(PATHS["HISTORY_FILE"], history)

def update_history_with_coins(history: dict, coins: List[dict]) -> None:
    """به‌روزرسانی تاریخچه قیمت کوین‌ها"""
    try:
        now = int(time.time())
        for coin in coins:
            symbol = coin.get("symbol", "").lower()
            if not symbol:
                continue
            try:
                price = float(coin.get("current_price") or 0.0)
            except Exception:
                price = 0.0
            change_1h = coin.get("price_change_percentage_1h")
            
            if symbol not in history:
                history[symbol] = []
            
            history[symbol].append({
                "time": now,
                "price": price,
                "change_1h": change_1h,
            })
            
            # نگهداری داده‌های 4 ساعت اخیر
            history[symbol] = [x for x in history[symbol] if now - x.get("time", 0) <= 14400]
        
        save_history(history)
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی تاریخچه: {e}")

def get_change_from_history(history: dict, symbol: str, interval_seconds: int) -> Optional[float]:
    """محاسبه تغییر قیمت در بازه زمانی مشخص"""
    try:
        key = symbol.lower()
        if key not in history or not history[key]:
            return None
        
        now = int(time.time())
        entries = sorted(history[key], key=lambda x: x.get("time", 0))
        target_time = now - interval_seconds
        
        past_entry = None
        for entry in entries:
            if entry.get("time", 0) <= target_time:
                past_entry = entry
        
        if not past_entry:
            return None
        
        price_now = entries[-1].get("price", 0.0)
        price_past = past_entry.get("price", 0.0)
        
        if not price_now or not price_past or price_past <= 0:
            return None
        
        return ((price_now - price_past) / price_past) * 100.0
    except Exception as e:
        logger.error(f"خطا در محاسبه تغییر {symbol}: {e}")
        return None

def fetch_binance_all_ticker() -> List[dict]:
    """دریافت لیست همه تیکرهای USDT از Binance Futures"""
    try:
        resp = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        ret = []
        
        for d in data:
            sym = d.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            try:
                last = float(d.get("lastPrice", 0.0))
            except Exception:
                last = 0.0
            try:
                change_pct = float(d.get("priceChangePercent", 0.0))
            except Exception:
                change_pct = 0.0
            
            ret.append({
                "symbol": sym.upper(),
                "current_price": last,
                "price_change_percentage_1h": change_pct,
            })
        
        logger.debug(f"{len(ret)} تیکر USDT دریافت شد")
        return ret
        
    except Exception as e:
        logger.error(f"خطا در دریافت تیکرها: {e}")
        return []

def _validate_and_clean_klines_df(df: pd.DataFrame, interval: str) -> Optional[pd.DataFrame]:
    """اعتبارسنجی و پاکسازی دیتا فریم کندل‌ها"""
    if df is None or df.empty:
        return None
    
    df = df.copy()
    
    if not isinstance(df.index, pd.DatetimeIndex):
        if "time" in df.columns:
            df = df.set_index(pd.to_datetime(df["time"]))
            df = df.drop(columns=["time"], errors='ignore')
        else:
            return None
    
    df = df.sort_index()
    df = df[~df.index.duplicated(keep='last')]
    
    required_cols = ["open", "high", "low", "close", "volume"]
    for c in required_cols:
        if c not in df.columns:
            logger.error(f"ستون {c} در دیتافریم وجود ندارد")
            return None
    
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["volume"] > 0) & (df["close"] > 0)]
    
    minutes = _interval_to_minutes(interval) or 60
    if minutes > 0:
        diffs = df.index.to_series().diff().dropna()
        expected_delta = pd.Timedelta(minutes=minutes)
        big_gaps = diffs[diffs > expected_delta * 3]
        if not big_gaps.empty:
            logger.debug(f"{len(big_gaps)} gap بزرگ در کندل‌های {interval}")
    
    return df

def fetch_klines_df(symbol: str, interval: str = None, limit: int = None, use_cache: bool = True) -> Optional[pd.DataFrame]:
    """دریافت دیتا فریم کندل‌ها از بایننس"""
    try:
        if interval is None:
            interval = CONFIG.get("KLINE_INTERVAL", "1h")
        if limit is None:
            limit = CONFIG.get("KLINE_LIMIT", 1000)
        
        key = (symbol.upper(), interval, int(limit))
        now_ts = time.time()
        
        if use_cache and key in _KLINES_CACHE:
            df_cached, ts = _KLINES_CACHE[key]
            if now_ts - ts < _KLINES_CACHE_TTL:
                logger.debug(f"کش برای {symbol} ({interval}) - HIT")
                return df_cached.copy()
        
        logger.debug(f"دریافت کندل‌های {symbol} ({interval})...")
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}"
        
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                
                rows = []
                for x in data:
                    try:
                        rows.append({
                            "time": pd.to_datetime(int(x[0]), unit='ms'),
                            "open": float(x[1]),
                            "high": float(x[2]),
                            "low": float(x[3]),
                            "close": float(x[4]),
                            "volume": float(x[5])
                        })
                    except Exception:
                        continue
                
                df = pd.DataFrame(rows).set_index("time").sort_index()
                df = _validate_and_clean_klines_df(df, interval)
                
                if df is not None and not df.empty:
                    _KLINES_CACHE[key] = (df.copy(), now_ts)
                    logger.debug(f"دریافت {len(df)} کندل برای {symbol}")
                    return df
                
            except requests.exceptions.Timeout:
                if attempt < 2:
                    logger.debug(f"تایم اوت، تلاش مجدد {attempt+2}/3...")
                    time.sleep(2)
            except Exception as e:
                if attempt == 2:
                    logger.error(f"خطا در دریافت کندل {symbol}: {e}")
                else:
                    time.sleep(2)
        
        return None
        
    except Exception as e:
        logger.error(f"خطا در fetch_klines_df {symbol}: {e}")
        return None


# ============================================================================
# بخش 12: اندیکاتورهای تکنیکال (Technical Indicators) - کامل
# ============================================================================

def sma_pd(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average"""
    if period <= 0 or len(series) < period:
        return pd.Series(index=series.index, dtype=float).fillna(series.mean() if len(series) > 0 else 0)
    return series.rolling(period, min_periods=min(period, len(series))).mean()

def ema_pd(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average"""
    if period <= 0 or len(series) == 0:
        return pd.Series(index=series.index, dtype=float).fillna(0)
    return series.ewm(span=period, adjust=False, min_periods=1).mean()

def macd_pd(series: pd.Series, fast=12, slow=26, signal=9):
    """MACD Indicator"""
    ema_fast = ema_pd(series, fast)
    ema_slow = ema_pd(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema_pd(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def rsi_pd(series: pd.Series, period=14) -> pd.Series:
    """Relative Strength Index"""
    if len(series) < period:
        return pd.Series(index=series.index, dtype=float).fillna(50)
    
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=1).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=1).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def true_range_pd(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True Range calculation"""
    if high.empty or low.empty or close.empty:
        return pd.Series(dtype=float)
    
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.fillna(tr1)

def atr_pd(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    """Average True Range"""
    tr = true_range_pd(high, low, close)
    return tr.ewm(alpha=1/period, adjust=False, min_periods=1).mean()

def bollinger_pd(series: pd.Series, period=20, mult=2.0):
    """Bollinger Bands"""
    mid = sma_pd(series, period)
    std = series.rolling(period, min_periods=period).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower

def stochastic_pd(high: pd.Series, low: pd.Series, close: pd.Series, k_period=14, d_period=3):
    """Stochastic Oscillator"""
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    k = 100 * (close - lowest_low) / denom
    k = k.fillna(50)
    d = k.rolling(d_period, min_periods=1).mean().fillna(50)
    return k, d

def adx_pd(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    """Average Directional Index"""
    if len(high) < period:
        return pd.Series(index=high.index, dtype=float).fillna(25)
    
    up_move = high.diff()
    down_move = -low.diff()
    
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    
    tr = true_range_pd(high, low, close)
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=1).mean()
    
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False, min_periods=1).mean() / atr.replace(0, np.nan))
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/period, adjust=False, min_periods=1).mean()

def obv_pd(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume - جریان حجم تجمعی، برای تأیید روند با حجم"""
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).fillna(0).cumsum()

def cci_pd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """Commodity Channel Index - بیش‌خرید/بیش‌فروش نسبت به میانگین قیمت معمولی"""
    typical_price = (high + low + close) / 3.0
    sma_tp = typical_price.rolling(period, min_periods=1).mean()
    mean_dev = typical_price.rolling(period, min_periods=1).apply(
        lambda x: np.mean(np.abs(x - x.mean())), raw=True
    )
    cci = (typical_price - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))
    return cci.fillna(0)

def williams_r_pd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R - نوسان‌نمای بیش‌خرید/بیش‌فروش (بازه صفر تا -100)"""
    highest_high = high.rolling(period, min_periods=1).max()
    lowest_low = low.rolling(period, min_periods=1).min()
    denom = (highest_high - lowest_low).replace(0, np.nan)
    wr = -100 * (highest_high - close) / denom
    return wr.fillna(-50)

def mfi_pd(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14) -> pd.Series:
    """Money Flow Index - RSI وزن‌دار شده با حجم"""
    typical_price = (high + low + close) / 3.0
    money_flow = typical_price * volume
    tp_diff = typical_price.diff()
    positive_flow = money_flow.where(tp_diff > 0, 0.0)
    negative_flow = money_flow.where(tp_diff < 0, 0.0)
    pos_sum = positive_flow.rolling(period, min_periods=1).sum()
    neg_sum = negative_flow.rolling(period, min_periods=1).sum()
    money_ratio = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + money_ratio))
    return mfi.fillna(50)

def vwap_pd(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    """VWAP تجمعی روی بازه دیتافریم فعلی (نه ریست روزانه) - برای مقایسه قیمت با میانگین وزنی حجم"""
    typical_price = (high + low + close) / 3.0
    cum_vol = volume.cumsum().replace(0, np.nan)
    cum_tp_vol = (typical_price * volume).cumsum()
    return (cum_tp_vol / cum_vol).bfill().fillna(close)

def supertrend_pd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, mult: float = 3.0):
    """SuperTrend - خط روند پویا بر اساس ATR، برمی‌گرداند (خط، جهت) که جهت=1 صعودی و -1 نزولی است"""
    atr = atr_pd(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper_band = hl2 + mult * atr
    lower_band = hl2 - mult * atr

    n = len(close)
    final_upper = upper_band.copy()
    final_lower = lower_band.copy()
    direction = pd.Series(1, index=close.index, dtype=int)
    supertrend = pd.Series(0.0, index=close.index)

    if n == 0:
        return supertrend, direction

    close_vals = close.values
    upper_vals = final_upper.values.copy()
    lower_vals = final_lower.values.copy()
    dir_vals = np.ones(n, dtype=int)
    st_vals = np.zeros(n)

    st_vals[0] = upper_vals[0]
    for i in range(1, n):
        if close_vals[i - 1] <= upper_vals[i - 1]:
            upper_vals[i] = min(upper_vals[i], upper_vals[i - 1])
        if close_vals[i - 1] >= lower_vals[i - 1]:
            lower_vals[i] = max(lower_vals[i], lower_vals[i - 1])

        if st_vals[i - 1] == upper_vals[i - 1]:
            dir_vals[i] = -1 if close_vals[i] <= upper_vals[i] else 1
        else:
            dir_vals[i] = 1 if close_vals[i] >= lower_vals[i] else -1

        st_vals[i] = lower_vals[i] if dir_vals[i] == 1 else upper_vals[i]

    return pd.Series(st_vals, index=close.index), pd.Series(dir_vals, index=close.index)


# ============================================================================
# بخش 13: تشخیص الگوهای پرایس اکشن (Price Action) - کامل
# ============================================================================

def detect_price_action_signals(df: pd.DataFrame) -> List[str]:
    """تشخیص الگوهای Price Action"""
    if df.shape[0] < 3:
        return []
    
    signals = []
    try:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        body = abs(last["close"] - last["open"])
        total_range = max(last["high"] - last["low"], 1e-9)
        upper_wick = last["high"] - max(last["close"], last["open"])
        lower_wick = min(last["close"], last["open"]) - last["low"]
        
        # Pin Bar
        if body <= 0.25 * total_range:
            if upper_wick >= 2 * body and upper_wick >= 0.3 * total_range:
                signals.append("Pin Bar - rejection بالاتر")
            if lower_wick >= 2 * body and lower_wick >= 0.3 * total_range:
                signals.append("Pin Bar - rejection پایین")
        
        # Inside Bar
        if last["high"] <= prev["high"] and last["low"] >= prev["low"]:
            signals.append("Inside Bar")
        
        # Engulfing
        prev_body = abs(prev["close"] - prev["open"])
        if prev["close"] < prev["open"] and last["close"] > last["open"] and body > prev_body:
            signals.append("Engulfing صعودی")
        if prev["close"] > prev["open"] and last["close"] < last["open"] and body > prev_body:
            signals.append("Engulfing نزولی")
        
        # Higher Highs / Lower Lows
        highs = df["high"].values
        lows = df["low"].values
        
        if len(highs) >= 3:
            if highs[-1] > highs[-2] > highs[-3]:
                signals.append("Higher Highs")
            if highs[-1] < highs[-2] < highs[-3]:
                signals.append("Lower Highs")
        
        if len(lows) >= 3:
            if lows[-1] > lows[-2] > lows[-3]:
                signals.append("Higher Lows")
            if lows[-1] < lows[-2] < lows[-3]:
                signals.append("Lower Lows")
        
    except Exception as e:
        logger.error(f"خطا در تشخیص پرایس اکشن: {e}")
    
    return signals

def find_swing_levels_pd(df: pd.DataFrame, lookback: int = 8) -> dict:
    """یافتن سقف‌ها و کف‌های سوئینگ"""
    try:
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)
        swings = {"highs": [], "lows": []}
        
        if n < (2 * lookback + 1):
            return swings
        
        for i in range(lookback, n - lookback):
            if highs[i] == np.max(highs[i - lookback:i + lookback + 1]):
                swings["highs"].append((i, float(highs[i])))
            if lows[i] == np.min(lows[i - lookback:i + lookback + 1]):
                swings["lows"].append((i, float(lows[i])))
        
        swings["highs"] = swings["highs"][-5:]
        swings["lows"] = swings["lows"][-5:]
        return swings
    except Exception as e:
        logger.error(f"خطا در یافتن سطوح سوئینگ: {e}")
        return {"highs": [], "lows": []}

def detect_market_regime(df: pd.DataFrame) -> str:
    """تشخیص رژیم بازار"""
    try:
        if df.empty or len(df) < 20:
            return "UNKNOWN"
        
        atr_ratio = (df["atr"].iloc[-1] / df["close"].iloc[-1]) if "atr" in df.columns else 0
        adx_val = adx_pd(df["high"], df["low"], df["close"]).iloc[-1] if len(df) > 14 else 0
        
        if adx_val < 20:
            return "RANGING"
        elif atr_ratio > 0.02:
            return "VOLATILE"
        else:
            return "TRENDING"
    except Exception as e:
        logger.error(f"خطا در تشخیص رژیم بازار: {e}")
        return "UNKNOWN"

def volatility_filter(df: pd.DataFrame, threshold: float = 2.5) -> bool:
    """فیلتر نوسان غیرعادی بازار"""
    try:
        if len(df) < 20:
            return True
        
        returns = df["close"].pct_change().abs()
        volatility = returns.rolling(20).std()
        current_vol = returns.iloc[-1] if not returns.empty else 0.0
        ref_vol = volatility.iloc[-1] if not volatility.empty else 0.0
        
        if pd.isna(ref_vol) or ref_vol == 0:
            return True
        
        return current_vol <= (ref_vol * threshold)
    except Exception as e:
        logger.error(f"خطا در فیلتر نوسان: {e}")
        return True

def symbol_quality_check(symbol: str) -> bool:
    """بررسی کیفیت بازار"""
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            return False
        
        ticker = resp.json()
        
        quote_volume = float(ticker.get("quoteVolume", 0))
        if quote_volume < CONFIG["MIN_QUOTE_VOLUME"]:
            return False
        
        bid_price = float(ticker.get("bidPrice", 0))
        ask_price = float(ticker.get("askPrice", 0))
        if bid_price > 0 and ask_price > 0:
            spread = (ask_price - bid_price) / ask_price
            if spread > CONFIG["MAX_SPREAD_PCT"]:
                return False
        
        price_change = float(ticker.get("priceChangePercent", 0))
        if abs(price_change) > CONFIG["MAX_24H_CHANGE"]:
            return False
        
        return True
    except Exception as e:
        logger.debug(f"خطا در بررسی کیفیت {symbol}: {e}")
        return False

def detect_false_breakout(df: pd.DataFrame, swing_levels: dict) -> bool:
    """تشخیص شکست‌های فیک"""
    try:
        if len(df) < 3:
            return False
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        if swing_levels.get("highs"):
            resistance = swing_levels["highs"][-1][1]
            if prev["high"] > resistance and last["close"] < resistance:
                return True
        
        if swing_levels.get("lows"):
            support = swing_levels["lows"][-1][1]
            if prev["low"] < support and last["close"] > support:
                return True
        
        return False
    except Exception as e:
        logger.error(f"خطا در تشخیص شکست فیک: {e}")
        return False

def dynamic_risk_management(symbol: str, df: pd.DataFrame) -> float:
    """تنظیم ریسک بر اساس نوسان بازار"""
    try:
        if len(df) < 14 or "atr" not in df.columns:
            return CONFIG["RISK_PERCENT"]
        
        close = df["close"].iloc[-1]
        atr_val = df["atr"].iloc[-1]
        atr_percent = (atr_val / close) * 100 if close else 0.0
        
        if atr_percent > 5:
            return CONFIG["RISK_PERCENT"] * 0.5
        elif atr_percent < 1:
            return CONFIG["RISK_PERCENT"] * 2.0
        else:
            return CONFIG["RISK_PERCENT"]
    except Exception as e:
        logger.error(f"خطا در مدیریت ریسک {symbol}: {e}")
        return CONFIG["RISK_PERCENT"]


# ============================================================================
# بخش 14: توابع سیگنال و بک‌تست - کامل
# ============================================================================

def compute_confirmation_signals(df: pd.DataFrame, require_volume: bool = True) -> pd.DataFrame:
    """محاسبه سیگنال‌های تأیید با چند اندیکاتور مستقل (confluence) برای کاهش سیگنال‌های اشتباه"""
    try:
        df = df.copy()
        df["ema_s"] = ema_pd(df["close"], CONFIG["EMA_SHORT"])
        df["ema_m"] = ema_pd(df["close"], CONFIG["EMA_MED"])
        df["ema_l"] = ema_pd(df["close"], CONFIG["EMA_LONG"])
        
        df["trend_up"] = (df["ema_s"] > df["ema_m"]) & (df["ema_m"] > df["ema_l"])
        df["trend_down"] = (df["ema_s"] < df["ema_m"]) & (df["ema_m"] < df["ema_l"])
        
        df["rsi"] = rsi_pd(df["close"], CONFIG["RSI_PERIOD"])
        macd, macd_sig, _ = macd_pd(df["close"])
        df["macd"] = macd
        df["macd_sig"] = macd_sig
        
        df["momentum_pos"] = (df["rsi"] > 55) & (df["macd"] > df["macd_sig"])
        df["momentum_neg"] = (df["rsi"] < 45) & (df["macd"] < df["macd_sig"])
        
        df["vol_sma20"] = df["volume"].rolling(20, min_periods=1).mean()
        df["volume_spike"] = df["volume"] > (df["vol_sma20"] * 1.2)

        # لایه تأیید مستقل دوم: قدرت روند (ADX) + سه نوسان‌نمای مستقل (CCI, Williams %R, MFI)
        # این‌ها از خانواده اندیکاتورهای متفاوتی هستند (نه صرفاً مشتق EMA/RSI) تا هم‌بستگی کاذب کمتر شود
        df["adx"] = adx_pd(df["high"], df["low"], df["close"])
        df["cci"] = cci_pd(df["high"], df["low"], df["close"], CONFIG.get("CCI_PERIOD", 20))
        df["williams_r"] = williams_r_pd(df["high"], df["low"], df["close"], CONFIG.get("WILLIAMS_R_PERIOD", 14))
        df["mfi"] = mfi_pd(df["high"], df["low"], df["close"], df["volume"], CONFIG.get("MFI_PERIOD", 14))
        _, st_dir = supertrend_pd(df["high"], df["low"], df["close"],
                                   CONFIG.get("SUPERTREND_PERIOD", 10), CONFIG.get("SUPERTREND_MULT", 3.0))
        df["supertrend_dir"] = st_dir

        trending_enough = df["adx"] >= CONFIG.get("ADX_TREND_MIN", 20)

        bull_votes = (
            (df["cci"] > 0).astype(int)
            + (df["williams_r"] > -50).astype(int)
            + (df["mfi"] > 50).astype(int)
            + (df["supertrend_dir"] > 0).astype(int)
        )
        bear_votes = (
            (df["cci"] < 0).astype(int)
            + (df["williams_r"] < -50).astype(int)
            + (df["mfi"] < 50).astype(int)
            + (df["supertrend_dir"] < 0).astype(int)
        )
        df["confluence_bull"] = bull_votes >= 3
        df["confluence_bear"] = bear_votes >= 3
        
        base_long = df["trend_up"] & df["momentum_pos"] & trending_enough & df["confluence_bull"]
        base_short = df["trend_down"] & df["momentum_neg"] & trending_enough & df["confluence_bear"]
        
        if require_volume:
            df["long_confirm"] = base_long & df["volume_spike"]
            df["short_confirm"] = base_short & df["volume_spike"]
        else:
            df["long_confirm"] = base_long
            df["short_confirm"] = base_short
        
        return df[["long_confirm", "short_confirm", "adx", "cci", "williams_r", "mfi", "supertrend_dir"]]
    except Exception as e:
        logger.error(f"خطا در محاسبه سیگنال‌های تأیید: {e}")
        return pd.DataFrame({"long_confirm": [False], "short_confirm": [False]})

def backtest_symbol_realistic(symbol: str, candles: int = None) -> dict:
    """بک‌تست واقعی یک نماد - از همان منطق تأیید سیگنال زنده (EMA+RSI+MACD+حجم+confluence) استفاده می‌کند
    تا وین‌ریت گزارش‌شده واقعاً همان استراتژی‌ای را بسنجد که سیگنال زنده تولید می‌کند."""
    try:
        if candles is None:
            candles = CONFIG["BACKTEST_CANDLES"]
        
        df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=candles)
        if df is None or df.empty or df.shape[0] < CONFIG["BACKTEST_MIN_REQUIRED"]:
            return {"symbol": symbol, "total": 0, "wins": 0, "losses": 0, "winrate": None}
        
        df = df.copy().reset_index(drop=True)
        df["atr"] = atr_pd(df["high"], df["low"], df["close"], CONFIG["ATR_PERIOD"])

        conf = compute_confirmation_signals(df, require_volume=CONFIG.get("REQUIRE_VOLUME_SPIKE", True))
        long_signal = conf["long_confirm"].values
        short_signal = conf["short_confirm"].values
        
        atrs = df["atr"].values
        wins = losses = total = 0
        gross_returns = []
        net_returns = []
        n = len(df)
        min_idx = CONFIG["BACKTEST_MIN_REQUIRED"]
        max_hold = get_max_hold_candles()
        # کمیسیون رفت‌وبرگشت (باز کردن + بستن پوزیشن) - باید از سود ناخالص کم شود تا سود خالص واقعی باشد
        round_trip_commission_pct = CONFIG["COMMISSION_PCT"] * 2 * 100
        
        for i in range(min_idx, n - 1):
            atr_v = atrs[i]
            if pd.isna(atr_v) or atr_v == 0:
                continue
            
            if long_signal[i]:
                signal_direction = "LONG"
            elif short_signal[i]:
                signal_direction = "SHORT"
            else:
                continue
            
            entry_idx = i + 1
            if entry_idx >= n:
                continue
            
            entry_price = df.loc[entry_idx, "open"]
            slippage = CONFIG["SLIPPAGE_PCT"]
            
            if signal_direction == "LONG":
                entry_price = entry_price * (1 + slippage)
                sl = entry_price - CONFIG["ATR_MULT_SL"] * atr_v
                tps = [entry_price + m * atr_v for m in CONFIG["TP_ATR_MULTS"]]
            else:
                entry_price = entry_price * (1 - slippage)
                sl = entry_price + CONFIG["ATR_MULT_SL"] * atr_v
                tps = [entry_price - m * atr_v for m in CONFIG["TP_ATR_MULTS"]]
            
            result = None
            exit_price = None
            # نکته مهم: در هر کندل ابتدا SL چک می‌شود، سپس TP - یعنی اگر high و low یک کندل
            # هر دو به SL و TP برسند (ابهام برخورد هم‌زمان)، به‌صورت محافظه‌کارانه SL در اولویت است
            for j in range(1, max_hold + 1):
                idx = entry_idx + j
                if idx >= n:
                    break
                
                hi, lo = df.loc[idx, "high"], df.loc[idx, "low"]
                
                if signal_direction == "LONG":
                    if lo <= sl:
                        result = "loss"
                        exit_price = sl * (1 - slippage)
                        break
                    hit_tps = [tp for tp in tps if hi >= tp]
                    if hit_tps:
                        result = "win"
                        exit_price = min(hit_tps)
                        break
                else:
                    if hi >= sl:
                        result = "loss"
                        exit_price = sl * (1 + slippage)
                        break
                    hit_tps = [tp for tp in tps if lo <= tp]
                    if hit_tps:
                        result = "win"
                        exit_price = max(hit_tps)
                        break
            
            if result is None:
                result = "loss"
                exit_price = df.loc[min(entry_idx + max_hold, n - 1), "close"]
            
            if signal_direction == "LONG":
                gross_pct = (exit_price - entry_price) / entry_price * 100
            else:
                gross_pct = (entry_price - exit_price) / entry_price * 100
            net_pct = gross_pct - round_trip_commission_pct
            
            gross_returns.append(gross_pct)
            net_returns.append(net_pct)
            
            if result == "win":
                wins += 1
            else:
                losses += 1
            total += 1
        
        winrate = (wins / total * 100.0) if total > 0 else None
        avg_net_return = float(np.mean(net_returns)) if net_returns else None
        gross_profit = sum(r for r in net_returns if r > 0)
        gross_loss = abs(sum(r for r in net_returns if r < 0))
        net_profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else None)
        return {
            "symbol": symbol, "total": total, "wins": wins, "losses": losses, "winrate": winrate,
            "avg_net_return_pct": avg_net_return, "net_profit_factor": net_profit_factor,
        }
    except Exception as e:
        logger.error(f"خطا در بک‌تست {symbol}: {e}")
        return {"symbol": symbol, "total": 0, "wins": 0, "losses": 0, "winrate": None}

def adaptive_parameters_from_df(df: pd.DataFrame) -> dict:
    """تنظیم پارامترها بر اساس دیتافریم فعلی"""
    try:
        if df is None or df.empty:
            return {"ATR_MULT_SL": CONFIG["ATR_MULT_SL"]}
        
        latest = df.iloc[-1]
        atr_ratio = (latest.get("atr", np.nan) / latest.get("close", np.nan)) if latest.get("atr", np.nan) and latest.get("close", np.nan) else 0.0
        
        if pd.isna(atr_ratio):
            atr_ratio = 0.0
        
        params = {}
        if atr_ratio > CONFIG["VOLATILITY_REGIME_ATR_RATIO"]:
            params["ATR_MULT_SL"] = max(1.6, CONFIG["ATR_MULT_SL"] * 1.25)
        else:
            params["ATR_MULT_SL"] = max(1.0, CONFIG["ATR_MULT_SL"] * 0.9)
        
        return params
    except Exception as e:
        logger.error(f"خطا در تنظیم پارامترهای تطبیقی: {e}")
        return {"ATR_MULT_SL": CONFIG["ATR_MULT_SL"]}


# ============================================================================
# بخش 15: کامپوننت‌های سراسری یادگیری
# ============================================================================

performance_memory = PerformanceMemory(max_size=500, short_term_size=50)
param_optimizer = AdaptiveParameterOptimizer(performance_memory)
weight_learner = FeatureWeightLearner(performance_memory)
pattern_recognizer = PatternRecognizer(performance_memory)
ml_model = MLConfidenceModel(performance_memory)
auto_learning = AutoLearningSystem(performance_memory)
self_healing_autopilot = SelfHealingAutoPilot(performance_memory)


# ===================== ALWAYS-ON SELF DIAGNOSTICS =====================
def self_diagnose_and_repair() -> None:
    """هر دور اجرای ربات، تنظیمات خطرناک/متناقض را خودکار اصلاح می‌کند.
    هدف: هیچ‌وقت به‌خاطر optimizer، regime adjustment یا خراب شدن state،
    گیت سیگنال غیرقابل‌دستیابی نشود.
    """
    try:
        with CONFIG_LOCK:
            min_c = float(CONFIG.get("MIN_CONFIDENCE_SCORE", 6.0))
            max_c = float(CONFIG.get("MAX_EFFECTIVE_CONFIDENCE", 6.4))
            if max_c < 5.9:
                max_c = 5.9
                CONFIG["MAX_EFFECTIVE_CONFIDENCE"] = max_c
            if min_c > max_c:
                CONFIG["MIN_CONFIDENCE_SCORE"] = max_c
            elif min_c < 5.5:
                CONFIG["MIN_CONFIDENCE_SCORE"] = 5.5

            adj = dict(CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}))
            for regime in ("TRENDING", "VOLATILE", "RANGING", "UNKNOWN"):
                v = float(adj.get(regime, 0.0))
                adj[regime] = round(max(0.0, min(0.30, v)), 2)
            CONFIG["REGIME_CONFIDENCE_ADJUSTMENT"] = adj

            if float(CONFIG.get("PUMP_THRESHOLD", 1.8)) < 0.8:
                CONFIG["PUMP_THRESHOLD"] = 0.8
            if float(CONFIG.get("PUMP_THRESHOLD", 1.8)) > 2.5:
                CONFIG["PUMP_THRESHOLD"] = 2.5
            CONFIG["DUMP_THRESHOLD"] = -abs(float(CONFIG["PUMP_THRESHOLD"]))

            # مدل ML هیچ‌وقت مجاز نیست خودش باعث رد همه سیگنال‌ها شود.
            CONFIG["ML_MAX_INFLUENCE"] = min(0.15, max(0.0, float(CONFIG.get("ML_MAX_INFLUENCE", 0.15))))
    except Exception as e:
        logger.error(f"Self-diagnostic failed: {e}")

# ============================================================================
# بخش 16: هسته تحلیل با یادگیری - کامل
# ============================================================================

def calculate_signal_confidence_with_learning(signal_data: dict, current_features: dict) -> float:
    """محاسبه امتیاز اطمینان با استفاده از یادگیری"""
    try:
        score = 0
        
        trend = signal_data.get("trend", "")
        if trend in ["STRONG LONG", "STRONG SHORT"]:
            score += 3
        elif trend in ["LONG", "SHORT"]:
            score += 2
        elif trend == "NEUTRAL":
            score += 1
        
        if signal_data.get("confirmed", False):
            score += 2
        
        if signal_data.get("multi_tf_aligned", False):
            score += 2
        
        pa_signals = signal_data.get("pa_signals", [])
        score += min(len(pa_signals), 3)
        
        backtest = signal_data.get("backtest", {})
        winrate = backtest.get("winrate", 0)
        if winrate and winrate > 60:
            score += 2
        elif winrate and winrate > 50:
            score += 1
        
        if pattern_recognizer.matches_successful_pattern(current_features):
            score += 3
            logger.debug("🎯 تطابق با الگوی موفق گذشته")
        
        if pattern_recognizer.matches_failed_pattern(current_features):
            score -= 4
            logger.debug("⚠️ تطابق با الگوی ناموفق گذشته")
        
        weighted_score = weight_learner.calculate_weighted_confidence(current_features)
        # سهم امتیاز یادگیری‌شده به‌تدریج و متناسب با بلوغ داده افزایش می‌یابد (نه یک نسبت ثابت) -
        # با نمونه‌ی کم عمدتاً به امتیاز قانون‌محور (که همیشه قابل‌اعتماد است) تکیه می‌کند، و فقط با
        # جمع‌شدن داده‌ی کافی سهم امتیاز یادگیری‌شده بیشتر می‌شود
        n_trades = len(performance_memory.trades)
        min_t = CONFIG.get("WEIGHT_SHARPEN_MIN_TRADES", 100)
        full_t = CONFIG.get("WEIGHT_SHARPEN_FULL_TRADES", 300)
        if n_trades < min_t:
            learned_share = 0.25
        elif n_trades >= full_t:
            learned_share = 0.35
        else:
            progress = (n_trades - min_t) / max(1, (full_t - min_t))
            learned_share = 0.25 + progress * (0.35 - 0.25)
        final_score = (score * (1 - learned_share)) + (weighted_score * learned_share)
        
        # ML: مدل بد فقط به‌صورت observe-only باقی می‌ماند. مدل خوب با ramp تدریجی اثر می‌گذارد.
        # علاوه بر AUC، ثبات WF و Brier و جهت/رژیم بررسی می‌شود.
        # اگر مدل ML واقعی آموزش دیده و بالغ کافی است، پیش‌بینی احتمال بردش هم وارد امتیاز نهایی می‌شود -
        # با سهمی که به‌تدریج زیاد می‌شود (get_influence_weight)، دقیقاً همان فلسفه‌ی محافظه‌کارانه
        ml_influence = ml_model.get_influence_weight()
        if ml_influence > 0:
            ml_proba = ml_model.predict_win_probability(current_features)
            if ml_proba is not None:
                ml_score_0_10 = ml_proba * 10.0
                final_score = (final_score * (1 - ml_influence)) + (ml_score_0_10 * ml_influence)
        
        return max(0.0, min(10.0, final_score))
        
    except Exception as e:
        logger.error(f"خطا در محاسبه اطمینان: {e}")
        return 5.0

def enhance_signal_with_learning(signal: dict, df: pd.DataFrame) -> dict:
    """بهبود سیگنال با استفاده از یادگیری"""
    if signal is None:
        return None
    
    try:
        current_features = {
            "trend_alignment": 1.0 if signal.get("confirmed", False) else 0.0,
            "volume_confirmation": 1.0 if signal.get("volume_spike", False) else 0.0,
            "multi_tf_alignment": 1.0 if signal.get("multi_tf_aligned", False) else 0.0,
            "price_action_quality": min(len(signal.get("pa_signals", [])), 3) / 3.0,
            "backtest_winrate": (signal.get("backtest", {}).get("winrate", 0) or 0) / 100.0,
            "rsi_momentum": 0.0,
            "volatility_regime": 0.0,
            "trend_type": signal.get("trend", "NEUTRAL"),
            "volatility": 0.0,
            "volume_ratio": 0.0,
            "rsi": 50,
            "price_action": signal.get("pa_signals", [""])[0] if signal.get("pa_signals") else "",
            "market_regime": signal.get("market_regime", "UNKNOWN"),
            "adx_strength": 0.0,
            "cci_signal": 0.0,
            "williams_signal": 0.0,
            "mfi_signal": 0.0,
            "supertrend_alignment": 0.0,
        }
        
        if df is not None and len(df) > 0:
            if "rsi" in df.columns:
                current_features["rsi"] = float(df["rsi"].iloc[-1]) if not pd.isna(df["rsi"].iloc[-1]) else 50
                current_features["rsi_momentum"] = abs(50 - current_features["rsi"]) / 50.0
            if "atr_ratio" in df.columns:
                current_features["volatility_regime"] = min(1.0, float(df["atr_ratio"].iloc[-1]) / 0.03) if not pd.isna(df["atr_ratio"].iloc[-1]) else 0.5
            if "volume_ratio" in df.columns:
                current_features["volume_ratio"] = min(2.0, float(df["volume_ratio"].iloc[-1])) if not pd.isna(df["volume_ratio"].iloc[-1]) else 1.0
            if "volatility_20" in df.columns:
                current_features["volatility"] = float(df["volatility_20"].iloc[-1]) if not pd.isna(df["volatility_20"].iloc[-1]) else 0.0
            if "adx" in df.columns and not pd.isna(df["adx"].iloc[-1]):
                current_features["adx_strength"] = min(1.0, float(df["adx"].iloc[-1]) / 50.0)
            is_long = "LONG" in str(signal.get("direction", ""))
            if "cci" in df.columns and not pd.isna(df["cci"].iloc[-1]):
                cci_v = float(df["cci"].iloc[-1])
                current_features["cci_signal"] = 1.0 if (cci_v > 0) == is_long else 0.0
            if "williams_r" in df.columns and not pd.isna(df["williams_r"].iloc[-1]):
                wr_v = float(df["williams_r"].iloc[-1])
                current_features["williams_signal"] = 1.0 if (wr_v > -50) == is_long else 0.0
            if "mfi" in df.columns and not pd.isna(df["mfi"].iloc[-1]):
                mfi_v = float(df["mfi"].iloc[-1])
                current_features["mfi_signal"] = 1.0 if (mfi_v > 50) == is_long else 0.0
            if "supertrend_dir" in df.columns and not pd.isna(df["supertrend_dir"].iloc[-1]):
                st_v = float(df["supertrend_dir"].iloc[-1])
                current_features["supertrend_alignment"] = 1.0 if (st_v > 0) == is_long else 0.0
        
        confidence = calculate_signal_confidence_with_learning(signal, current_features)
        signal["confidence"] = confidence
        signal["learning_features"] = current_features
        
        return signal
        
    except Exception as e:
        logger.error(f"خطا در بهبود سیگنال: {e}")
        signal["confidence"] = 5.0
        return signal

def analyze_symbol_full(symbol: str, direction_hint: Optional[str] = None, use_multi_tf: bool = True) -> Optional[dict]:
    """تحلیل کامل یک نماد"""
    try:
        df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=CONFIG["KLINE_LIMIT"])
        if df is None or df.empty or df.shape[0] < CONFIG["BACKTEST_MIN_REQUIRED"]:
            return None
        
        df_features = create_ml_features(df)
        adaptive = adaptive_parameters_from_df(df_features)
        
        df["ema_short"] = ema_pd(df["close"], CONFIG["EMA_SHORT"])
        df["ema_med"] = ema_pd(df["close"], CONFIG["EMA_MED"])
        df["ema_long"] = ema_pd(df["close"], CONFIG["EMA_LONG"])
        df["atr"] = atr_pd(df["high"], df["low"], df["close"], CONFIG["ATR_PERIOD"])
        df["atr_ratio"] = df["atr"] / df["close"].replace(0, np.nan)
        df["rsi"] = rsi_pd(df["close"], CONFIG["RSI_PERIOD"])
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(20, min_periods=1).mean()
        df["volatility_20"] = df["close"].pct_change().rolling(20).std()
        market_regime = detect_market_regime(df)
        
        atr_v = float(df["atr"].iloc[-1]) if not df["atr"].isna().all() else None
        if atr_v is None or atr_v == 0:
            return None
        
        ema_s, ema_m, ema_l = df["ema_short"].iloc[-1], df["ema_med"].iloc[-1], df["ema_long"].iloc[-1]
        if ema_s > ema_m > ema_l:
            trend = "STRONG LONG"
        elif ema_s > ema_m:
            trend = "LONG"
        elif ema_s < ema_m < ema_l:
            trend = "STRONG SHORT"
        elif ema_s < ema_m:
            trend = "SHORT"
        else:
            trend = "NEUTRAL"
        
        hint, price = (direction_hint or "").lower().strip(), float(df["close"].iloc[-1])
        
        if hint.startswith("bull") or hint == "bull":
            signal_direction, is_warning = "LONG", trend not in ["LONG", "STRONG LONG"]
        elif hint.startswith("bear") or hint == "bear":
            signal_direction, is_warning = "SHORT", trend not in ["SHORT", "STRONG SHORT"]
        else:
            if trend in ["LONG", "STRONG LONG"]:
                signal_direction, is_warning = "LONG", False
            elif trend in ["SHORT", "STRONG SHORT"]:
                signal_direction, is_warning = "SHORT", False
            else:
                return None
        
        atr_mult = adaptive.get("ATR_MULT_SL", CONFIG["ATR_MULT_SL"])
        
        if signal_direction == "LONG":
            entry = price
            sl = round(price - atr_mult * atr_v, 8)
            tps = [round(price + m * atr_v, 8) for m in CONFIG["TP_ATR_MULTS"]]
            direction_text = "LONG" + (" ⚠️" if is_warning else "")
        else:
            entry = price
            sl = round(price + atr_mult * atr_v, 8)
            tps = [round(price - m * atr_v, 8) for m in CONFIG["TP_ATR_MULTS"]]
            direction_text = "SHORT" + (" ⚠️" if is_warning else "")
        
        conf = compute_confirmation_signals(df, require_volume=True)
        long_conf = conf["long_confirm"].iloc[-1] if len(conf) > 0 else False
        short_conf = conf["short_confirm"].iloc[-1] if len(conf) > 0 else False
        confirmed = (signal_direction == "LONG" and bool(long_conf)) or (signal_direction == "SHORT" and bool(short_conf))
        volume_spike = bool(df["volume_ratio"].iloc[-1] > 1.2) if "volume_ratio" in df.columns else False
        # اندیکاتورهای تکمیلی برای ثبت در سیگنال و استفاده در یادگیری (از خروجی compute_confirmation_signals)
        df["adx"] = conf["adx"]
        df["cci"] = conf["cci"]
        df["williams_r"] = conf["williams_r"]
        df["mfi"] = conf["mfi"]
        df["supertrend_dir"] = conf["supertrend_dir"]
        
        mtf_ok = True
        if use_multi_tf:
            try:
                higher_int = "4h" if CONFIG["KLINE_INTERVAL"].endswith("m") else "1d"
                df_higher = fetch_klines_df(symbol, interval=higher_int, limit=200)
                if df_higher is not None:
                    hema_s = ema_pd(df_higher["close"], CONFIG["EMA_SHORT"]).iloc[-1]
                    hema_m = ema_pd(df_higher["close"], CONFIG["EMA_MED"]).iloc[-1]
                    if signal_direction == "LONG" and not (hema_s > hema_m):
                        mtf_ok = False
                    if signal_direction == "SHORT" and not (hema_s < hema_m):
                        mtf_ok = False
            except Exception as e:
                logger.debug(f"خطا در MTF {symbol}: {e}")
                mtf_ok = True
        
        pa_signals = detect_price_action_signals(df)
        swings = find_swing_levels_pd(df)
        breakout = None
        backtest_res = backtest_symbol_realistic(symbol)
        
        with CONFIG_LOCK:
            params_used_snapshot = {
                "ATR_MULT_SL": CONFIG["ATR_MULT_SL"],
                "EMA_SHORT": CONFIG["EMA_SHORT"],
                "EMA_MED": CONFIG["EMA_MED"]
            }
        
        signal = {
            "symbol": symbol.upper(),
            "price": price,
            "direction": direction_text,
            "entry": entry,
            "sl": sl,
            "tps": tps,
            "trend": trend,
            "atr": atr_v,
            "atr_mult_used": atr_mult,
            "swings": swings,
            "breakout": breakout,
            "pa_signals": pa_signals,
            "confirmed": confirmed,
            "volume_spike": volume_spike,
            "multi_tf_ok": mtf_ok,
            "multi_tf_aligned": mtf_ok,
            "market_regime": market_regime,
            "indicators": {
                "adx": float(df["adx"].iloc[-1]) if not pd.isna(df["adx"].iloc[-1]) else None,
                "cci": float(df["cci"].iloc[-1]) if not pd.isna(df["cci"].iloc[-1]) else None,
                "williams_r": float(df["williams_r"].iloc[-1]) if not pd.isna(df["williams_r"].iloc[-1]) else None,
                "mfi": float(df["mfi"].iloc[-1]) if not pd.isna(df["mfi"].iloc[-1]) else None,
                "supertrend_dir": int(df["supertrend_dir"].iloc[-1]) if not pd.isna(df["supertrend_dir"].iloc[-1]) else None,
            },
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            # timestamp دقیق کندلی که سیگنال رویش صادر شده - برای اینکه خودآموزی بعداً دقیقاً
            # همون لحظه به بعد رو بررسی کند، نه یک بازه‌ی تقریبی بر اساس زمان پردازش
            "signal_candle_ts": df.index[-1].timestamp(),
            "backtest": backtest_res,
            "features_snapshot": df_features.iloc[-5:].tail(1).to_dict("records")[0] if not df_features.empty else {},
            "params_used": params_used_snapshot
        }
        
        signal = enhance_signal_with_learning(signal, df)
        return signal
        
    except Exception as e:
        logger.error(f"خطا در تحلیل {symbol}: {e}")
        return None

def enhanced_analysis(symbol: str, direction_hint: Optional[str] = None, recovery_mode: bool = False) -> Optional[dict]:
    """تحلیل پیشرفته با فیلترهای کیفیت"""
    try:
        df = fetch_klines_df(symbol, interval=CONFIG["KLINE_INTERVAL"], limit=CONFIG["KLINE_LIMIT"])
        if df is None or df.empty or df.shape[0] < CONFIG["BACKTEST_MIN_REQUIRED"]:
            return None
        
        if not symbol_quality_check(symbol):
            logger.debug(f"{symbol}: رد شد (کیفیت)")
            return None
        
        if not volatility_filter(df):
            logger.debug(f"{symbol}: رد شد (نوسان)")
            return None
        
        swing_levels = find_swing_levels_pd(df)
        if detect_false_breakout(df, swing_levels):
            logger.debug(f"{symbol}: رد شد (شکست فیک)")
            return None
        
        # atr باید قبل از تشخیص رژیم بازار محاسبه شود، وگرنه atr_ratio همیشه صفر
        # و حالت VOLATILE هرگز شناسایی نمی‌شود
        df_regime = df.copy()
        df_regime["atr"] = atr_pd(df_regime["high"], df_regime["low"], df_regime["close"], CONFIG["ATR_PERIOD"])
        regime = detect_market_regime(df_regime)
        if regime == "RANGING":
            logger.debug(f"{symbol}: رد شد (بازار رنج)")
            return None
        
        signal = analyze_symbol_full(symbol, direction_hint)
        
        # آستانه‌ی اطمینان بر اساس رژیم بازار تنظیم می‌شود - داده‌ی واقعی نشان داد رژیم VOLATILE
        # با اختلاف زیاد ضعیف‌ترین وین‌ریت را دارد ولی بیشترین سهم معاملات را هم به خودش اختصاص می‌دهد،
        # پس باید سخت‌گیرانه‌تر فیلتر شود، نه رد کامل (شاید بعضی سیگنال‌های خیلی قوی هنوز ارزش داشته باشند)
        hard_cap = float(CONFIG.get("MAX_EFFECTIVE_CONFIDENCE", 6.4))
        min_confidence = min(hard_cap,
                             float(CONFIG.get("MIN_CONFIDENCE_SCORE", 6.0)) +
                             float(CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT", {}).get(regime, 0)))
        if recovery_mode:
            # Recovery فقط گیت امتیاز را کمی باز می‌کند؛ کیفیت بازار، حجم، شکست فیک،
            # MTF و emergency gate همچنان فعال می‌مانند.
            min_confidence = min(min_confidence, float(CONFIG.get("FALLBACK_MIN_CONFIDENCE", 5.9)))
        # Self-healing signal recovery: if the scanner has been starved, relax
        # the confidence gate gradually, but never below the hard safety floor.
        idle_min = max(0.0, (time.time() - _LAST_ACCEPTED_SIGNAL_TS) / 60.0)
        starvation_start = float(CONFIG.get("SIGNAL_STARVATION_MINUTES", 20))
        if idle_min >= starvation_start:
            recovery_steps = int((idle_min - starvation_start) // 20) + 1
            recovery = min(0.70, recovery_steps * 0.15)
            min_confidence = max(5.75, min_confidence - recovery)
            min_confidence = min(min_confidence, float(CONFIG.get("MAX_EFFECTIVE_CONFIDENCE", 6.4)))
        
        # ثبت آماری - چند سیگنال از هر رژیم ارزیابی و چند تا واقعاً قبول شدند (برای گزارش ساعتی،
        # تا بشود فهمید یک رژیم اصلاً سیگنال تولید نمی‌کند یا فقط رد صلاحیت می‌شود)
        _REGIME_GATE_STATS["evaluated"][regime] = _REGIME_GATE_STATS["evaluated"].get(regime, 0) + 1
        
        if signal and signal.get("confidence", 0) >= min_confidence:
            _REGIME_GATE_STATS["passed"][regime] = _REGIME_GATE_STATS["passed"].get(regime, 0) + 1
            return signal
        
        return None
        
    except Exception as e:
        logger.error(f"خطا در enhanced_analysis {symbol}: {e}")
        return None


# ============================================================================
# بخش 17: توابع ذخیره‌سازی و گزارش
# ============================================================================

def create_ml_features(df: pd.DataFrame) -> pd.DataFrame:
    """ساخت ویژگی‌های ML از داده‌های OHLCV"""
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        
        df = df.copy()
        features = pd.DataFrame(index=df.index)
        
        features["price"] = df["close"]
        
        for period in [1, 5, 10]:
            features[f"returns_{period}"] = df["close"].pct_change(period)
        
        for period in [5, 10, 20]:
            features[f"volatility_{period}"] = df["close"].pct_change().rolling(period).std()
        
        vol_sma_20 = df["volume"].rolling(20, min_periods=1).mean()
        features["volume_ratio"] = df["volume"] / vol_sma_20.replace(0, np.nan)
        
        for period in [7, 14, 21]:
            features[f"rsi_{period}"] = rsi_pd(df["close"], period)
        
        macd, macd_signal, macd_hist = macd_pd(df["close"])
        features["macd"] = macd
        features["macd_signal"] = macd_signal
        features["macd_hist"] = macd_hist
        
        features["ema_short"] = ema_pd(df["close"], CONFIG["EMA_SHORT"])
        features["ema_long"] = ema_pd(df["close"], CONFIG["EMA_LONG"])
        features["ema_ratio"] = features["ema_short"] / features["ema_long"].replace(0, np.nan)
        
        features["atr"] = atr_pd(df["high"], df["low"], df["close"], CONFIG["ATR_PERIOD"])
        features["atr_ratio"] = features["atr"] / df["close"].replace(0, np.nan)
        
        bb_upper, _, bb_lower = bollinger_pd(df["close"])
        features["bb_position"] = (df["close"] - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
        
        k, d = stochastic_pd(df["high"], df["low"], df["close"])
        features["stoch_k"] = k
        features["stoch_d"] = d
        
        features["adx"] = adx_pd(df["high"], df["low"], df["close"])

        features["cci"] = cci_pd(df["high"], df["low"], df["close"], CONFIG.get("CCI_PERIOD", 20))
        features["williams_r"] = williams_r_pd(df["high"], df["low"], df["close"], CONFIG.get("WILLIAMS_R_PERIOD", 14))
        features["mfi"] = mfi_pd(df["high"], df["low"], df["close"], df["volume"], CONFIG.get("MFI_PERIOD", 14))
        obv = obv_pd(df["close"], df["volume"])
        features["obv_slope"] = obv.diff(5) / df["volume"].rolling(5, min_periods=1).mean().replace(0, np.nan)
        _, st_dir = supertrend_pd(df["high"], df["low"], df["close"],
                                   CONFIG.get("SUPERTREND_PERIOD", 10), CONFIG.get("SUPERTREND_MULT", 3.0))
        features["supertrend_dir"] = st_dir
        features["vwap_dist"] = (df["close"] - vwap_pd(df["high"], df["low"], df["close"], df["volume"])) / df["close"].replace(0, np.nan)
        
        features["body_size"] = (df["close"] - df["open"]).abs()
        features["total_range"] = df["high"] - df["low"]
        features["body_ratio"] = features["body_size"] / features["total_range"].replace(0, np.nan)
        
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.ffill().bfill().fillna(0)
        
        return features
        
    except Exception as e:
        logger.error(f"خطا در ساخت ویژگی‌های ML: {e}")
        return pd.DataFrame()

def save_signal_json_overwrite(signals: List[dict]) -> None:
    save_json_file(PATHS["FINAL_SIGNAL_FILE"], signals)

def save_signal_history(signal: Dict[str, Any]) -> None:
    try:
        history = load_json_file(PATHS["SIGNAL_HISTORY_FILE"]) or []
        if not isinstance(history, list):
            history = []
        
        signal["ts"] = int(time.time())
        history.append(signal)
        
        if len(history) > 100:
            history = history[-100:]
        
        save_json_file(PATHS["SIGNAL_HISTORY_FILE"], history)
    except Exception as e:
        logger.error(f"خطا در ذخیره تاریخچه سیگنال: {e}")

def update_learning_system() -> None:
    """به‌روزرسانی کامل سیستم یادگیری"""
    logger.info("\n🔄 شروع به‌روزرسانی سیستم یادگیری...")
    
    param_optimizer.optimize()
    param_optimizer.apply_optimized_params()
    weight_learner.update_weights()
    pattern_recognizer.learn_patterns()
    ml_model.train(force=True)  # بازآموزی کامل مدل ML هر 24 ساعت، صرف‌نظر از فاصله‌ی معمول
    param_optimizer.optimize_regime_thresholds()
    
    summary = performance_memory.get_summary()
    logger.info(f"✅ خلاصه عملکرد: {summary['total_trades']} معامله, وین‌ریت: {summary['long_term_winrate']:.1f}%")
    logger.info("✅ سیستم یادگیری به‌روزرسانی شد\n")


# نگهداری آخرین وزن‌های فیچر که گزارش شده‌اند - برای نمایش میزان تغییر در هر گزارش ساعتی
_LAST_REPORTED_WEIGHTS: Dict[str, float] = {}

# شمارنده‌ی سیگنال‌های ارزیابی‌شده در برابر رد/قبول‌شده، به‌ازای هر رژیم بازار - از آخرین گزارش ساعتی.
# برای تشخیص اینکه آیا یک رژیم خاص (مثلاً VOLATILE) اصلاً سیگنال تولید نمی‌کند یا فقط رد صلاحیت می‌شود
_REGIME_GATE_STATS: Dict[str, Dict[str, int]] = {"evaluated": {}, "passed": {}}


# وضعیت گزارش برای مقایسه دقیق «این ساعت با ساعت قبل»
_REPORT_STATE = {
    "time": None,
    "config": None,
    "trades": 0,
    "errors": 0,
    "warnings": 0,
    "gate": {"evaluated": {}, "passed": {}},
}


def _fmt(v, digits=2, default="-"):
    try:
        if v is None:
            return default
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def _metric_block(trades):
    """محاسبه‌ی متریک‌های مستقل برای گزارش؛ به حافظه‌ی داخلی متکی نیست."""
    tr = list(trades or [])
    n = len(tr)
    if not n:
        return {"n": 0, "wins": 0, "losses": 0, "wr": 0.0, "pf": 0.0,
                "avg": 0.0, "expectancy": 0.0, "gross_profit": 0.0,
                "gross_loss": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "max_dd": 0.0}
    vals = []
    for t in tr:
        try: vals.append(float(t.get("return_pct", 0.0)))
        except Exception: vals.append(0.0)
    wins = sum(1 for t in tr if bool(t.get("win")))
    losses = n - wins
    gp = sum(x for x in vals if x > 0)
    gl = abs(sum(x for x in vals if x < 0))
    eq = 0.0; peak = 0.0; max_dd = 0.0
    for x in vals:
        eq += x; peak = max(peak, eq); max_dd = max(max_dd, peak-eq)
    return {
        "n": n, "wins": wins, "losses": losses,
        "wr": wins/n*100.0, "pf": gp/gl if gl > 1e-12 else (99.0 if gp > 0 else 0.0),
        "avg": float(np.mean(vals)), "expectancy": float(np.mean(vals)),
        "gross_profit": gp, "gross_loss": gl,
        "avg_win": gp/wins if wins else 0.0,
        "avg_loss": gl/losses if losses else 0.0,
        "max_dd": max_dd,
    }


def _config_snapshot():
    """فقط پارامترهای قابل‌تغییر استراتژی را برای گزارش و مقایسه نگه می‌دارد."""
    keys = [
        "PUMP_THRESHOLD","DUMP_THRESHOLD","MIN_CONFIDENCE_SCORE","ATR_MULT_SL",
        "EMA_SHORT","EMA_MED","EMA_LONG","RSI_PERIOD","ATR_PERIOD","RISK_PERCENT",
        "MAX_NEW_SIGNALS_PER_CYCLE","MAX_NEW_SIGNALS_PER_HOUR","MAX_EFFECTIVE_CONFIDENCE",
        "FALLBACK_MIN_CONFIDENCE","FALLBACK_SCAN_AFTER_MINUTES","MAX_PENDING_PER_SYMBOL",
        "SYMBOL_COOLDOWN_SEC","MAX_CONSECUTIVE_LOSSES","COOLDOWN_AFTER_LOSS",
        "REQUIRE_VOLUME_SPIKE","MIN_VOLUME_RATIO","MAX_SPREAD_PCT","BACKTEST_MAX_HOLD",
        "MAX_HOLD_MINUTES","AUTO_LEARN_PATH_BASED","LEARNING_RATE","LEARNING_WINDOW",
        "ML_MAX_INFLUENCE","ML_PROVISIONAL_INFLUENCE","ML_MIN_AUC_FOR_INFLUENCE",
        "ML_MIN_WF_AUC","ML_MAX_WF_AUC_STD","ML_REQUIRE_BRIER_MAX",
        "REGIME_CONFIDENCE_ADJUSTMENT","REGIME_MAX_ADJUSTMENT","REGIME_ADJUSTMENT_STEP",
    ]
    out={}
    for k in keys:
        if k in CONFIG:
            v=CONFIG[k]
            out[k]=dict(v) if isinstance(v,dict) else list(v) if isinstance(v,list) else v
    return out


def _changed_config_lines(old, new):
    if not old:
        return []
    out=[]
    for k in sorted(set(old)|set(new)):
        a=old.get(k); b=new.get(k)
        if a == b:
            continue
        if isinstance(a,dict) and isinstance(b,dict):
            sub=[]
            for sk in sorted(set(a)|set(b)):
                if a.get(sk)!=b.get(sk): sub.append(f"{sk}: {a.get(sk)}→{b.get(sk)}")
            if sub: out.append(f"{k}: " + "; ".join(sub))
        else:
            out.append(f"{k}: {a} → {b}")
    return out


def build_learning_report(price_map: Dict[str, float]) -> str:
    """گزارش تشخیصی کامل: عملکرد، کیفیت سیگنال، یادگیری، تغییرات، سلامت و خطاها."""
    global _LAST_REPORTED_WEIGHTS, _REPORT_STATE, _REGIME_GATE_STATS
    try:
        trades=list(performance_memory.trades)
        all_m=_metric_block(trades)
        r20=_metric_block(trades[-20:]); r50=_metric_block(trades[-50:]); r100=_metric_block(trades[-100:])
        pending=auto_learning.get_pending_status(price_map)
        cfg=_config_snapshot()
        old_cfg=_REPORT_STATE.get("config")
        changed=_changed_config_lines(old_cfg,cfg)
        old_trades=int(_REPORT_STATE.get("trades") or 0)
        old_errors=int(_REPORT_STATE.get("errors") or 0)
        old_warnings=int(_REPORT_STATE.get("warnings") or 0)
        new_trades=max(0,len(trades)-old_trades)
        err_report=logger.get_report()
        errors_now=err_report["total_errors"]; warnings_now=err_report["total_warnings"]
        new_errors=max(0,errors_now-old_errors); new_warnings=max(0,warnings_now-old_warnings)

        lines=["="*60,"🧠 گزارش جامع خودآموزی و سلامت ربات","⏰ "+time.strftime('%Y-%m-%d %H:%M:%S'),"="*60]
        if not auto_learning.is_healthy():
            lines += ["","🔴 وضعیت بحرانی: ترد پردازش صف یادگیری سالم نیست."]

        lines += ["","📊 1) عملکرد واقعی"]
        lines += [f"  • کل: {all_m['n']} معامله | برد {all_m['wins']} | باخت {all_m['losses']} | WR {all_m['wr']:.1f}% | PF {all_m['pf']:.2f} | Expectancy {all_m['expectancy']:.3f}% | MaxDD تجمعی {all_m['max_dd']:.2f}%"]
        lines += [f"  • 20 اخیر: {r20['n']} | WR {r20['wr']:.1f}% | PF {r20['pf']:.2f} | Exp {r20['expectancy']:.3f}%"]
        lines += [f"  • 50 اخیر: {r50['n']} | WR {r50['wr']:.1f}% | PF {r50['pf']:.2f} | Exp {r50['expectancy']:.3f}%"]
        lines += [f"  • 100 اخیر: {r100['n']} | WR {r100['wr']:.1f}% | PF {r100['pf']:.2f} | Exp {r100['expectancy']:.3f}%"]
        lines += [f"  • این ساعت: +{new_trades} معامله جدید"]

        diagnosis=[]
        if all_m['pf'] < 1.0: diagnosis.append("PF زیر 1 → استراتژی فعلاً سودده نیست")
        if r50['n']>=20 and r50['wr'] < all_m['wr']-5: diagnosis.append("افت WR اخیر → کیفیت سیگنال‌های جدید ضعیف‌تر شده")
        if r50['n']>=20 and r50['pf'] < 1.0: diagnosis.append("PF اخیر زیر 1 → تغییرات فعلی هنوز جواب نداده‌اند")
        if pending.get('total_pending',0)>max(20,all_m['n']*0.08): diagnosis.append("صف بزرگ است → سرعت نهایی‌شدن معاملات کم است")
        if diagnosis:
            lines += ["  🚨 تشخیص:"] + ["     • "+x for x in diagnosis]
        else:
            lines.append("  ✅ افت بحرانی از روی داده فعلی شناسایی نشد")

        lines += ["","🎯 2) جریان سیگنال و گیت"]
        ev=_REGIME_GATE_STATS.get("evaluated",{}); ps=_REGIME_GATE_STATS.get("passed",{})
        if ev:
            for reg in sorted(ev):
                e=ev.get(reg,0); p=ps.get(reg,0); rate=(p/e*100) if e else 0
                lines.append(f"  • {reg}: {p}/{e} قبول = {rate:.1f}%")
        else:
            lines.append("  • در این ساعت سیگنال گیت‌شده‌ای ثبت نشده")
        lines.append(f"  • حداقل امتیاز: {CONFIG.get('MIN_CONFIDENCE_SCORE')} | سقف مؤثر: {CONFIG.get('MAX_EFFECTIVE_CONFIDENCE')}")
        lines.append(f"  • Pump/Dump: {CONFIG.get('PUMP_THRESHOLD')}% / {CONFIG.get('DUMP_THRESHOLD')}%")
        lines.append(f"  • سقف سیگنال: {CONFIG.get('MAX_NEW_SIGNALS_PER_CYCLE')}/چرخه | {CONFIG.get('MAX_NEW_SIGNALS_PER_HOUR')}/ساعت")

        lines += ["","🌐 3) رژیم بازار"]
        regimes=performance_memory.get_summary().get("market_regimes",{})
        adj=CONFIG.get("REGIME_CONFIDENCE_ADJUSTMENT",{})
        for reg,st in sorted(regimes.items()):
            base=float(CONFIG.get('MIN_CONFIDENCE_SCORE',0)); a=float(adj.get(reg,0) or 0)
            eff=min(float(CONFIG.get('MAX_EFFECTIVE_CONFIDENCE',99)),base+a)
            lines.append(f"  • {reg}: {st.get('wins',0)}/{st.get('total',0)} | WR {st.get('winrate',0):.1f}% | adjustment {a:.2f} | threshold {eff:.2f}")

        lines += ["","🧠 4) ML AutoPilot"]
        if SKLEARN_AVAILABLE and ml_model.is_trained:
            infl=ml_model.get_influence_weight()*100
            lines += [f"  • مدل: {ml_model.selected_model_name or '-'} | health: {getattr(ml_model,'health','UNKNOWN')} | influence: {infl:.1f}%",
                      f"  • Train: {ml_model.trained_on_n_trades} | WF AUC: {_fmt(ml_model.wf_auc_mean,3)} ± {_fmt(ml_model.wf_auc_std,3)} | folds: {ml_model.wf_folds}",
                      f"  • Holdout AUC: {_fmt(ml_model.last_test_auc,3)} | Accuracy: {_fmt(ml_model.last_test_accuracy,3)} | Brier: {_fmt(ml_model.last_brier,3)}"]
            if infl==0: lines.append("  • ML فعلاً وارد امتیاز نهایی نمی‌شود؛ علت را در health/AUC/Brier بالا بررسی کنید.")
        else:
            lines.append("  • ML فعال/آموزش‌دیده نیست")

        lines += ["","⚖️ 5) وزن فیچرها و دلیل تغییر"]
        for feat,w in sorted(weight_learner.feature_weights.items(),key=lambda x:-x[1]):
            prev=_LAST_REPORTED_WEIGHTS.get(feat,w); delta=w-prev
            corr=performance_memory.get_feature_correlation(feat,window=CONFIG.get('LEARNING_WINDOW',100))
            arrow='📈' if delta>0.005 else '📉' if delta<-0.005 else '➖'
            lines.append(f"  {arrow} {feat}: {w:.3f} | Δ {delta:+.3f} | corr_recent {corr:+.3f}")
        _LAST_REPORTED_WEIGHTS=weight_learner.feature_weights.copy()

        lines += ["","🔧 6) تغییرات خودکار از گزارش قبل"]
        if changed:
            for ch in changed: lines.append("  • "+ch)
        else:
            lines.append("  • هیچ پارامتر اصلی بین دو گزارش تغییر نکرده است")
        # تغییرات نامعتبر مثل '?' هرگز به عنوان تغییر معتبر پذیرفته نمی‌شوند.
        bad_keys=[k for k in cfg if not isinstance(k,str) or not k or '?' in k]
        lines.append(f"  • سلامت نام‌گذاری پارامترها: {'❌ نامعتبر' if bad_keys else '✅ سالم'}")

        lines += ["","⚙️ 7) تنظیمات فعلی مهم"]
        for k in ["MIN_CONFIDENCE_SCORE","MAX_EFFECTIVE_CONFIDENCE","PUMP_THRESHOLD","DUMP_THRESHOLD","ATR_MULT_SL","RISK_PERCENT","MAX_HOLD_MINUTES","MAX_NEW_SIGNALS_PER_CYCLE","MAX_NEW_SIGNALS_PER_HOUR","MAX_PENDING_PER_SYMBOL","REQUIRE_VOLUME_SPIKE","MIN_VOLUME_RATIO","LEARNING_WINDOW","LEARNING_RATE"]:
            lines.append(f"  • {k}: {CONFIG.get(k)}")
        lines.append(f"  • REGIME_ADJUSTMENT: {CONFIG.get('REGIME_CONFIDENCE_ADJUSTMENT',{})}")

        lines += ["","⏱️ 8) کیفیت ورود و خروج"]
        timing=performance_memory.get_entry_timing_stats()
        if timing.get('available'):
            lines += [f"  • Pre-signal move: {timing.get('avg_pre_signal_move_pct',0):.2f}% | TP1: {timing.get('tp1_hit_rate_pct',0):.1f}% | SL: {timing.get('sl_hit_rate_pct',0):.1f}%",
                      f"  • زمان نتیجه: {_fmt(timing.get('avg_time_to_result_min'),1)} دقیقه | MFE بازنده: {_fmt(timing.get('avg_mfe_on_losses_pct'),2)}%"]
        else: lines.append(f"  • داده کافی نیست: {timing.get('sample_size',0)}/5")

        lines += ["","🧩 9) الگوها"]
        lines.append(f"  • موفق: {len(pattern_recognizer.successful_patterns)} | ناموفق: {len(pattern_recognizer.failed_patterns)}")

        lines += ["","⏳ 10) صف یادگیری"]
        lines += [f"  • کل: {pending.get('total_pending',0)} | TP1: {pending.get('tp1_hit',0)} | SL: {pending.get('sl_hit',0)} | باز: {pending.get('still_open',0)} | نامشخص: {pending.get('unknown',0)}"]
        if pending.get('regime_counts'):
            lines.append("  • رژیم‌ها: "+", ".join(f"{k}: {v}" for k,v in sorted(pending['regime_counts'].items())))
        for it in pending.get('items',[])[:12]:
            lines.append(f"     {'✅' if it.get('status')=='TP1_HIT' else '❌' if it.get('status')=='SL_HIT' else '⏳'} {it.get('symbol')} {it.get('direction')} [{it.get('regime','?')}] - {it.get('elapsed_min')}m")

        lines += ["","🛡️ 11) سلامت سیستم"]
        lines += [f"  • خطاهای جدید از گزارش قبل: {new_errors} | هشدارهای جدید: {new_warnings}",
                  f"  • خطاهای کل: {errors_now} | هشدارهای کل: {warnings_now}",
                  f"  • آخرین خطا: {(err_report.get('last_error') or {}).get('message','ندارد')}",
                  f"  • آخرین هشدار: {(err_report.get('last_warning') or {}).get('message','ندارد')}"]

        lines += ["","📌 12) نتیجه قابل اقدام"]
        if all_m['pf']<1:
            lines.append("  🔴 فعلاً سوددهی تأیید نشده؛ تغییرات بعدی باید با PF/Expectancy و OOS ارزیابی شوند، نه فقط WR.")
        elif r50['pf']>=1.05 and r50['wr']>=all_m['wr']:
            lines.append("  🟢 عملکرد اخیر بهتر است؛ سیستم فعلاً در مسیر مناسب است و تغییرات شدید نباید اعمال شود.")
        else:
            lines.append("  🟡 وضعیت میانی؛ داده بیشتری لازم است تا تغییر جدید با اطمینان پذیرفته شود.")
        lines.append("="*60)

        # وضعیت گزارش بعدی
        _REPORT_STATE={"time":time.time(),"config":cfg,"trades":len(trades),"errors":errors_now,"warnings":warnings_now,
                       "gate":{"evaluated":dict(ev),"passed":dict(ps)}}
        _REGIME_GATE_STATS["evaluated"]={}; _REGIME_GATE_STATS["passed"]={}
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"خطا در ساخت گزارش جامع: {e}")
        return f"⚠️ خطا در ساخت گزارش جامع: {e}"


# ============================================================================
# بخش 18: حلقه اصلی (Main Loop) - کامل
# ============================================================================

_LAST_ACCEPTED_SIGNAL_TS = time.time()

def get_adaptive_trigger_thresholds() -> tuple:
    """ضد قفل سیگنال: اگر مدت زیادی هیچ سیگنالی قبول نشده باشد، فقط Trigger پامپ/دامپ را
    تدریجی پایین می‌آورد؛ فیلترهای کیفیت و حداقل اطمینان همچنان فعال می‌مانند."""
    try:
        idle_min = (time.time() - _LAST_ACCEPTED_SIGNAL_TS) / 60.0
        base = float(CONFIG.get("PUMP_THRESHOLD", 1.8))
        if idle_min >= CONFIG.get("SIGNAL_STARVATION_MINUTES", 20):
            steps = int((idle_min - CONFIG.get("SIGNAL_STARVATION_MINUTES", 20)) // 30) + 1
            base -= steps * CONFIG.get("SIGNAL_STARVATION_RECOVERY_STEP", 0.15)
            base = max(CONFIG.get("SIGNAL_STARVATION_THRESHOLD_MIN", 1.4), base)
        base = min(CONFIG.get("SIGNAL_STARVATION_THRESHOLD_MAX", 1.9), base)
        return base, -base
    except Exception:
        return float(CONFIG.get("PUMP_THRESHOLD", 1.8)), float(CONFIG.get("DUMP_THRESHOLD", -1.8))

def main_loop():
    """حلقه اصلی برنامه"""
    logger.info(f"شروع حلقه اصلی | اینتروال: {CONFIG['KLINE_INTERVAL']}")
    logger.info(f"آستانه پامپ: {CONFIG['PUMP_THRESHOLD']}% | دامپ: {CONFIG['DUMP_THRESHOLD']}%")
    logger.info(f"حداقل امتیاز اطمینان: {CONFIG['MIN_CONFIDENCE_SCORE']}")
    logger.info(f"🧠 ML AutoPilot: provisional_weight={CONFIG.get('ML_PROVISIONAL_INFLUENCE',0.05):.2f} | max_influence={CONFIG.get('ML_MAX_INFLUENCE',0.15):.2f}")
    logger.info(f"🛟 Signal recovery: starts={CONFIG.get('SIGNAL_STARVATION_MINUTES',20)}m | max_conf={CONFIG.get('MAX_EFFECTIVE_CONFIDENCE',6.7)}")
    
    last_learning_update = 0
    last_report_time = 0.0
    auto_learning.start()
    self_healing_autopilot.run(force=True)
    self_diagnose_and_repair()
    check_count = 0
    signal_count = 0
    
    while True:
        try:
            check_count += 1
            self_diagnose_and_repair()
            logger.debug(f"--- چک شماره {check_count} ---")
            
            # دریافت تیکرها
            coins = fetch_binance_all_ticker()
            if not coins:
                logger.warning("هیچ تیکری دریافت نشد! ممکن است VPN نیاز باشد.")
                time.sleep(30)
                continue
            
            logger.debug(f"{len(coins)} تیکر دریافت شد")
            
            history = load_history()
            update_history_with_coins(history, coins)
            
            # نگاشت نماد->قیمت لحظه‌ای، برای گزارش ساعتی (بدون درخواست شبکه اضافه)
            price_map = {c.get("symbol"): c.get("current_price") for c in coins if c.get("symbol")}
            
            # خواندن یک نسخه ثابت از آستانه‌های CONFIG برای کل این دور چک - تا اگر ترد یادگیری
            # هم‌زمان CONFIG را تغییر دهد، تصمیم‌های این دور با مقادیر ناهماهنگ گرفته نشوند
            with CONFIG_LOCK:
                min_confidence = CONFIG["MIN_CONFIDENCE_SCORE"]
            pump_threshold, dump_threshold = get_adaptive_trigger_thresholds()
            logger.info(f"🎯 Trigger تطبیقی این دور: پامپ ≥ {pump_threshold:.2f}% | دامپ ≤ {dump_threshold:.2f}%")
            
            signals = []
            pump_count = 0
            dump_count = 0
            
            for coin in coins:
                symbol = coin.get("symbol", "").upper()
                if not symbol.endswith("USDT"):
                    continue
                
                change_15m = get_change_from_history(history, symbol, 900)
                if change_15m is None:
                    continue
                
                if abs(change_15m) > 0.1:
                    logger.debug(f"📊 {symbol}: تغییر 15 دقیقه = {change_15m:.2f}%")
                
                direction_hint = None
                if change_15m >= pump_threshold:
                    direction_hint = "bull"
                    pump_count += 1
                    logger.info(f"🚀 پامپ در {symbol}: {change_15m:.2f}%")
                elif change_15m <= dump_threshold:
                    direction_hint = "bear"
                    dump_count += 1
                    logger.info(f"📉 دامپ در {symbol}: {change_15m:.2f}%")
                else:
                    continue
                
                allowed, block_reason = self_healing_autopilot.emergency_gate(symbol, "LONG" if direction_hint == "bull" else "SHORT")
                if not allowed:
                    logger.debug(f"🛡️ AutoPilot blocked {symbol}: {block_reason}")
                    continue
                if len(signals) >= CONFIG.get("MAX_NEW_SIGNALS_PER_CYCLE", 8):
                    continue
                summary = enhanced_analysis(symbol, direction_hint=direction_hint)
                if summary:
                    # ثبت دقیق «چقدر از حرکت قبل از سیگنال انجام شده» - برای اندازه‌گیری کیفیت زمان‌بندی ورود
                    summary["pre_signal_change_15m"] = change_15m
                    signals.append(summary)
                    globals()["_LAST_ACCEPTED_SIGNAL_TS"] = time.time()
                    save_signal_history(summary)
                    auto_learning.add_signal_for_learning(summary)
                    signal_count += 1
                    
                    # نمایش سیگنال در کنسول
                    print(f"\n{'='*50}")
                    print(f"🎯 سیگنال #{signal_count} پیدا شد!")
                    print(f"   نماد: {summary['symbol']}")
                    print(f"   جهت: {summary['direction']}")
                    print(f"   قیمت: {summary['price']}")
                    print(f"   ورود: {summary['entry']}")
                    print(f"   حد ضرر: {summary['sl']}")
                    print(f"   TP1: {summary['tps'][0] if summary['tps'] else 'N/A'}")
                    print(f"   TP2: {summary['tps'][1] if len(summary['tps']) > 1 else 'N/A'}")
                    print(f"   TP3: {summary['tps'][2] if len(summary['tps']) > 2 else 'N/A'}")
                    print(f"   اطمینان: {summary.get('confidence', 0):.1f}/10")
                    print(f"   تأیید روند: {'✅' if summary.get('confirmed') else '❌'}")
                    print(f"   حجم: {'✅' if summary.get('volume_spike') else '❌'}")
                    print(f"{'='*50}\n")
                    
                    # ارسال به تلگرام (اختیاری)
                    if CONFIG["TELEGRAM_BOT_TOKEN"]:
                        regime_note = " ⚡VOLATILE" if summary.get("market_regime") == "VOLATILE" else ""
                        line = f"{summary['symbol']}{regime_note}\n\n📊 {summary['direction']}\n\n🎯 ENTRY: {summary['entry']}\n🛑 SL: {summary['sl']}\n"
                        for i, tp in enumerate(summary.get('tps', [])[:3]):
                            line += f"🎯 TP{i+1}: {tp}\n"
                        line += f"🎓 اطمینان: {summary.get('confidence', 0):.1f}/10"
                        if regime_note:
                            line += "\n⚠️ بازار پرنوسان - آمار گذشته نشون داده این حالت ریسک بالاتری داره"
                        send_telegram_message_with_cooldown(symbol, summary['direction'], line)
            
            # ===================== SMART FALLBACK SCANNER =====================
            # اگر trigger-based scan چیزی پیدا نکرد یا بازار آرام شد، ربات دیگر منتظر
            # پامپ 15 دقیقه‌ای نمی‌ماند. چند کاندیدای برتر را با تحلیل کامل بررسی می‌کند.
            idle_min = max(0.0, (time.time() - _LAST_ACCEPTED_SIGNAL_TS) / 60.0)
            fallback_after = float(CONFIG.get("FALLBACK_SCAN_AFTER_MINUTES", 12))
            if len(signals) < 2 and idle_min >= fallback_after:
                candidates = []
                for c in coins:
                    sym = str(c.get("symbol", "")).upper()
                    if not sym.endswith("USDT"):
                        continue
                    ch = get_change_from_history(history, sym, 900)
                    if ch is None:
                        continue
                    try:
                        candidates.append((abs(float(ch)), float(ch), sym))
                    except Exception:
                        continue
                candidates.sort(reverse=True)
                candidates = candidates[:int(CONFIG.get("FALLBACK_CANDIDATES", 18))]
                logger.info(f"🛟 Smart fallback فعال شد | idle={idle_min:.1f}m | candidates={len(candidates)}")
                for _, ch, symbol in candidates:
                    if len(signals) >= int(CONFIG.get("MAX_NEW_SIGNALS_PER_CYCLE", 8)):
                        break
                    direction = "bull" if ch >= 0 else "bear"
                    direction_text = "LONG" if direction == "bull" else "SHORT"
                    allowed, reason = self_healing_autopilot.emergency_gate(symbol, direction_text)
                    if not allowed:
                        continue
                    try:
                        summary = enhanced_analysis(symbol, direction_hint=direction, recovery_mode=True)
                    except Exception as e:
                        logger.error(f"Fallback analysis failed {symbol}: {e}")
                        continue
                    if not summary:
                        continue
                    summary["pre_signal_change_15m"] = ch
                    summary["recovery_mode"] = True
                    signals.append(summary)
                    globals()["_LAST_ACCEPTED_SIGNAL_TS"] = time.time()
                    save_signal_history(summary)
                    auto_learning.add_signal_for_learning(summary)
                    signal_count += 1
                    logger.info(f"🛟 Fallback signal: {symbol} {summary.get('direction')} {summary.get('confidence',0):.1f}/10")
                    if CONFIG.get("TELEGRAM_BOT_TOKEN"):
                        regime_note = " ⚡VOLATILE" if summary.get("market_regime") == "VOLATILE" else ""
                        line = f"{summary['symbol']}{regime_note}\n\n📊 {summary['direction']}\n\n🎯 ENTRY: {summary['entry']}\n🛑 SL: {summary['sl']}\n"
                        for i, tp in enumerate(summary.get('tps', [])[:3]):
                            line += f"🎯 TP{i+1}: {tp}\n"
                        line += f"🎓 اطمینان: {summary.get('confidence', 0):.1f}/10\n🛟 Smart Recovery"
                        send_telegram_message_with_cooldown(symbol, summary['direction'], line)

            # self-diagnostic همیشه بعد از هر دور اجرا می‌شود.
            self_diagnose_and_repair()
            logger.info(f"📊 جمع‌بندی: پامپ‌ها: {pump_count} | دامپ‌ها: {dump_count} | سیگنال‌ها: {len(signals)}")
            
            if signals:
                save_signal_json_overwrite(signals)
            
            # خودترمیمی مداوم: تشخیص افت، تنظیم رژیم، snapshot و محافظت از سیستم
            try:
                self_healing_autopilot.run()
            except Exception as heal_err:
                logger.error(f"AutoPilot self-heal error: {heal_err}")

            # ML با فاصله کم‌تر خودش را با داده جدید تطبیق می‌دهد؛ بهینه‌سازی سنگین پارامترها روزانه می‌ماند.
            try:
                if ml_model.should_retrain():
                    ml_model.train(force=True)
            except Exception as ml_err:
                logger.error(f"ML periodic retrain failed: {ml_err}")

            # به‌روزرسانی روزانه سیستم یادگیری (بهینه‌سازی پارامترها)
            now_hour = int(time.time() // 3600)
            if now_hour - last_learning_update >= 24:
                update_learning_system()
                last_learning_update = now_hour
                
                # نمایش گزارش عملکرد
                summary = performance_memory.get_summary()
                if summary["total_trades"] > 0:
                    logger.info(f"📈 گزارش عملکرد: {summary['total_trades']} معامله, وین‌ریت: {summary['long_term_winrate']:.1f}%")
                    logger.info(f"   فاکتور سود: {summary.get('profit_factor', 0):.2f} | نسبت شارپ: {summary.get('sharpe_ratio', 0):.2f}")
            
            # گزارش دوره‌ای یادگیری به تلگرام؛ فقط بعد از ارسال موفق تایمر Reset می‌شود
            # (وگرنه اگه یه بار ارسال به هر دلیلی fail بشه، تا ساعت بعد اصلاً دوباره امتحان نمی‌شد)
            report_interval_sec = CONFIG.get("LEARNING_REPORT_INTERVAL_HOURS", 1) * 3600
            if time.time() - last_report_time >= report_interval_sec:
                logger.info("📨 زمان ارسال گزارش یادگیری فرا رسیده است...")
                report_text = build_learning_report(price_map)
                logger.info("\n" + report_text + "\n")
                if CONFIG.get("TELEGRAM_BOT_TOKEN") and CONFIG.get("TELEGRAM_CHAT_ID"):
                    report_sent = send_telegram_message(report_text, message_type="learning report")
                    if report_sent:
                        last_report_time = time.time()
                    else:
                        logger.warning("⚠️ گزارش یادگیری ارسال نشد؛ تایمر Reset نشد و در چرخه بعد دوباره تلاش می‌شود")
                else:
                    logger.error("❌ گزارش یادگیری قابل ارسال نیست: TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID خالی است")
            
            # نمایش خلاصه خطاها هر 100 بار
            if check_count % 100 == 0:
                logger.print_summary()
            
        except KeyboardInterrupt:
            logger.info("\n⏹️ دریافت سیگنال توقف... در حال خروج...")
            auto_learning.stop()
            logger.info("✅ برنامه متوقف شد")
            break
            
        except Exception as e:
            logger.error(f"خطا در حلقه اصلی: {e}")
        
        time.sleep(CONFIG["CHECK_INTERVAL"])


# ============================================================================
# بخش 19: نقطه شروع برنامه
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 سیستم تحلیل سیگنال نسخه 13.0 AUTO-PILOT - Self-Healing + Smart Signal Recovery")
    print("📚 یادگیری از سیگنال‌هایی که خودش می‌دهد (Walk-Forward + Path-based)")
    print("🎯 کمترین ضریب خطا - کاملاً خودکار")
    print("🔍 با قابلیت خطایابی کامل در هر بخش")
    print("=" * 60)
    print()
    
    # تست اتصال به بایننس
    test_result = test_binance_connection()

    # تست اعتبار توکن/چت‌آیدی تلگرام (بدون ارسال پیام آزمایشی به چت)
    test_telegram_connection()
    
    if not test_result["success"]:
        print("\n⚠️ اخطار: اتصال به بایننس برقرار نیست!")
        print("   ممکن است به VPN نیاز داشته باشید.")
        print("   آیا می‌خواهید ادامه دهید؟ (y/n)")
        response = input().strip().lower()
        if response != 'y':
            print("خروج از برنامه...")
            sys.exit(1)
    else:
        print("✅ اتصال به بایننس برقرار است. شروع برنامه...")
    
    print("\n" + "=" * 60)
    print("شروع حلقه اصلی...")
    print("برای خروج Ctrl+C را بزنید")
    print("=" * 60 + "\n")
    
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n⏹️ برنامه با موفقیت متوقف شد")
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}")
        traceback.print_exc()
