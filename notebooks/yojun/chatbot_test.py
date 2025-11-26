# run_vector_store.py

from notebooks.yojun.vectorstore_manager import save_month_folder_to_vectorstore

# 1) 월별 강의자료 폴더
month_folder = r"C:\POTENUP\MumulMumul\storage\Bootcamp_Lectures"

# 2) 벡터스토어 저장 폴더
db_root = r"C:\POTENUP\MumulMumul\storage\vectorstore"

# 3) 저장할 월
month = "all_new"

if __name__ == "__main__":
    save_month_folder_to_vectorstore(month_folder, db_root, month)
