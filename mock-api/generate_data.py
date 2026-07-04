#!/usr/bin/env python3
"""世界主要 100 都市 × 12 か月 × 10 年 の月平均気温テストデータ生成器（正規化版）。

2 つのエンティティを別ファイルに出力する:

    cities.json        … 都市マスタ (100 件)
        { "id", "city", "country", "latitude", "longitude" }

    temperatures.json  … 月平均気温 (12,000 件)
        { "id", "city_id", "year", "month", "temp" }
        - city_id は cities.id への外部キー
        - temp は摂氏 (°C)、小数第 1 位

- 実データが手元に無いため、都市ごとの「年平均気温 (climatological normal)」を
  基準に、緯度から求めた季節振幅・半球位相・微小な経年トレンド・決定論的ノイズを
  合成した近似値。乱数は (city, year, month) をシードに固定しており、何度実行しても
  同じ値が再現される（CI / モック API で安定的に使える）。

実行:
    python generate_data.py            # data/cities.json と data/temperatures.json を生成
"""

import argparse
import json
import math
import random
from pathlib import Path

# (city, country, latitude, longitude, annual_mean_temp_C)
# 年平均気温は代表的な平年値に基づく概算。
CITIES = [
    ("Tokyo", "Japan", 35.68, 139.69, 16.0),
    ("Delhi", "India", 28.61, 77.21, 25.0),
    ("Shanghai", "China", 31.23, 121.47, 17.0),
    ("Sao Paulo", "Brazil", -23.55, -46.63, 19.0),
    ("Mexico City", "Mexico", 19.43, -99.13, 17.0),
    ("Cairo", "Egypt", 30.04, 31.24, 22.0),
    ("Mumbai", "India", 19.08, 72.88, 27.0),
    ("Beijing", "China", 39.90, 116.41, 13.0),
    ("Dhaka", "Bangladesh", 23.81, 90.41, 26.0),
    ("Osaka", "Japan", 34.69, 135.50, 17.0),
    ("New York", "United States", 40.71, -74.01, 13.0),
    ("Karachi", "Pakistan", 24.86, 67.01, 26.0),
    ("Buenos Aires", "Argentina", -34.60, -58.38, 18.0),
    ("Chongqing", "China", 29.43, 106.91, 18.0),
    ("Istanbul", "Turkey", 41.01, 28.98, 15.0),
    ("Kolkata", "India", 22.57, 88.36, 27.0),
    ("Manila", "Philippines", 14.60, 120.98, 28.0),
    ("Lagos", "Nigeria", 6.52, 3.38, 27.0),
    ("Rio de Janeiro", "Brazil", -22.91, -43.17, 24.0),
    ("Tianjin", "China", 39.13, 117.20, 13.0),
    ("Kinshasa", "DR Congo", -4.44, 15.27, 25.0),
    ("Guangzhou", "China", 23.13, 113.26, 22.0),
    ("Los Angeles", "United States", 34.05, -118.24, 18.0),
    ("Moscow", "Russia", 55.76, 37.62, 6.0),
    ("Shenzhen", "China", 22.54, 114.06, 23.0),
    ("Lahore", "Pakistan", 31.55, 74.34, 24.0),
    ("Bangalore", "India", 12.97, 77.59, 24.0),
    ("Paris", "France", 48.86, 2.35, 12.0),
    ("Bogota", "Colombia", 4.71, -74.07, 14.0),
    ("Jakarta", "Indonesia", -6.21, 106.85, 28.0),
    ("Chennai", "India", 13.08, 80.27, 29.0),
    ("Lima", "Peru", -12.05, -77.04, 19.0),
    ("Bangkok", "Thailand", 13.76, 100.50, 29.0),
    ("Seoul", "South Korea", 37.57, 126.98, 13.0),
    ("Nagoya", "Japan", 35.18, 136.91, 16.0),
    ("Hyderabad", "India", 17.39, 78.49, 27.0),
    ("London", "United Kingdom", 51.51, -0.13, 11.0),
    ("Tehran", "Iran", 35.69, 51.39, 17.0),
    ("Chicago", "United States", 41.88, -87.63, 10.0),
    ("Chengdu", "China", 30.57, 104.07, 16.0),
    ("Nanjing", "China", 32.06, 118.80, 16.0),
    ("Wuhan", "China", 30.59, 114.31, 17.0),
    ("Ho Chi Minh City", "Vietnam", 10.82, 106.63, 28.0),
    ("Luanda", "Angola", -8.84, 13.23, 26.0),
    ("Ahmedabad", "India", 23.03, 72.59, 27.0),
    ("Kuala Lumpur", "Malaysia", 3.14, 101.69, 27.0),
    ("Xian", "China", 34.34, 108.94, 14.0),
    ("Hong Kong", "China", 22.32, 114.17, 23.0),
    ("Dongguan", "China", 23.02, 113.75, 22.0),
    ("Hangzhou", "China", 30.27, 120.15, 17.0),
    ("Foshan", "China", 23.02, 113.12, 22.0),
    ("Riyadh", "Saudi Arabia", 24.71, 46.68, 26.0),
    ("Baghdad", "Iraq", 33.31, 44.36, 23.0),
    ("Santiago", "Chile", -33.45, -70.67, 14.0),
    ("Surat", "India", 21.17, 72.83, 27.0),
    ("Madrid", "Spain", 40.42, -3.70, 15.0),
    ("Suzhou", "China", 31.30, 120.58, 16.0),
    ("Pune", "India", 18.52, 73.86, 25.0),
    ("Harbin", "China", 45.80, 126.53, 5.0),
    ("Houston", "United States", 29.76, -95.37, 21.0),
    ("Dallas", "United States", 32.78, -96.80, 19.0),
    ("Toronto", "Canada", 43.65, -79.38, 9.0),
    ("Dar es Salaam", "Tanzania", -6.79, 39.21, 26.0),
    ("Miami", "United States", 25.76, -80.19, 25.0),
    ("Belo Horizonte", "Brazil", -19.92, -43.94, 21.0),
    ("Singapore", "Singapore", 1.35, 103.82, 28.0),
    ("Philadelphia", "United States", 39.95, -75.17, 13.0),
    ("Atlanta", "United States", 33.75, -84.39, 17.0),
    ("Fukuoka", "Japan", 33.59, 130.40, 17.0),
    ("Khartoum", "Sudan", 15.50, 32.56, 30.0),
    ("Barcelona", "Spain", 41.39, 2.17, 16.0),
    ("Johannesburg", "South Africa", -26.20, 28.05, 16.0),
    ("Saint Petersburg", "Russia", 59.93, 30.34, 6.0),
    ("Yangon", "Myanmar", 16.87, 96.20, 28.0),
    ("Alexandria", "Egypt", 31.20, 29.92, 21.0),
    ("Guadalajara", "Mexico", 20.66, -103.35, 20.0),
    ("Ankara", "Turkey", 39.93, 32.87, 12.0),
    ("Melbourne", "Australia", -37.81, 144.96, 15.0),
    ("Sydney", "Australia", -33.87, 151.21, 18.0),
    ("Nairobi", "Kenya", -1.29, 36.82, 18.0),
    ("Cape Town", "South Africa", -33.92, 18.42, 17.0),
    ("Berlin", "Germany", 52.52, 13.40, 10.0),
    ("Casablanca", "Morocco", 33.57, -7.59, 18.0),
    ("Addis Ababa", "Ethiopia", 9.03, 38.74, 16.0),
    ("Jeddah", "Saudi Arabia", 21.49, 39.19, 29.0),
    ("Rome", "Italy", 41.90, 12.50, 16.0),
    ("Accra", "Ghana", 5.60, -0.19, 27.0),
    ("Abidjan", "Ivory Coast", 5.36, -4.01, 27.0),
    ("Kano", "Nigeria", 12.00, 8.52, 26.0),
    ("Caracas", "Venezuela", 10.48, -66.90, 22.0),
    ("Kabul", "Afghanistan", 34.56, 69.21, 13.0),
    ("Montreal", "Canada", 45.50, -73.57, 7.0),
    ("Guatemala City", "Guatemala", 14.63, -90.51, 19.0),
    ("Havana", "Cuba", 23.11, -82.37, 25.0),
    ("Vancouver", "Canada", 49.28, -123.12, 11.0),
    ("Auckland", "New Zealand", -36.85, 174.76, 15.0),
    ("Kyiv", "Ukraine", 50.45, 30.52, 8.0),
    ("Warsaw", "Poland", 52.23, 21.01, 9.0),
    ("Amsterdam", "Netherlands", 52.37, 4.90, 10.0),
    ("Bandung", "Indonesia", -6.91, 107.61, 23.0),
]

