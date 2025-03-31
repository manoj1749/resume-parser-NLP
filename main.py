from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import tempfile
import shutil

# Import functions from finalised.py
from finalised import extract_text, extract_basic_info, extract_resume_info_structured

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Resume Parser API is running!"}


@app.post("/parse-resume/")
async def parse_resume(file: UploadFile = File(...)):
    # Check supported file types
    if not file.filename.lower().endswith(('.pdf', '.docx')):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    try:
        # Save file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            temp_path = tmp_file.name

        # Extract and parse
        text = extract_text(temp_path)
        basic_info = extract_basic_info(text)
        structured = extract_resume_info_structured(text)

        return JSONResponse(content={
            "Basic Info": basic_info,
            "Education": structured["Education"],
            "Work Experience": structured["Work Experience"]
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing resume: {str(e)}")
