import re

def clean_ocr_duplicates(text: str) -> str:
    if not text:
        return text

    def clean_word(word: str) -> str:
        if len(word) <= 1:
            return word
            
        dup_pairs = 0
        k = 0
        while k < len(word) - 1:
            if word[k].lower() == word[k+1].lower():
                dup_pairs += 1
                k += 2
            else:
                k += 1
                
        has_accent_dup = False
        for j in range(len(word)-1):
            if word[j].lower() == word[j+1].lower() and any(c in "àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ" for c in word[j].lower()):
                has_accent_dup = True
                break
                
        is_common_english_dup = False
        if dup_pairs == 1:
            for j in range(len(word)-1):
                if word[j].lower() == word[j+1].lower() and word[j].lower() in "eo":
                    is_common_english_dup = True
                    break
                    
        dup_ratio = (dup_pairs * 2) / len(word)
        
        should_clean = False
        if has_accent_dup:
            should_clean = True
        elif dup_pairs >= 2:
            should_clean = True
        elif dup_pairs == 1 and len(word) <= 4 and dup_ratio >= 0.5 and not is_common_english_dup:
            should_clean = True
            
        if should_clean:
            cleaned = []
            skip = False
            for j in range(len(word)):
                if skip:
                    skip = False
                    continue
                if j + 1 < len(word) and word[j].lower() == word[j+1].lower():
                    cleaned.append(word[j])
                    skip = True
                else:
                    cleaned.append(word[j])
            return "".join(cleaned)
        return word

    words = text.split()
    cleaned_words = [clean_word(w) for w in words]
    result = " ".join(cleaned_words)
    
    for _ in range(3):
        result = re.sub(r'\b([A-Za-zÀ-ỹđĐ])\s+\1\b', r'\1', result)
        
    return result

import unicodedata
text = "Lý thuyết đồ thị... Giải thích tại sao đối với đồ thị sau, cần tìm đường đi dài nhất từ đỉnh 1 tới đỉnh 4 lại không thể dùng thuật toán Dijkstra được"
print("ORIGINAL:")
print(text)

print("\nNORMALIZED:")
norm = unicodedata.normalize('NFC', text)
print(norm)

print("\nCLEANED:")
clean = clean_ocr_duplicates(norm)
print(clean)
