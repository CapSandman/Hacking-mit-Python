import os
from datetime import date

def get_bam_rate(for_date: date) -> float:
    """
    Vrati kurs EUR->KM za zadati dan.
    Podrazumevano koristi fiksni peg 1.95583 ili .env BAM_PER_EUR.
    Ako želiš kasnije: ovde možeš dodati lookup iz tabele 'fx_rates'.
    """
    try:
        return float(os.getenv("BAM_PER_EUR", "1.95583"))
    except Exception:
        return 1.95583

def get_pdv_percent() -> float:
    try:
        return float(os.getenv("PDV_PERCENT", "17"))
    except Exception:
        return 17.0
