# Inceputul proiectului

Plecarea conteaza foarte tare asa ca tregbuie stabilit totul de la inceput
Propun construirea unei aplicatii care sparge query ul in multe subunitati care sa fie testate individual si construirea unui sistem unic de premiere a fiecarei companii din baza de date.

## Probleme punctuale:
### PROBLEMA 1 - Neconcordanta intre query si baza de date
- Datele din query vor sa caute ceva, dar cu alt nume sau pur si simplu nu s a oferit un data pinpoint(spre exemplu in query scrie: "logistics company in Balkans or Romania", iar in baza de date am o companie disponibila la Brasov)

- Confirmarea problemei: Dupa o analiza pe baza de date folosind Gemini, am observat ca datele intr-adevar sunt salvate intr un mod non-general, astfel trebuie implementata o asa zisa: "metoda de normalizare" ca baza de date si query ul sa vorbeasca aceeasi limba

### PROBLEMA 2 - Campurile scrie "la liber"

- Datele din baza de date au campuri care trebuie doar **CITITE**. O companie poate fi obiectiv in Brasov, iar daca query ul zice Balcani, Europa, Romania, tot in Brasov ramane sau daca e companie publica sau nu, e ceva fix. Exista totusi campuri care sunt scrise de un om si trebuie **INTELESE**, o descriere, un scop, care e subiectiv, difera foarte tare de cine scrie si trebuie inteleasa acea descriere in mod constient.

### PROBLEMA 3 - Campuri lipsa in baza de date

- Datele din baza de date au campuri care nu contin informatie, problema apare cand un query cere intentionat acea informatie. Ce sa faca LLM ul aici? sa anuleze de tot compania sau sa primeasca "benefit of the doubt", iar in cazul acesta, cat de permisiv sa fie cu acest concept?

- Trebuie luata o decizie in directia nivelului de permisiune(toleranta): dacă lipsesc date si esti strict, pierzi firme care s-ar fi potrivit. Dacă ești permisiv, adaugi firme care nu se potrivesc.

### PROBLEMA 4 - Trade-off (viteza vs acuratete vs cost)

- Agentul trebuie sa aiba undeva un trade-off. Variabilele sunt:
viteza, cost si acuratete. Problema se pune: cand trebuie sa se modifice overheadurile la toate 3? in functie de ce si cand.

- Un call catre un agent extern este foarte folositor dar costisitor, asa ca trebuie folosit, dar cu foarte multa grija si atentie pentru a nu pierde resurse. Problema apare: pentru ce firme/situatii merita apelul extern, astfel incat sa nu fie un compromis foarte mare la cost?
