# RecoMMaxML

<img src="gif/Demo.gif" alt="Learning Bird" width="600">

RecoMMaxML este o aplicație inteligentă care transformă un query în limbaj natural într-un set de filtre structurate pentru a găsi, filtra și scora cele mai relevante companii B2B dintr-o bază de date. 

Aplicația rezolvă neconcordanțele dintre modul în care utilizatorii formulează căutările și modul în care datele sunt stocate, aplicând un echilibru optim între viteză, cost și acuratețe. Pentru detalii tehnice aprofundate și decizii de arhitectură, consultați fișierul `WRITEUP.md`.

## 🚀 Cum se utilizează

Proiectul este cross-platform și rulează direct folosind scripturile de automatizare incluse, care gestionează crearea mediului virtual și instalarea dependențelor.

**Cerință prealabilă:** Copiați fișierul `.env.example` în `.env` și adăugați cheia `GEMINI_API_KEY`. (Scripturile vă vor ghida automat dacă uitați acest pas).

### Windows
Folosiți executabilul `run.bat` din rădăcina proiectului:
*   **Mod Interactiv:** `run` (Introduceți query-urile manual de la tastatură).
*   **Mod Batch:** `run --file lista_query.txt` (Procesează automat o listă de query-uri).

### Mac / Linux
Folosiți scriptul `run.sh` (necesită drepturi de execuție: `chmod +x run.sh`):
*   **Mod Interactiv:** `./run.sh`
*   **Mod Batch:** `./run.sh --file lista_query.txt`

---

## 📂 Structura rezultatelor (Output)

Pentru o experiență de utilizare curată, consola va afișa doar informațiile esențiale (Numele companiei și Website-ul). Toate datele tehnice, deciziile algoritmului și logurile sunt salvate automat după fiecare rulare într-un director nou structurat astfel: `results/$datetime/`

*   `log.txt`: Jurnalul detaliat al execuției (condiții extrase, status API, erori).
*   `top.txt`: Rezumatul curat al afișajului din consolă.
*   `query_list.jsonl`: Istoricul rulării cu statusul și metricile de timp pentru fiecare query.
*   `company_lists/`: Fisiere `.jsonl` per query ce conțin profilele complete ale companiilor calificate.
*   `telemetry_list/`: Fișiere `.json` cu detalii transparente despre modul în care s-a calculat scorul fiecărei firme.

---

## ⚙️ Metoda de Lucru (Pipeline-ul de Procesare)

Sistemul funcționează într-un flux de 3 etape principale:

### 1. Query Division (Spargerea Query-ului)
Query-ul este segmentat în condiții contextuale testate individual. Se bazează pe un model hibrid:
*   **Local (Reguli / Regex):** Extrage la viteză maximă argumentele sigure (ex: număr angajați, locație, venit).
*   **API Call (LLM):** Oferă context inteligent și expansiune semantică pentru criteriile interpretabile (industrii, oferte, piețe țintă).

### 2. Trierea (Hard Knockout)
Filtrează masiv baza de date folosind informațiile obiective extrase (prin metoda Batching).
*   Folosește principiul **"Benefit of the Doubt"**: Dacă o firmă are un câmp obiectiv lipsă (ex: venit null), este păstrată ca potențial candidat.
*   Codurile **NAICS** și potrivirile lexicale de bază funcționează ca filtre *hard* pentru a elimina zgomotul evident.

### 3. Scoring-ul (Notarea Semantică)
Clasează companiile trecute de filtrul Hard pe baza relevanței.
*   **Normalizare Matematică Dinamică:** Plafonul de scor se ajustează în funcție de numărul de criterii cerute de query.
*   **Departajare Fină:** Egalitățile sunt sparte prin *Term Frequency* și un *Bonus de Densitate* a profilului companiei.
*   **Dynamic Thresholding:** Se evaluează scorul liderului și se aplică un prag (cutoff) pentru a tăia "coada" listei, returnând doar firmele cu adevărat relevante, fără a umple artificial clasamentul.