from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional
from backend.config import settings

class CurriculumItemValidation(BaseModel):
    """Schema for validated curriculum item"""
    subject: str = Field(description="Subject name (e.g., Math, English)")
    topic: str = Field(description="Specific topic within subject")
    start_date: str = Field(description="Start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(default=None, description="End date in YYYY-MM-DD format if provided")

class CurriculumValidationResponse(BaseModel):
    """Schema for Ollama's validation response"""
    validated_items: List[CurriculumItemValidation] = Field(description="List of validated and corrected curriculum items")
    corrections_made: List[str] = Field(description="List of corrections or issues found")

class OllamaValidator:
    """
    Use Ollama (local LLM) to validate and correct extracted curriculum data.
    Leverages LLM's understanding to fix parsing errors, normalize names, etc.
    """
    
    def __init__(self):
        self.llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            format="json"
        )
        self.parser = JsonOutputParser(pydantic_object=CurriculumValidationResponse)
    
    def validate_curriculum(self, raw_items: List[dict], month: str, year: int) -> dict:
        """
        Validate and correct curriculum items using Ollama.
        
        Args:
            raw_items: Raw parsed curriculum items from template parser
            month: Month name for context
            year: Year for context
            
        Returns:
            Dict with validated_items and corrections_made
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a curriculum data validator. Your job is to:
1. Validate and correct subject names (capitalize properly, fix typos)
2. Validate and correct topic names (proper formatting)
3. Ensure dates are valid and in YYYY-MM-DD format
4. Flag any suspicious or incomplete data
5. Standardize subject names (Math not Maths, English not Eng, etc.)

Return validated data as JSON matching the schema."""),
            ("human", """Validate this curriculum data for {month} {year}:

Raw data:
{raw_data}

Return:
1. validated_items: corrected curriculum items
2. corrections_made: list of issues found and fixed

{format_instructions}""")
        ])
        
        chain = prompt | self.llm | self.parser
        
        result = chain.invoke({
            "month": month,
            "year": year,
            "raw_data": str(raw_items),
            "format_instructions": self.parser.get_format_instructions()
        })
        
        return result
