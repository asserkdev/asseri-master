# Arabic Grammar Notes

Phase 1 implementation now includes:

- Diacritics removal for robust matching.
- Alef/Hamza normalization (إ/أ/آ/ٱ -> ا).
- Final letter normalization (ى -> ي, ة -> ه for matching pipeline).
- Arabic-Indic and Eastern Arabic digits normalization.
- Tatweel removal.
- Basic punctuation normalization (Arabic question mark/comma).

Current limitations (by design in phase 1):

- No full morphological analysis.
- No syntactic parsing tree.
- No dialect-specific grammar model.

Planned next phases:

- Lemma-level normalization.
- Better dialect handling.
- Arabic-specific intent confidence calibration.
