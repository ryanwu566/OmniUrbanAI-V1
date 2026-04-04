import pandas as pd

# 1. 你的 CSV 檔案名稱
csv_file_name = 'opendata114road.csv'

print("讀取全國路名資料中，請稍候...")

try:
    # 嘗試讀取 CSV (政府資料通常是帶 BOM 的 utf-8 或是 big5)
    try:
        df = pd.read_csv(csv_file_name, encoding='utf-8-sig')
    except:
        df = pd.read_csv(csv_file_name, encoding='big5')
    
    road_dict = {}
    
    # 2. 依照你截圖的真實欄位名稱
    col_city = 'city'
    col_site = 'site_id'
    col_road = 'road'

    for index, row in df.iterrows():
        city = str(row[col_city]).strip()
        site_id = str(row[col_site]).strip()
        road = str(row[col_road]).strip()
        
        if pd.isna(road) or road == "" or road == "nan":
            continue
            
        # ⚠️ 破解政府資料陷阱：把 site_id 裡重複的縣市名稱拔掉 (例如把 '宜蘭縣三星鄉' 變成 '三星鄉')
        dist = site_id.replace(city, "") 
        
        # 組合出我們系統要的 Key，例如 "宜蘭縣_三星鄉"
        key = f"{city}_{dist}"
        
        if key not in road_dict:
            road_dict[key] = []
            
        if road not in road_dict[key]:
            road_dict[key].append(road)

    # 3. 將結果輸出成我們需要的 Python 檔案
    output_file = 'new_taiwan_roads.py'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("TAIWAN_ROADS = {\n")
        for k, v in road_dict.items():
            f.write(f'    "{k}": {v},\n')
        f.write("}\n")
        
    print(f"🎉 轉換大成功！全台 {len(road_dict)} 個行政區的真實路名已寫入 {output_file}")

except Exception as e:
    print(f"❌ 發生錯誤啦: {e}")