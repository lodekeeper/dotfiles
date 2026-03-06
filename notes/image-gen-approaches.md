# Image Generation Approaches — 2026-02-26

## Summary
Explored multiple approaches for generating images without API credits. The ChatGPT browser pipeline works but produces low-quality results via DALL-E.

## Approaches Tried

### 1. OpenAI API (gpt-image-1) ✅ WORKING
- **Status:** Unblocked — Nico topped up $20 (2026-02-26)
- **Quality:** Best available (sharp, clean text)
- **Cost:** ~$0.04-0.08/image (high quality 1536x1024)

### 2. Gemini API (Nano Banana Pro) ❌
- **Status:** Blocked — both API keys exhausted (quota)
- **Quality:** Good
- **Fix:** Wait for quota reset or new Google account

### 3. Oracle CLI → ChatGPT ❌
- **Status:** Oracle extracts text only, can't capture generated images
- **Issue:** Oracle CLI scrapes text responses; when ChatGPT generates an image via DALL-E, it appears inline but Oracle has no mechanism to download it

### 4. Oracle Bridge (direct browser) ❌
- **Status:** Bridge crashes with EPIPE error mid-generation
- **Issue:** rebrowser-playwright pipe disconnects during long-running image gen

### 5. Playwright → ChatGPT Web UI ✅ (works, low quality)
- **Status:** Working pipeline!
- **Script:** `/tmp/chatgpt-image-gen.py` (v1), `/tmp/chatgpt-image-gen-v2.py` (v2, untested due to OOM)
- **Flow:** Launch headless Chrome → inject auth cookies → navigate to chatgpt.com → type prompt → wait for DALL-E → download image via fetch()
- **Issue:** Images are blurry/low quality — ChatGPT web uses older DALL-E model, not gpt-image-1
- **Image URL pattern:** `chatgpt.com/backend-api/estuary/content?id=file_...&sig=...`
- **Cookie:** `__Secure-next-auth.session-token` from Nico's ChatGPT Pro account
- **Note:** v2 script (click-to-expand for full res) kept getting OOM killed due to Chrome + pointer compression container memory pressure

### 6. Free APIs (Pollinations, HuggingFace, Pixazo) ❌
- **Status:** All require auth, rate-limited, or blocked
- **Not viable** without accounts

### 7. Sora (video gen) 🔲 Not tested
- **Status:** Same browser approach should work on sora.com
- **Potential:** Could generate short clips via ChatGPT Pro

## Recommendations
1. **Best ROI:** Top up OpenAI ~$5 → unlocks gpt-image-1 API (sharp images), Whisper (transcription), and vision
2. **Free option:** Playwright→ChatGPT pipeline works but DALL-E quality is poor for memes (blurry, bad text rendering)
3. **Future:** Save the Playwright script as a proper skill once quality improves or API is available
