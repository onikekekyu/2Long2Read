import os
import json
import time
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Configuration
RAW_DATA_DIR = Path("raw_data")
STRUCTURED_DATA_DIR = Path("structured_data_hybrid")
CONFIG_FILE = Path("config/companies_config.json")

# Client Anthropic
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Charger la config des entreprises
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)
    companies_dict = {c["name"].lower().replace(" ", "_"): c for c in config["companies"]}


def clean_model_output(text: str) -> str:
    """
    Nettoie la sortie du modèle (gère markdown fences).
    Source: Collègue (robuste) - Version améliorée pour gérer les réponses tronquées
    """
    if not text:
        return text

    text_strip = text.strip()

    # Remove triple-backtick fenced blocks (même si tronqués à la fin)
    if text_strip.startswith("```"):
        lines = text_strip.splitlines()

        # Retirer la première ligne (```json ou ```)
        if len(lines) > 1:
            # Retirer aussi la dernière ligne si elle contient uniquement ```
            if lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
            else:
                # Pas de ``` à la fin, donc réponse probablement tronquée
                # On garde tout sauf la première ligne
                return "\n".join(lines[1:]).strip()

        # Fallback: juste supprimer tous les backticks
        return text_strip.strip("`").strip()

    # Remove single-line backticks
    if text_strip.startswith("`") and text_strip.endswith("`"):
        return text_strip.strip("`").strip()

    return text


def get_hybrid_prompt(company_name: str, raw_text: str) -> str:
    """
    Prompt hybride optimisé pour génération de données UI/UX riches.
    """
    return f"""You are a legal document analyzer specialized in Terms & Conditions analysis. Your goal is to create a comprehensive, user-friendly analysis for a public-facing dashboard.

Company: {company_name}
Document Type: Terms & Conditions / Terms of Service

TEXT TO ANALYZE:
---
{raw_text[:60000]}
---

IMPORTANT: Return ONLY valid JSON (no markdown, no explanations). The JSON will power an interactive web dashboard.

REQUIRED JSON STRUCTURE:
{{
  "metadata": {{
    "company_name": "{company_name}",
    "language": "en",
    "word_count": <total words>,
    "estimated_reading_time_minutes": <minutes to read at 200 wpm>,
    "last_updated": "<extract from doc if present, else 'Unknown'>",
    "document_type": "Terms of Service" | "Terms and Conditions" | "User Agreement"
  }},

  "executive_summary": {{
    "one_liner": "One sentence (max 20 words) describing overall risk level",
    "key_takeaways": [
      "3-5 bullet points of most important things users should know",
      "Each point should be actionable or clearly explain impact"
    ],
    "overall_verdict": "User Friendly" | "Standard" | "Concerning" | "Highly Problematic"
  }},

  "risk_scores": {{
    "overall": <0-100, overall risk score>,
    "data_privacy": <0-100, how risky for user data>,
    "user_rights": <0-100, how much rights user loses>,
    "termination_risk": <0-100, ease of account termination by company>,
    "legal_protection": <0-100, how vulnerable user is legally>,
    "transparency": <0-100, how clear/unclear the terms are>
  }},

  "key_flags": {{
    "data_sharing_third_party": true/false,
    "data_selling": true/false,
    "ip_rights_transfer": true/false,
    "content_monitoring": true/false,
    "termination_without_notice": true/false,
    "forced_arbitration": true/false,
    "class_action_waiver": true/false,
    "unilateral_changes": true/false,
    "broad_indemnification": true/false,
    "location_tracking": true/false
  }},

  "dangerous_clauses": [
    {{
      "id": "unique_id_1",
      "type": "DATA_PRIVACY" | "USER_RIGHTS" | "TERMINATION" | "LEGAL" | "CONTENT",
      "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
      "title": "Short title (5-8 words)",
      "summary": "What this clause means for users (1-2 sentences)",
      "exact_quote": "Exact text from document (if possible, 1-2 sentences max)",
      "user_impact": "Concrete impact on user (what they lose/risk)",
      "recommendation": "What user should do about this"
    }}
  ],

  "sections_breakdown": [
    {{
      "title": "Section title from document",
      "risk_level": "LOW" | "MEDIUM" | "HIGH",
      "summary": "2-3 sentence summary",
      "key_points": ["2-4 bullet points"]
    }}
  ],

  "comparison_to_industry": {{
    "overall_rating": "Better than average" | "Industry standard" | "Worse than average" | "Among the worst",
    "standout_good": ["Things this company does better than competitors"],
    "standout_bad": ["Things this company does worse than competitors"]
  }},

  "readability": {{
    "score": <1-10, where 1=very complex legal jargon, 10=plain English>,
    "grade_level": "Elementary" | "Middle School" | "High School" | "College" | "Graduate" | "Legal Expert",
    "estimated_comprehension": "Percentage of general public who could understand this"
  }},

  "action_items": [
    {{
      "priority": "HIGH" | "MEDIUM" | "LOW",
      "action": "Specific thing user should do",
      "reason": "Why this matters"
    }}
  ],

  "good_news": [
    "2-3 positive aspects of these terms (if any exist)",
    "Things the company does right or better than competitors"
  ]
}}

ANALYSIS GUIDELINES:
1. Be objective but user-focused (help users understand risks)
2. Use plain language in summaries (avoid legal jargon)
3. Provide exact quotes when identifying dangerous clauses
4. Focus on practical impact, not just legal theory
5. Include positive aspects to be balanced
6. Make recommendations actionable
7. Use severity levels consistently (CRITICAL = immediate concern)

Return ONLY the JSON object, no other text."""


