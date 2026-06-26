"""
research/utils/dataset_loader.py
================================
Đọc dataset và quản lý version.json.
"""
import json
import os

def get_datasets_dir() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "research", "datasets")

def load_dataset_version() -> dict:
    """Đọc file version.json."""
    datasets_dir = get_datasets_dir()
    version_file = os.path.join(datasets_dir, "version.json")
    
    if not os.path.exists(version_file):
        raise FileNotFoundError(f"Không tìm thấy file version.json tại {version_file}")
        
    with open(version_file, "r", encoding="utf-8") as f:
        return json.load(f)

def load_active_dataset() -> tuple[list[dict], str]:
    """
    Đọc benchmark dataset dựa trên file được chỉ định trong version.json.
    Trả về:
        - list[dict]: Danh sách câu hỏi.
        - str: dataset_version.
    """
    version_info = load_dataset_version()
    dataset_version = version_info.get("dataset_version", "unknown")
    active_file = version_info.get("active_file")
    
    if not active_file:
        raise ValueError("version.json không định nghĩa 'active_file'")
        
    dataset_path = os.path.join(get_datasets_dir(), active_file)
    
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Không tìm thấy active dataset tại {dataset_path}")
        
    with open(dataset_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
        
    return questions, dataset_version
