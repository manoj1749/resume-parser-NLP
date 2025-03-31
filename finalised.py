import os
import re
import docx2txt
import fitz  # PyMuPDF
from collections import defaultdict
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

# ------------ Load Resume NER Model ------------ #

model_name = "manishiitg/resume-ner"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForTokenClassification.from_pretrained(model_name)
ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer, aggregation_strategy="simple")

# ------------ Text Extraction ------------ #

def extract_text(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".pdf":
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    elif ext == ".docx":
        return docx2txt.process(file_path)
    else:
        raise ValueError("Unsupported file type. Please use PDF or DOCX.")

# ------------ Basic Info (Regex) ------------ #

def extract_basic_info(text):
    name_match = re.search(r'(?i)^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})', text)
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    phone_match = re.search(r'(\+?\d[\d\s\-\(\)]{8,})', text)

    return {
        "Name": name_match.group(1).strip() if name_match else None,
        "Email": email_match.group(0).strip() if email_match else None,
        "Phone Number": phone_match.group(0).strip() if phone_match else None
    }

def clean_output(obj):
    return {k: v.strip().title() if isinstance(v, str) and v else v for k, v in obj.items()}

# ------------ Helper: Fallback Date Extraction ------------ #

def extract_dates_from_text(text):
    matches = re.findall(r'(?i)(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*\d{4})', text)
    if len(matches) >= 2:
        return f"{matches[0]} - {matches[1]}"
    elif len(matches) == 1:
        return matches[0]
    return None

# ------------ Structured Resume Info ------------ #

def extract_resume_info_structured(text):
    sentences = re.split(r'(?<=[\.\?\!\n])\s+', text)

    education = []
    experience = []

    last_date = None
    last_org = None

    for sent in sentences:
        ents = ner_pipeline(sent)
        if not ents:
            continue

        tags = defaultdict(str)
        date_tokens = []

        for ent in ents:
            clean_word = re.sub(r"\s+", " ", ent['word'].replace("##", "")).strip()
            entity_group = ent['entity_group']

            if entity_group == 'DATE':
                date_tokens.append(clean_word)
            else:
                tags[entity_group] += clean_word + " "

        # Clean final tag strings
        for key in tags:
            tags[key] = tags[key].strip()

        # Date handling (NER or regex fallback)
        date = None
        if len(date_tokens) >= 2:
            date = f"{date_tokens[0]} - {date_tokens[1]}"
        elif len(date_tokens) == 1:
            date = date_tokens[0]
        else:
            date = extract_dates_from_text(sent)

        # Update last known values
        if date:
            last_date = date
        if 'ORG' in tags or 'INSTITUTE' in tags or 'COMPANY' in tags:
            last_org = tags.get('ORG') or tags.get('INSTITUTE') or tags.get('COMPANY')

        # === Education ===
        is_edu = (
            'EducationDegree' in tags or
            re.search(r'\b(b\.tech|m\.tech|bachelor|master|engineering|intermediate|school|college|university)\b', sent, re.IGNORECASE)
        )

        if is_edu:
            degree = tags.get('EducationDegree')
            org = tags.get('ORG') or tags.get('INSTITUTE') or last_org
            if degree or org:
                education.append(clean_output({
                    "degree": degree,
                    "university": org,
                    "date": date or last_date
                }))

        # === Work Experience ===
        if 'Designation' in tags:
            designation = tags['Designation']
            company = tags.get('ORG') or tags.get('COMPANY') or last_org
            if designation or company:
                experience.append(clean_output({
                    "designation": designation,
                    "organization": company,
                    "date": date or last_date
                }))

    return {
        "Education": education,
        "Work Experience": experience
    }

# ------------ Main ------------ #

# if __name__ == "__main__":
#     resume_path = "../test-resume/Siddharth_Reddy_Resume.pdf"  # Update to your path

#     if not os.path.exists(resume_path):
#         print(f"Error: File '{resume_path}' not found.")
#     else:
#         resume_text = extract_text(resume_path)
#         basic_info = extract_basic_info(resume_text)
#         parsed = extract_resume_info_structured(resume_text)

#         print("\nBASIC INFO:")
#         print(basic_info)

#         for section, items in parsed.items():
#             print(f"\n{section}:")
#             for item in items:
#                 print(f"- {item}")

## ------------ Batch Folder Parser ------------ #
def process_resumes_in_folder(folder_path: str):
    for file_name in sorted(os.listdir(folder_path)):
        if not file_name.lower().endswith(('.pdf', '.docx')):
            continue

        file_path = os.path.join(folder_path, file_name)
        print(f"\n📄 Processing: {file_name}")

        try:
            text = extract_text(file_path)
            basic_info = extract_basic_info(text)
            structured = extract_resume_info_structured(text)

            print("\nBASIC INFO:")
            print(basic_info)

            print("\nEducation:")
            for edu in structured["Education"]:
                print("-", edu)

            print("\nWork Experience:")
            for work in structured["Work Experience"]:
                print("-", work)

        except Exception as e:
            print(f"⚠️ Error processing {file_name}: {e}")

# Prevent this from running when imported in FastAPI
if __name__ == "__main__":
    process_resumes_in_folder("../resume-parser-NLP/test-resume")