def analyze_document_hybrid(txt_file: Path) -> dict:
    """
    Analyse un document avec l'approche hybride optimale.
    """
    # Lire le fichier
    with open(txt_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Identifier l'entreprise
    company_key = txt_file.stem.replace("_tc", "")

    if company_key not in companies_dict:
        print(f"[WARN] {company_key} not in config")
        company_name = company_key.replace("_", " ").title()
        company_info = {"name": company_name, "url": "unknown", "category": "unknown"}
    else:
        company_info = companies_dict[company_key]
        company_name = company_info["name"]

    print(f"[PROCESSING] {company_name}...")

    try:
        # Appel API avec paramètres optimaux
        message = client.messages.create(
            model="claude-sonnet-4-5",  # Modèle le plus récent
            max_tokens=8192,             # Maximum pour détails riches
            temperature=0,               # Déterministe/reproductible
            messages=[{
                "role": "user",
                "content": get_hybrid_prompt(company_name, raw_text)
            }]
        )

        response_text = message.content[0].text

        # Nettoyage robuste
        cleaned = clean_model_output(response_text)

        # Parser JSON
        structured_data = json.loads(cleaned)

        # Ajouter métadonnées supplémentaires
        structured_data["meta"] = {
            "source_url": company_info.get("url", "unknown"),
            "category": company_info.get("category", "unknown"),
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
            "raw_text_length": len(raw_text),
            "analyzer_version": "hybrid_v1.0"
        }

        # Calculer des métriques UI supplémentaires
        structured_data["ui_helpers"] = {
            "risk_color": get_risk_color(structured_data["risk_scores"]["overall"]),
            "severity_badge": get_severity_badge(structured_data["executive_summary"]["overall_verdict"]),
            "critical_issues_count": sum(1 for c in structured_data.get("dangerous_clauses", []) if c["severity"] == "CRITICAL"),
            "high_issues_count": sum(1 for c in structured_data.get("dangerous_clauses", []) if c["severity"] == "HIGH"),
            "reading_difficulty": get_difficulty_label(structured_data["readability"]["score"])
        }

        print(f"[OK] {company_name} (Risk: {structured_data['risk_scores']['overall']}/100)")
        return structured_data

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing failed for {company_name}")
        print(f"Response preview: {response_text[:200]}...")

        # Tentative d'extraction JSON
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            try:
                extracted = json.loads(cleaned[start:end+1])
                print("[RECOVERED] Extracted JSON successfully")
                return extracted
            except:
                pass

        return None

    except Exception as e:
        print(f"[ERROR] API call failed for {company_name}: {e}")
        return None


def get_risk_color(score: int) -> str:
    """Helper: Retourne couleur pour UI basée sur score."""
    if score >= 80: return "#DC2626"  # red-600
    if score >= 60: return "#EA580C"  # orange-600
    if score >= 40: return "#F59E0B"  # amber-500
    if score >= 20: return "#10B981"  # green-500
    return "#059669"  # green-600


def get_severity_badge(verdict: str) -> dict:
    """Helper: Badge pour UI."""
    badges = {
        "User Friendly": {"color": "green", "icon": "check-circle"},
        "Standard": {"color": "blue", "icon": "info-circle"},
        "Concerning": {"color": "orange", "icon": "alert-triangle"},
        "Highly Problematic": {"color": "red", "icon": "x-circle"}
    }
    return badges.get(verdict, {"color": "gray", "icon": "question"})


def get_difficulty_label(score: int) -> str:
    """Helper: Label lisibilité."""
    if score >= 8: return "Very Easy"
    if score >= 6: return "Easy"
    if score >= 4: return "Moderate"
    if score >= 2: return "Difficult"
    return "Very Difficult"


def analyze_text_content(text_content: str, company_name: str = "Unknown Company") -> dict:
    """
    Analyse un contenu textuel brut fourni en tant que chaîne de caractères.
    C'est la version que notre worker va utiliser.
    """
    print(f"[PROCESSING] Analyzing content for: {company_name}...")

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=8192,  # Augmenté de 4096 à 8192 pour permettre des réponses complètes
            temperature=0,
            messages=[{
                "role": "user",
                "content": get_hybrid_prompt(company_name, text_content)
            }]
        )

        response_text = message.content[0].text

        # Vérifier si la réponse a été tronquée par la limite de tokens
        stop_reason = message.stop_reason
        if stop_reason == "max_tokens":
            print(f"[WARNING] Response was truncated due to max_tokens limit for {company_name}")
            print(f"[INFO] Consider increasing max_tokens or reducing prompt complexity")

        # Debug: Vérifier si la réponse est vide
        if not response_text or not response_text.strip():
            print(f"[ERROR] Empty response from API for {company_name}")
            return {"error": "Empty response from Anthropic API"}

        cleaned = clean_model_output(response_text)

        # Debug: Vérifier si le nettoyage a tout supprimé
        if not cleaned or not cleaned.strip():
            print(f"[ERROR] Cleaned response is empty for {company_name}")
            print(f"[DEBUG] Original response (first 500): {response_text[:500]}")
            print(f"[DEBUG] Original response (last 500): {response_text[-500:]}")
            return {"error": "Response cleaning resulted in empty content"}

        print(f"[DEBUG] Cleaned text length: {len(cleaned)} chars")
        print(f"[DEBUG] First char of cleaned: {repr(cleaned[0]) if cleaned else 'EMPTY'}")
        print(f"[DEBUG] Last char of cleaned: {repr(cleaned[-1]) if cleaned else 'EMPTY'}")

        try:
            structured_data = json.loads(cleaned)
        except json.JSONDecodeError as json_err:
            print(f"[ERROR] JSON parsing failed for {company_name}: {json_err}")
            print(f"[DEBUG] Cleaned text (first 500 chars): {cleaned[:500]}")
            print(f"[DEBUG] Cleaned text (last 200 chars): {cleaned[-200:]}")

            # Si tronquée à cause de max_tokens, retourner une erreur plus explicite
            if stop_reason == "max_tokens":
                return {"error": f"Response truncated due to token limit. Increase max_tokens beyond 8192 or simplify the analysis."}

            return {"error": f"JSON parsing failed: {str(json_err)}"}

        # Enrichir les données comme avant
        structured_data["meta"] = {
            "source_name": company_name,
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
            "raw_text_length": len(text_content),
            "analyzer_version": "hybrid_v1.1_worker"
        }
        structured_data["ui_helpers"] = {
            "risk_color": get_risk_color(structured_data["risk_scores"]["overall"]),
            "severity_badge": get_severity_badge(structured_data["executive_summary"]["overall_verdict"]),
            "critical_issues_count": sum(1 for c in structured_data.get("dangerous_clauses", []) if c.get("severity") == "CRITICAL"),
            "high_issues_count": sum(1 for c in structured_data.get("dangerous_clauses", []) if c.get("severity") == "HIGH"),
            "reading_difficulty": get_difficulty_label(structured_data["readability"]["score"])
        }

        print(f"[OK] {company_name} (Risk: {structured_data['risk_scores']['overall']}/100)")
        return structured_data

    except Exception as e:
        print(f"[ERROR] API call or processing failed for {company_name}: {e}")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

