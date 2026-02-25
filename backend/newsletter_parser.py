import pandas as pd
import re
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

class NewsletterParser:
    """
    Parse structured newsletter tables to extract curriculum data.
    Assumes consistent table format across newsletters.
    """
    
    @staticmethod
    def parse_csv_table(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse CSV format newsletter table.
        Expected columns: Date, Subject, Topic, Week/Duration
        """
        df = pd.read_csv(file_path)
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()
        
        curriculum_items = []
        for _, row in df.iterrows():
            item = {
                "subject": str(row.get("subject", "")).strip(),
                "topic": str(row.get("topic", "")).strip(),
                "start_date": NewsletterParser._parse_date(row.get("date", row.get("start_date", ""))),
                "end_date": NewsletterParser._parse_date(row.get("end_date", "")) if "end_date" in row else None
            }
            
            if item["subject"] and item["topic"]:
                curriculum_items.append(item)
        
        return curriculum_items
    
    @staticmethod
    def parse_excel_table(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse Excel format newsletter table.
        Expected columns: Date, Subject, Topic, Week/Duration
        """
        df = pd.read_excel(file_path)
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()
        
        curriculum_items = []
        for _, row in df.iterrows():
            subject = str(row.get("subject", "")).strip()
            topic = str(row.get("topic", "")).strip()
            start_date = NewsletterParser._parse_date(row.get("date", row.get("start_date", "")))
            
            # Skip rows with missing essential data or nan values
            if subject and topic and start_date and subject.lower() != "nan" and topic.lower() != "nan":
                item = {
                    "subject": subject,
                    "topic": topic,
                    "start_date": start_date,
                    "end_date": NewsletterParser._parse_date(row.get("end_date", "")) if "end_date" in row else None
                }
                curriculum_items.append(item)
        
        return curriculum_items
    
    @staticmethod
    def _parse_date(date_value: Any) -> str:
        """Parse date from various formats to YYYY-MM-DD string"""
        if pd.isna(date_value):
            return None
        
        if isinstance(date_value, (datetime, pd.Timestamp)):
            return date_value.strftime("%Y-%m-%d")
        
        # Try parsing string dates
        date_str = str(date_value).strip()
        
        # Common formats - including 2-digit years
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y", "%m/%d/%y", "%d-%m-%y"]
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return None
    
    @staticmethod
    def parse_pdf_with_ollama(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse PDF newsletter using pdfplumber + Ollama.
        Extracts tables and uses LLM to normalize curriculum data.
        """
        try:
            # Extract all tables from PDF
            tables_text = []
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables, 1):
                        # Convert table to text representation
                        table_str = f"\n--- Page {page_num}, Table {table_num} ---\n"
                        for row in table:
                            table_str += " | ".join([str(cell) if cell else "" for cell in row]) + "\n"
                        tables_text.append(table_str)
            
            if not tables_text:
                raise ValueError("No tables found in PDF")
            
            # Combine all tables
            all_tables = "\n".join(tables_text)
            
            # Use Ollama to extract and normalize curriculum data
            llm = ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                temperature=0.1,  # Low temperature for precise extraction
                format="json"
            )
            
            prompt = f"""You are extracting curriculum schedule data from a school newsletter.

Here are the tables extracted from the PDF:
{all_tables[:15000]}

Find the curriculum/study schedule table and extract each topic with its details.

Return a JSON array of curriculum items with this exact structure:
[
  {{
    "subject": "subject name (e.g., English, Math, EVS, Art)",
    "topic": "specific topic description",
    "start_date": "date in DD/MM/YYYY or DD/MM/YY format",
    "end_date": null
  }}
]

Rules:
- Only extract the curriculum/timetable/study schedule (ignore other tables like announcements, events, etc.)
- Extract ALL curriculum items from the schedule
- Keep topic descriptions concise but complete
- If a date range is given, use the start date
- If no date is found for an item, skip it
- Return valid JSON array only
"""
            
            response = llm.invoke(prompt)
            
            # Parse JSON response
            if hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            curriculum_data = json.loads(content.strip())
            
            # Handle both list and dict responses from Ollama
            if isinstance(curriculum_data, dict):
                # Try to find the list in the dict (common keys: items, curriculum, data, schedule)
                for key in ['items', 'curriculum', 'data', 'schedule', 'topics', 'curriculum_items']:
                    if key in curriculum_data and isinstance(curriculum_data[key], list):
                        curriculum_data = curriculum_data[key]
                        break
                else:
                    # If still a dict, wrap in list or raise error
                    if 'subject' in curriculum_data and 'topic' in curriculum_data:
                        curriculum_data = [curriculum_data]
                    else:
                        raise ValueError(f"Ollama returned dict but couldn't find curriculum list. Keys: {curriculum_data.keys()}")
            
            if not isinstance(curriculum_data, list):
                raise ValueError(f"Expected list from Ollama, got {type(curriculum_data)}")
            
            # Normalize dates to YYYY-MM-DD format
            for item in curriculum_data:
                if not isinstance(item, dict):
                    raise ValueError(f"Expected dict items, got {type(item)}: {item}")
                    
                if item.get("start_date"):
                    item["start_date"] = NewsletterParser._parse_date(item["start_date"])
                if item.get("end_date"):
                    item["end_date"] = NewsletterParser._parse_date(item["end_date"])
            
            return curriculum_data
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Ollama response as JSON: {e}\nResponse: {content[:500]}")
        except Exception as e:
            raise ValueError(f"PDF parsing failed: {str(e)}")
    
    @staticmethod
    def auto_parse(file_path: str) -> List[Dict[str, Any]]:
        """
        Automatically detect file type and parse accordingly.
        Supports: CSV, Excel (xlsx, xls), PDF
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == ".csv":
            return NewsletterParser.parse_csv_table(file_path)
        elif file_ext in [".xlsx", ".xls"]:
            return NewsletterParser.parse_excel_table(file_path)
        elif file_ext == ".pdf":
            return NewsletterParser.parse_pdf_with_ollama(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}. Use .csv, .xlsx, or .pdf")
