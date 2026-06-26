"""
research/utils/yaml_loader.py
=============================
Đọc file cấu hình Benchmark Matrix (YAML).
"""
import yaml
import os

def load_benchmark_matrix() -> list[str]:
    """
    Đọc file research/configs/benchmark_matrix.yaml và trả về
    danh sách các experiments (tên các cấu hình) cần chạy.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    matrix_path = os.path.join(base_dir, "research", "configs", "benchmark_matrix.yaml")
    
    if not os.path.exists(matrix_path):
        raise FileNotFoundError(f"Không tìm thấy file {matrix_path}")
        
    with open(matrix_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    experiments = data.get("experiments", [])
    if not experiments:
        raise ValueError(f"File {matrix_path} không có experiment nào được định nghĩa.")
        
    return experiments

def load_chunking_config(config_name: str) -> dict:
    """
    Tải cấu hình chi tiết (chunk_size, chunk_overlap, strategy) từ file global_config 
    hoặc 1 định dạng mapping cho trước dựa vào config_name.
    Trong phạm vi đơn giản, ta map cứng logic tại đây.
    """
    # Mapping tĩnh các experiment name sang cấu hình chi tiết
    mapping = {
        "fixed_512": {"strategy": "fixed", "chunk_size": 512, "chunk_overlap": 51, "length_unit": "char"},
        "fixed_1024": {"strategy": "fixed", "chunk_size": 1024, "chunk_overlap": 102, "length_unit": "char"},
        
        "recursive_512": {"strategy": "recursive", "chunk_size": 512, "chunk_overlap": 51, "length_unit": "char"},
        "recursive_1024": {"strategy": "recursive", "chunk_size": 1024, "chunk_overlap": 102, "length_unit": "char"},
        
        "sentence_small": {"strategy": "sentence", "sentence_count": 6, "overlap_sentences": 1},
        "sentence_large": {"strategy": "sentence", "sentence_count": 12, "overlap_sentences": 2},
        
        "token_128": {"strategy": "token", "chunk_size": 128, "chunk_overlap": 13},
        "token_256": {"strategy": "token", "chunk_size": 256, "chunk_overlap": 26},
        
        "semantic_low": {"strategy": "semantic", "chunk_size": 300},
        "semantic_high": {"strategy": "semantic", "chunk_size": 800}
    }
    
    if config_name not in mapping:
        raise ValueError(f"Config '{config_name}' chưa được hỗ trợ trong hệ thống mapping.")
        
    return mapping[config_name]
