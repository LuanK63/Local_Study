"""
scratch/test_ocr_clean.py
Verify the refined clean_ocr_duplicates function.
"""
import sys
import re

if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def clean_ocr_duplicates(text: str) -> str:
    if not text:
        return text

    def clean_word(word: str) -> str:
        if len(word) <= 1:
            return word
            
        # Count duplicate pairs
        dup_pairs = 0
        k = 0
        while k < len(word) - 1:
            if word[k].lower() == word[k+1].lower():
                dup_pairs += 1
                k += 2
            else:
                k += 1
                
        # Check for duplicate accented Vietnamese character
        has_accent_dup = False
        for j in range(len(word)-1):
            if word[j].lower() == word[j+1].lower() and any(c in "àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ" for c in word[j].lower()):
                has_accent_dup = True
                break
                
        # Check if the only duplicate pair is 'e' or 'o'
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

    # Clean words
    words = text.split()
    cleaned_words = [clean_word(w) for w in words]
    result = " ".join(cleaned_words)
    
    # Remove single characters separated by spaces (e.g., "G G" -> "G")
    for _ in range(3):
        result = re.sub(r'\b([A-Za-zÀ-ỹđĐ])\s+\1\b', r'\1', result)
        
    return result

def main():
    test_cases = [
        "LLÊÊM MIINNH HHOÀ HOÀNNG G",
        "PPH HẦẦNN22..CCẤẤUUTTRRÚÚCCDDỮ ỮLLIIỆỆUUVVÀÀ",
        "G GIIẢẢIITTH HUUẬẬTT",
        "loop tree free c++ class pattern lookup"
    ]
    
    for tc in test_cases:
        cleaned = clean_ocr_duplicates(tc)
        print(f"Original: '{tc}'")
        print(f"Cleaned : '{cleaned}'")
        print("-" * 50)

if __name__ == "__main__":
    main()
