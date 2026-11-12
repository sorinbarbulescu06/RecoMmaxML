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

- Mentiune speciala: Daca query-ul nu mentioneaza adresa sau numarul de angajati sa zicem, ideea de "benefit of the doubt" pica pentru campul respectiv, devine un camp neimportant.

### PROBLEMA 4 - Trade-off (viteza vs acuratete vs cost)

- Agentul trebuie sa aiba undeva un trade-off. Variabilele sunt:
viteza, cost si acuratete. Problema se pune: cand trebuie sa se modifice overheadurile la toate 3? in functie de ce si cand.

- Un call catre un agent extern este foarte folositor dar costisitor, asa ca trebuie folosit, dar cu foarte multa grija si atentie pentru a nu pierde resurse. Problema apare: pentru ce firme/situatii merita apelul extern, astfel incat sa nu fie un compromis foarte mare la cost?

## Idei de implementare

### 1y division:
 "Spargem" query ul in informatii separate si vedem ce putem alege din ele.

 - Cum? : Spargem query ul in conditii (secvente **CONTEXTUALE**) ca sa putem dobandi informatii pe care sa le comparam cu baza de date printr sistem de: local ai si api call.
 - De ce 2 modele ai? : Primul pas caută argumente **SIGURE** și **CLARE** care îngustează aria de căutare în baza de date, iar pentru ce nu înțelege spune simplu **NU ȘTIU**. API call ul va oferi context si un mod mai inteligent de a citi query ul, in locurile unde agentul local va avea dificultati sa acopere un caz mai neconcludent. El va stoca si cateva informatii cheie care o sa ne ajute la a identifica companiile suitable pe baza lor.

 ### Prima Triere:
 Dupa apelarea celor 2 modele vom primi niste date concludente (SI OBIECTIVE) pe care sa le folosim ca sa micsoram numarul de potentiale companii. Campurile intrepretabile cum ar fi website-ul sau descrierea vor ramane momentan pe pauza.

 ### Start lucru:
 Incepem lucrul prin a construi initial codul folosind principii ale programarii orientate pe obiecte ca sa generam o baza de lucru al query ului
 
 Structura: Vreau ca proiectul sa aiba mai multe etape de colectare a conditiilor pt a usura la final trierea finala, astfel voi incepe sa implementez rand pe rand aceste etape.

 Incep cu API call-ul pentru ca e cel mai simplu de testat