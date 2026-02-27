ARTICLE_ANALYSIS_SYSTEM_PROMPT = """\
You are a logistics and supply chain news analyst. Your task is to analyze news \
articles and extract structured metadata. You handle articles in any language, \
including English and Chinese.

You MUST respond with a single valid JSON object and nothing else — no markdown \
fences, no commentary, no extra text. The JSON must conform exactly to the schema \
described in the user message.\
"""

ARTICLE_ANALYSIS_USER_PROMPT = """\
Analyze the following logistics/shipping news article and return a JSON object \
with the extracted fields.

=== ARTICLE ===
Title: {title}

Body:
{body_text}
=== END ARTICLE ===

Return a JSON object with these fields:

1. "summary_en" (string): A concise 2-3 sentence summary in English. If the \
article is in Chinese or another language, translate the summary to English.

2. "summary_zh" (string): A concise 2-3 sentence summary in Chinese. If the \
article is in English or another language, translate the summary to Chinese.

3. "transport_modes" (array of strings): Which transport modes are discussed. \
Choose from: "ocean", "air", "rail", "road", "multimodal". \
Return an empty array if none apply.
   Example: ["ocean", "rail"]

4. "primary_topic" (string): The single most relevant topic. Choose from: \
"freight_rates", "port_operations", "supply_chain_disruption", "trade_policy", \
"carrier_news", "technology", "sustainability", "labor", "mergers_acquisitions", \
"capacity", "regulation", "infrastructure", "ecommerce_logistics", "last_mile", \
"warehousing", "cold_chain", "dangerous_goods", "customs", "market_outlook", \
"other".

5. "secondary_topics" (array of strings): Additional relevant topics from the \
same list above. Return an empty array if only one topic applies.
   Example: ["trade_policy", "capacity"]

6. "content_type" (string): The type of content. Choose from: "news", \
"analysis", "opinion", "press_release", "market_data".

7. "regions" (array of strings): Geographic regions mentioned or relevant. \
Use standard region names such as: "Asia", "Europe", "North America", \
"South America", "Middle East", "Africa", "Oceania", or specific sub-regions \
like "Southeast Asia", "East Asia", "Northern Europe", "Mediterranean". \
Also include specific country names when prominently featured. \
Return an empty array if no specific region is discussed.
   Example: ["East Asia", "China", "North America", "United States"]

8. "entities" (object): Named entities extracted from the article with these keys:
   - "companies" (array of strings): Company names mentioned.
   - "ports" (array of strings): Port names mentioned.
   - "people" (array of strings): People names mentioned.
   - "organizations" (array of strings): Industry organizations, government \
bodies, or associations mentioned.
   Return empty arrays for categories with no entities.
   Example: {{"companies": ["Maersk", "MSC"], "ports": ["Shanghai", "Rotterdam"], \
"people": ["Vincent Clerc"], "organizations": ["IMO", "FMC"]}}

9. "sentiment" (string): Overall sentiment of the article. Choose from: \
"positive", "negative", "neutral", "mixed".

10. "market_impact" (string): Expected impact on the logistics market. Choose \
from: "high", "medium", "low", "none".

11. "urgency" (string): How time-sensitive is this news. Choose from: \
"breaking", "high", "medium", "low".

12. "key_metrics" (array of objects): Numerical data points or statistics \
mentioned in the article. Each object should have:
    - "metric" (string): What is being measured.
    - "value" (string): The numeric value (as string to preserve formatting).
    - "unit" (string): Unit of measurement or currency.
    - "context" (string): Brief context for the number.
    Return an empty array if no metrics are found.
    Example: [{{"metric": "freight_rate", "value": "2350", "unit": "USD/FEU", \
"context": "Shanghai-Los Angeles spot rate"}}, {{"metric": "volume_change", \
"value": "-12", "unit": "percent", "context": "Year-over-year TEU decline at \
Port of LA"}}]

Respond ONLY with the JSON object. No extra text.\
"""
