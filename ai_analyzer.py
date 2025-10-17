import os
import anthropic
import json
from dotenv import load_dotenv

# Load variables from a local .env file (so CLAUDE_API_KEY in .env will be available)
load_dotenv()

# It's best practice to load the API key from an environment variable
API_KEY = os.environ.get("CLAUDE_API_KEY")

def analyze_terms(text_content: str) -> dict:
    """
    Analyzes the provided text using the Claude API and returns a structured JSON report.
    """
    client = anthropic.Anthropic(api_key=API_KEY)

    # The detailed prompt telling Claude what to do
    prompt = f"""
    Analyze the following Terms and Conditions text. Identify clauses related to data sharing, intellectual property, and account termination.
    Based on your analysis, fill in the following JSON template. Provide a risk score from 0 (low risk) to 100 (high risk).
    Do NOT add any text or explanation before or after the JSON object, only the JSON itself.

    JSON Template:
    {{
      "analysis_summary": "A brief, one-sentence summary of the terms and conditions' risk level.",
      "risk_score": {{ "overall": 0, "data_sharing": 0, "intellectual_property": 0, "termination_clause": 0 }},
      "clauses": [
        {{ "type": "DATA_SHARING", "summary": "...", "exact_quote": "...", "risk_level": "Low/Medium/High/Critical" }},
        {{ "type": "INTELLECTUAL_PROPERTY", "summary": "...", "exact_quote": "...", "risk_level": "Low/Medium/High/Critical" }},
        {{ "type": "TERMINATION", "summary": "...", "exact_quote": "...", "risk_level": "Low/Medium/High/Critical" }}
      ],
      "readability": {{ "score": "Easy/Medium/Hard/Very Difficult", "grade_level": "e.g., High School" }}
    }}

    Terms and Conditions Text to analyze:
    ---
    {text_content}
    ---
    """

    try:
        if not API_KEY:
            # Fail fast with a clear message when the key is missing
            raise RuntimeError(
                "CLAUDE_API_KEY not found. Please add it to your .env file or set the environment variable."
            )

        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt}
            ]
        ).content[0].text
        # Helper: clean model output from common wrappers (markdown fences, code blocks)
        def _clean_model_output(s: str) -> str:
            if not s:
                return s
            s_strip = s.strip()
            # Remove triple-backtick fenced blocks (with optional language identifier)
            if s_strip.startswith("```") and s_strip.endswith("```"):
                lines = s_strip.splitlines()
                # remove first and last fence lines
                if len(lines) >= 3:
                    return "\n".join(lines[1:-1]).strip()
                # fallback: strip the fences
                return s_strip.strip("`").strip()

            # Remove single-line fencing of a JSON blob like `{"a":1}`
            if s_strip.startswith("`") and s_strip.endswith("`"):
                return s_strip.strip("`").strip()

            return s

        # Clean the model response before parsing
        message_clean = _clean_model_output(message)

        # The response should be a clean JSON string, so we parse it
        try:
            report = json.loads(message_clean)
            return report
        except json.JSONDecodeError:
            # Print the raw response for debugging
            print("Failed to parse JSON. Raw model response:")
            print(message)

            # Attempt a best-effort extraction of the first JSON object in the cleaned text
            start = message_clean.find('{')
            end = message_clean.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = message_clean[start:end+1]
                try:
                    report = json.loads(candidate)
                    print("Successfully parsed JSON after extracting substring.")
                    return report
                except json.JSONDecodeError:
                    print("Substring extraction failed to produce valid JSON.")

            # If we reach here, parsing failed
            raise

    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": "Failed to analyze text."}

# --- To test this script ---
if __name__ == "__main__":
    # Use a sample text file until the scraper is ready
    with open("spotify_tc.txt", "r") as f:
        sample_text = f.read()

    analysis_result = analyze_terms(sample_text)
    print(json.dumps(analysis_result, indent=2))