START_YEAR = 2016
END_YEAR = 2025  # inclusive -> 10 年分
WARMING_PER_YEAR = 0.03  # 微小な経年温暖化トレンド (°C/年)


def seasonal_offset(lat: float, month: float) -> float:
    """緯度と月から季節変動 (°C) を返す。

    北半球は 7 月ピーク、南半球は 1 月ピーク。振幅は緯度の絶対値に比例
    （高緯度ほど季節差大）、上限 17°C。
    """
    amplitude = min(abs(lat) * 0.28, 17.0)
    peak_month = 7.0 if lat >= 0 else 1.0
    return amplitude * math.cos(2.0 * math.pi * (month - peak_month) / 12.0)


def generate() -> tuple[list[dict], list[dict]]:
    """(cities, temperatures) を返す。"""
    cities: list[dict] = []
    temperatures: list[dict] = []
    temp_id = 1
    for city_id, (city, country, lat, lon, annual_mean) in enumerate(CITIES, start=1):
        cities.append(
            {
                "id": city_id,
                "city": city,
                "country": country,
                "latitude": lat,
                "longitude": lon,
            }
        )
        for year in range(START_YEAR, END_YEAR + 1):
            for month in range(1, 13):
                rng = random.Random(f"{city}|{year}|{month}")
                noise = rng.uniform(-1.2, 1.2)
                trend = (year - START_YEAR) * WARMING_PER_YEAR
                temp = annual_mean + seasonal_offset(lat, month) + trend + noise
                temperatures.append(
                    {
                        "id": temp_id,
                        "city_id": city_id,
                        "year": year,
                        "month": month,
                        "temp": round(temp, 1),
                    }
                )
                temp_id += 1
    return cities, temperatures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).parent / "data"),
        help="出力ディレクトリ",
    )
    args = parser.parse_args()

    cities, temperatures = generate()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "cities.json").write_text(
        json.dumps(cities, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (data_dir / "temperatures.json").write_text(
        json.dumps(temperatures, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(cities)} cities to {data_dir / 'cities.json'}")
    print(f"Wrote {len(temperatures)} temperatures to {data_dir / 'temperatures.json'}")


if __name__ == "__main__":
    main()
