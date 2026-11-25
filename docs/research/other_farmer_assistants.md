# What other farmer assistants learned

Research notes, written 25 Nov 2026. These are for planning only; the bot never reads them.
Figures are as published. Self-reported or unverified ones are marked as such.

| Assistant | What it is | What we learn |
|---|---|---|
| **Farmer.CHAT** (Digital Green) | WhatsApp/Telegram/app, incl. Telugu; voice → text → English → RAG over expert-vetted content → back. 15,000+ users, 300,000+ queries. [paper](https://arxiv.org/html/2409.08916) | About 75% of queries answered; 66% of misses were "not in our documents". About 80% of answers were rated faithful to sources. Answers were too technical for less-educated farmers. Follow-up buttons drove over 45% of interactions. Trust grew when advice worked on the farmer's own field. |
| Farmer.CHAT pesticide follow-up | 4 agronomists reviewed about 12k Q&A pairs. [paper](https://arxiv.org/html/2603.03294) | A "red-line" check rejects answers with banned pesticides or missing safety steps. 1.4–3.2% of pesticide answers contradicted the experts. Pesticide approvals go out of date and need re-checking. |
| **Saagu Baagu** (Telangana + Digital Green) | Telugu WhatsApp bot that started with chilli; crop-stage alerts; 7,000 growers. [article](https://www.deeplearning.ai/the-batch/ai-elevates-chili-farming-in-india-with-smarter-yields) | Reported 9% less pesticide and 8% higher prices (no control group, unverified). |
| **Kisan e-Mitra** (GoI + Wadhwani AI) | PM-KISAN scheme questions only; 11 languages; voice. [Wadhwani AI](https://www.wadhwaniai.org/empowering-millions-of-indian-farmers-with-instant-ai-chatbot-support/) | FAQs are built from real queries and shown as tap buttons. |
| **Kisan Call Centre** | Human helpline. [study](https://ageconsearch.umn.edu/record/367932/files/Raja4242024AJAEES114511.pdf) | In one Karnataka survey 74% had never used it, and only 44% were highly satisfied. Don't rely on it as the only fallback. |
| **Plantix** | Photo diagnosis app. [CABI/ICRISAT field test](https://blog.plantwise.org/2020/06/19/teaching-an-app-to-help-farmers/) | Got the first diagnosis right in about 51% of 900 field cases. Root and collar rots are hard to see in photos. |
| **KissanAI / Dhenu** | Farm-tuned small models with Telugu voice. [news](https://analyticsindiamag.com/kissanai-releases-dhenu-llama-3-an-indic-llm-for-farmers/) | No independent accuracy data. |
| **Jugalbandi** (AI4Bharat/Microsoft) | WhatsApp, voice ↔ text ↔ GPT. [Microsoft](https://news.microsoft.com/en-in/features/with-help-from-next-generation-ai-indian-villagers-gain-easier-access-to-government-services/) | Its own team says the speech and translation models make errors. |
| **AIEP cross-project review** | FarmerChat, Gramvaani, Karya and others. [paper](https://arxiv.org/html/2601.11537v1) | Speech-to-text mishears farm terms ("dhan" (paddy) translated as "money"). Voice replies take 5–10 s or more. NPS was about 60. The top complaint was incomplete answers. About 33% of less-educated farmers found answers hard to understand. |
| **Telugu speech-to-text test** (Digital Green, farm audio) | [paper](https://arxiv.org/html/2602.03868v2) | Word error rates: Google 33%, Gemini 2.5 Pro 38%, Sarvam 47% (better on farm words), Meta MMS 68%. Bhashini wasn't tested. |
| **ANGRAU chatbot** (AP) | Telugu WhatsApp, rule-based; about 3,000 farmers. [article](https://www.smatbot.com/blog/?p=9013) | Shows that ANGRAU and RBK staff already use WhatsApp; they are possible partners. |
| **eSagu** (IIIT Hyderabad) | Photos sent to human experts. [page](https://web2py.iiit.ac.in/research_centres/default/view_area/103) | An expert-in-the-loop model; self-reported benefit of Rs 3,820/acre. |
| **CottonAce** (Wadhwani AI) | Photographs of pest traps give spray timing. [page](https://wadhwaniai.org/cottonace_k21) | 6,000+ farmers. A possible later idea for thrips sticky traps. |

Could not verify: AgriBuddy, an official AP RBK AI chatbot, Bhashini's Telugu error rate, any
chilli-specific accuracy figure.

What we're doing about it is listed in [PROJECT_STATUS.md](../../PROJECT_STATUS.md) section 8.
