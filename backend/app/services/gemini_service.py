import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Load API Key
genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel("gemini-2.0-flash")


def generate_financial_insights(comparison_results):

    try:

        # Prepare comparison summary
        summary_text = ""

        for item in comparison_results[:15]:

            summary_text += f"""
            Account: {item['account']}
            Section: {item['section']}
            Previous Year: {item['year1_value']}
            Current Year: {item['year2_value']}
            Growth: {item['growth_percent']}%
            """

        # Prompt
        prompt = f"""
                You are a senior financial analyst.
            Analyze the financial data below.
            Rules:
            - Keep response professional
            - Keep response concise
            - Maximum 10 points
            - Avoid markdown symbols
            - Use simple business language
            - Mention important increases/decreases
            - Mention risks
            - Mention positive signals
            - Give recommendations

            Financial Data:
            {summary_text}
            """

        response = model.generate_content(prompt)

        return {
            "status": "success",
            "ai_analysis": response.text.strip()
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }