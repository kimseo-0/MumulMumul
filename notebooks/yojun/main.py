

# main.py
import os
from vectorstore_manager import save_month_folder_to_vectorstore

# 🔥 1) PDF 자료가 들어있는 폴더
# 예: storage/Bootcamp_Lectures/8월 강의자료(머신러닝,딥러닝)
folder_path = r"C:\POTENUP\MumulMumul\storage\Bootcamp_Lectures\10월 강의자료(에이전트)"

# 🔥 2) 벡터스토어가 저장될 최상위 폴더
# 예: MumulMumul/vectorstore
db_root = r"C:\POTENUP\MumulMumul\storage\vectorstore"

# 🔥 3) 월을 문자열로 지정 (ex: "08", "09")
month = "10"

if __name__ == "__main__":
    save_month_folder_to_vectorstore(folder_path, db_root, month)
