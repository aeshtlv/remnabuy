#!/usr/bin/env python3
"""Тестовый скрипт для проверки чтения настроек из .env"""
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import get_settings

def main():
    print("=" * 70)
    print("READING SETTINGS FROM .env TEST")
    print("=" * 70)
    
    # Проверяем наличие .env
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        print(f"[OK] File .env found: {env_file}")
    else:
        print(f"[ERROR] File .env NOT FOUND: {env_file}")
        return
    
    # Читаем настройки
    settings = get_settings()
    
    print("\n" + "=" * 70)
    print("SUBSCRIPTION PRICES CHECK")
    print("=" * 70)
    
    prices = {
        "1 month": settings.subscription_stars_1month,
        "3 months": settings.subscription_stars_3months,
        "6 months": settings.subscription_stars_6months,
        "12 months": settings.subscription_stars_12months,
    }
    
    for period, price in prices.items():
        print(f"{period:12} = {price} stars")
    
    print("\n" + "=" * 70)
    print("SQUADS CHECK")
    print("=" * 70)
    
    print(f"External squad UUID: {settings.default_external_squad_uuid or 'NOT SET'}")
    print(f"Internal squads: {settings.default_internal_squads}")
    print(f"Internal squads count: {len(settings.default_internal_squads) if settings.default_internal_squads else 0}")
    
    if settings.default_internal_squads:
        for i, squad in enumerate(settings.default_internal_squads, 1):
            print(f"  [{i}] {squad}")
    
    print("\n" + "=" * 70)
    print("ENVIRONMENT VARIABLES CHECK (OS.ENVIRON)")
    print("=" * 70)
    
    env_vars = [
        "SUBSCRIPTION_STARS_1MONTH",
        "SUBSCRIPTION_STARS_3MONTHS",
        "SUBSCRIPTION_STARS_6MONTHS",
        "SUBSCRIPTION_STARS_12MONTHS",
        "DEFAULT_EXTERNAL_SQUAD_UUID",
        "DEFAULT_INTERNAL_SQUADS",
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"[OK] {var:35} = {value}")
        else:
            print(f"[NO] {var:35} = NOT SET")
    
    print("\n" + "=" * 70)
    print("ADMINS CHECK")
    print("=" * 70)
    print(f"Admins: {settings.admins}")
    print(f"Admins count: {len(settings.admins)}")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETED")
    print("=" * 70)

if __name__ == "__main__":
    main()