def main():
    """Fonction principale."""
    print("=" * 70)
    print("HYBRID AI ANALYZER - Optimized for Frontend")
    print("=" * 70)

    # Créer dossier output
    STRUCTURED_DATA_DIR.mkdir(exist_ok=True)

    # Vérifier raw_data
    if not RAW_DATA_DIR.exists():
        print("[ERROR] raw_data/ not found")
        return

    # Lister fichiers
    txt_files = list(RAW_DATA_DIR.glob("*.txt"))

    if not txt_files:
        print("[ERROR] No .txt files in raw_data/")
        return

    print(f"\nFound {len(txt_files)} files to analyze\n")

    # Statistiques
    success = 0
    failed = 0

    # Analyser chaque fichier
    for txt_file in txt_files:
        result = analyze_document_hybrid(txt_file)

        if result:
            # Sauvegarder JSON
            output_file = STRUCTURED_DATA_DIR / f"{txt_file.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            success += 1
        else:
            failed += 1

        # Pause pour rate limiting
        time.sleep(1)

    # Résumé
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"SUCCESS: {success}")
    print(f"FAILED: {failed}")
    print(f"OUTPUT: {STRUCTURED_DATA_DIR}/")
    print("\nData ready for frontend integration!")


if __name__ == "__main__":
    main()
