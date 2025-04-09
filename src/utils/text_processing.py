def split_text_into_sentences(text):
    import re
    pattern = r'([。！？])'
    parts = re.split(pattern, text)
    
    sentences = []
    temp_sentence = []
    
    for part in parts:
        if re.match(pattern, part):
            temp_sentence.append(part)
            sentence = "".join(temp_sentence).strip()
            if sentence:
                sentences.append(sentence)
            temp_sentence = []
        else:
            temp_sentence.append(part)
    
    if temp_sentence:
        sentence = "".join(temp_sentence).strip()
        if sentence:
            sentences.append(sentence)
    
    return [s for s in sentences if s.strip()]

def clean_text(text):
    return text.strip()  # Add more cleaning logic if needed

def process_text(text):
    cleaned_text = clean_text(text)
    return split_text_into_sentences(cleaned_text)