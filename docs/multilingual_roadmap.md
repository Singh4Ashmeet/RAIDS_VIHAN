# Multilingual Support - RAID Nexus

## Current Implementation
RAID Nexus performs offline language detection before running the NLP triage pipeline. Complaint text is checked with `langdetect`, short or non-alphabetic inputs are treated as unreliable, and all uncertain language detections are flagged for human review.

The current offline translation scope is intentionally limited to English and Hindi. English complaints pass through unchanged. Hindi complaints use a local Hindi-to-English path based on Helsinki-NLP Opus-MT, with an emergency Hinglish glossary for common Latin-script Hindi phrases such as `seene mein dard`, `sans nahi`, and `behosh`. Translated triage results are always flagged for human review, regardless of classifier confidence.

For other detected Indian languages, RAID Nexus does not attempt translation in the current build. The system records the detected language, forces human review, and falls back to the keyword safety path instead of downloading large additional models or silently misclassifying the complaint.

## Limitations
1. The NLP classifier (`facebook/bart-large-mnli`) is English-only. Hindi inputs must first pass through offline translation, so classification quality depends on the translated complaint.

2. Offline translation is currently enabled only for Hindi. Tamil, Telugu, Bengali, Kannada, Marathi, Gujarati, Punjabi, Malayalam, and Urdu inputs are detected and escalated for human review but are not translated automatically in this build.

3. `langdetect` accuracy drops below 70% for very short texts and mixed-language inputs. Low-confidence language detection therefore forces human review even when the complaint might still be understandable to a dispatcher.

## Production Roadmap

### Phase 1 - Offline Hindi Translation (IMPLEMENTED)
Helsinki-NLP Opus-MT provides offline, zero-API-key Hindi-to-English neural machine translation. RAID Nexus preloads only the Hindi model because it is the most likely non-English language for the current prototype cities and avoids large multi-model downloads during local development.

Coverage:
- English: passthrough, no translation required
- Hindi: dedicated `Helsinki-NLP/opus-mt-hi-en` model
- Hinglish: emergency glossary for common Latin-script Hindi complaint phrases
- Other languages: detection plus forced human review, no automatic translation

Limitations:
1. The Hindi model is trained on general-domain text. Emergency medical colloquialisms may not translate accurately.
2. First use requires the Hindi model download. Subsequent uses are fully offline.
3. Translation adds CPU inference latency for Hindi complaints.

Mitigation: All translated triage results are flagged for human review. Translation is a best-effort assist, not a trusted classification.

### Phase 2 - Additional Offline Indian-Language Models
If runtime constraints allow, add Helsinki-NLP models incrementally for Bengali, Urdu, Marathi, and the Dravidian family model for Tamil, Telugu, and Kannada. Each language should be enabled only after local download time, memory use, and translation quality are verified.

### Phase 3 - Bhashini/Dhruva API (Future, when access available)
Bhashini ([https://bhashini.gov.in/ulca](https://bhashini.gov.in/ulca)) offers government-grade translation for 22 scheduled Indian languages with better domain coverage than general-purpose models. Registration requires an institutional AISHE code. When available, a Bhashini API client can implement the same translator interface while keeping the offline Hindi path as a fallback.

### Phase 4 - IndicBERT Fine-tuning
IndicBERT (AI4Bharat, 2023) is a multilingual BERT model pre-trained on 12 Indian languages. Fine-tuning on emergency domain text would enable direct classification without translation. This requires an annotated emergency complaint dataset in Indian languages, which does not currently exist publicly and would likely require partnerships with EMS operators.

### Phase 5 - Speech-to-Text Integration
Real emergency calls are voice, not text. A future mobile SOS flow could accept audio, transcribe it into text, and pass the transcript through the same multilingual triage path.

## Language Access and Equity
Non-English speakers in India are disproportionately represented in lower-income and peripheral urban zones. If the triage system performs worse on non-English inputs, it compounds the geographic equity issues identified in the fairness analysis. The language detection, Hindi translation, and forced-human-review approach is designed to fail safely rather than fail silently. That is a deliberate ethical design choice.
