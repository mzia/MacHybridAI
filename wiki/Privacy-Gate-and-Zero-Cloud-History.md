# Privacy Gate (PII Guardian) and Zero Cloud History

`MacHybridAI` is architected around two strict privacy guarantees:
1. **On-Device PII Guardian Privacy Gate**: Sensitive personal and corporate identifiers are detected and masked on your Mac *before* any cloud model is called, and restored locally on your Mac afterward.
2. **Zero Cloud AI History Retention**: Cloud calls enforce stateless execution (`store=False`, `X-No-Store: true`, and Temporary Chat `disableMemory=1` on M365 Copilot), while local prompt history is stored on your Mac or in your personal iCloud Drive under your retention policy.

---

## 1. Dual-Layer On-Device PII Detection

`MacHybridAI` combines two local detection engines that run 100% on-device:
- **`SwiftNativeGuardian` (macOS `NaturalLanguage` `NLTagger`)**: High-accuracy on-device Named Entity Recognition for `PERSON` (`personalName`), `ORG` (`organizationName`), and `PLACE` (`placeName`).
- **`PIIGuardian` (High-Precision Pattern & Checksum Scanner)**:
  - `EMAIL`: RFC-5322 email addresses
  - `PHONE`: US & international phone numbers
  - `SSN`: US Social Security Numbers
  - `CREDIT_CARD`: Luhn-checksum-validated credit card numbers
  - `SECRET`: API keys & tokens (`AIza...`, `sk-...`, `ghp_...`, `AKIA...`, Bearer tokens)
  - `IPV4`: IPv4 network addresses
  - `CUSTOM_TERM`: User-defined project code names, client names, or internal terms

---

## 2. Guardian Policies

You can switch the active **Privacy Gate Policy** at any time in the top toolbar or under the **Privacy Gate (PII)** tab:

| Policy | Behavior Before Cloud Call | Behavior After Cloud Response |
| :--- | :--- | :--- |
| **`reversible_mask`** *(Recommended)* | Replaces each entity with a numbered stand-in token (`[PERSON_1]`, `[EMAIL_1]`, `[PHONE_1]`) and stores the mapping in the local in-memory `PIIVault`. | Automatically restores `[PERSON_1]` -> real name in the final response on your Mac. |
| **`strict_redact`** | Permanently strips PII with `[REDACTED_EMAIL]`, `[REDACTED_SSN]`, etc. | Never restores original values. |
| **`force_local_on_pii`** | If *any* PII is detected in the prompt or attached files, automatically blocks the cloud call and routes the entire task to **Station 1 (Fully Local Apple Silicon MLX)**. | Executed 100% on-device; nothing leaves your Mac. |

---

## 3. Verifying Privacy with the Live PII Inspector & Execution Receipts

1. **Live Composer Shield**: As you type in the chat composer or Menu Bar Quick-Prompt, a live badge displays how many PII entities will be masked before any cloud request is sent.
2. **Interactive Privacy Gate Inspector (Tab 3)**: Paste any document or prompt to preview side-by-side:
   - **Sanitized Cloud Payload** (what the cloud model actually sees)
   - **Restored Local Output** (what you see after local `PIIVault` restoration)
3. **Per-Message Execution Receipt**: Every assistant response includes an expandable **Execution Receipt** recording:
   - Compute Mode executed (`local` vs `hybrid`)
   - Local model used (`mlx-community/gemma-3-4b-it-4bit (on this Mac)`)
   - Cloud model used (`not used`, `gemini-3.8-flash`, `m365_copilot:gpt-5.5-think-deeper`, etc.)
   - Exact count & categories of PII masked and restored
   - Verification of `Nothing Left Mac` / `Zero Cloud Retention`

---

## 4. Local Mac & iCloud Drive Prompt History with Auto-Delete

In **History & iCloud Sync (Tab 2)** or the Menu Bar popover, you control where your conversations live and when they expire:
- **Storage Location**:
  - **Local Mac (`~/.machybrid/history/`)**: Stored only on your local drive with optional at-rest encryption.
  - **iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/MacHybridAI/`)**: Synced privately across your Apple devices via iCloud Drive.
- **Auto-Delete Retention Policy**:
  - `Auto-Delete after 24 Hours`
  - `Auto-Delete after 7 Days`
  - `Auto-Delete after 30 Days` *(Default)*
  - `Auto-Delete after 90 Days`
  - `Never Delete`
