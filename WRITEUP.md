# Inceputul proiectului

Plecarea conteaza foarte tare asa ca tregbuie stabilit totul de la inceput
Propun construirea unei aplicatii care sparge query ul in multe subunitati care sa fie testate individual si construirea unui sistem unic de premiere a fiecarei companii din baza de date.

## Probleme punctuale:
### PROBLEMA 1 - Neconcordanta intre query si baza de date
- Datele din query vor sa caute ceva, dar cu alt nume sau pur si simplu nu s a oferit un data pinpoint(spre exemplu in query scrie: "logistics company in Balkans or Romania", iar in baza de date am o companie disponibila la Brasov)

- Confirmarea problemei: Dupa o analiza pe baza de date folosind Gemini, am observat ca datele intr-adevar sunt salvate intr un mod non-general, astfel trebuie implementata o asa zisa: "metoda de normalizare" ca baza de date si query ul sa vorbeasca aceeasi limba

### PROBLEMA 2 - Campurile scrise "la liber"

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

### Query division:
 "Spargem" query ul in informatii separate si vedem ce putem alege din ele.

 - Cum? : Spargem query ul in conditii (secvente **CONTEXTUALE**) ca sa putem dobandi informatii pe care sa le comparam cu baza de date printr sistem de: local ai si api call.
 - De ce 2 modele ai? : Primul pas caută argumente **SIGURE** și **CLARE** care îngustează aria de căutare în baza de date, iar pentru ce nu înțelege spune simplu **NU ȘTIU**. API call ul va oferi context si un mod mai inteligent de a citi query ul, in locurile unde agentul local va avea dificultati sa acopere un caz mai neconcludent. El va stoca si cateva informatii cheie care o sa ne ajute la a identifica companiile suitable pe baza lor.

 ### Prima Triere:
 Dupa apelarea celor 2 modele vom primi niste date concludente (SI OBIECTIVE) pe care sa le folosim ca sa micsoram numarul de potentiale companii. Campurile intrepretabile cum ar fi website-ul sau descrierea vor ramane momentan pe pauza.

 # Etapa 1 : Query Divizion
 Incepem lucrul prin a construi initial codul folosind principii ale programarii orientate pe obiecte ca sa generam o baza de lucru al query ului
 Am facut un package care sa contina viitoarele trieri(cea locala si cea cu api call)
 
 Structura: Vreau ca proiectul sa aiba mai multe etape de colectare a conditiilor pt a usura la final trierea finala, astfel voi incepe sa implementez rand pe rand aceste etape.

 Incep cu API call-ul pentru ca e cel mai simplu de testat.

 ## Rezolvari ale problemelor in cadrul implementarii
 #### Separation of Concerns si SSOT
 - Am facut un package care o sa imi tina loc de "main lobby ul" aplicatiei. Acesta are 2 fisiere si 1 tine loc de dictionar global (config) iar celalalt face primele verificari : cea locala(inca nu e implementata) si cea cu apel. Dupa api call, fiecare camp care e returnat de LLM va fi de tip Condition, deci primim mereu un format valid (continutul local poate fi gresit)
  - Am eliminat orice date "hardcodate" (magic strings). Tot ce ține de mediu (API keys, versiuni de modele) este gestionat exclusiv dintr-un fișier .env și validat global printr-o clasă unică Config

#### Benefit of the doubt
 - Dacă un query nu menționează explicit un câmp obiectiv (ex: nu se specifică anul fondării sau numărul de angajați), sistemul marchează automat acel câmp ca fiind "fantomă". Astfel, la faza de filtrare a companiilor, motorul va ști să nu penalizeze firmele care au employee_count: null, pentru că acel câmp nici măcar nu a fost o cerință a utilizatorului.

 #### Brute-Mode si Fault Tolerance
 - Un API call eșuat nu va opri aplicația. Eroarea este prinsă (try/except), se aplică condițiile fantomă pe tot query-ul, iar execuția merge mai departe.

 - Brute-Mode: Am construit sistemul astfel încât să poată rula chiar și fără o cheie API configurată în .env. Dacă un evaluator clonează repo-ul și nu introduce o cheie, se detectează lipsa ei, se notifică utilizatorul printr-un avertisment clar în consolă și continuă procesarea strict pe baza faza 1 (Local), implementand astfel un Graceful Degradation al sistemului, în loc de un crash.

 #### Expansiunea Semantica
 - Pentru a evita răspunsurile inconsistente și lente, faza 2 folosește API-ul Gemini forțat printr-o schemă Pydantic strictă. LLM-ul nu mai trebuie să ghicească firme; el doar primește bucata de query neînțeleasă local (query.remainder) și o sparge în array-uri semantice.
De exemplu, pentru "packaging materials", modelul a fost instruit să facă expansiune semantică (adaugă automat: ['bottles', 'jars', 'tubes']), crescând enorm șansele de match pe textul liber din descrierile companiilor.

----
Acum ca API call-ul a fost implementat si e functional trebuie sa incepem constructia modelului local, care va avea 3 functii foarte importante:
 
 - Cautare de flaguri boolene: cauta daca firma e publica sau nu, sau ramane neconcludent daca nu gaseste

 - Cautare anul fondarii: Se va uita dupa cuvinte cheie care sa mentioneze anul fondarii, si dupa dupa acest an ca sa formeze un regex

 - Cautare metrici cantitative(venit si angajati) : va forma tot un regex despre aceste date 

#### BONUS: Metoda-Brute-Force
In cazul in care API key ul nu exista in fisier, modul de rulare va functiona intr o norma 100% locala pe keywords hardcodate.

## Rezultate teste 
Am rulat 3 teste folosind cele 12 query uri oferite ca exemplu(rezultatele se afla in `assets/`):
1. NoLocalJustApi - se foloseste doar apelul extern, iar intern nu se ia nicio decizie
2. LocalAndApi - se foloseste si apelul local si cel extern
3. LocalNoAPI - se foloseste exclusiv apelul local pe modul Brute-Force pentru a da grep la cat mai multa informatie

Rezultatele sunt unele decente dar se pot observa cateva erori si capacitati de imbunatatire

## Probleme si solutii la implementarea actuala:

#### Eroare la apelarea API-ului
 - Daca cumva API - ul intoarce eroarea 503, adica nu a putut fi accesat modelul, asta inseamna ca metoda brute-force nu a fost apelata deloc in stagiul incipient. De exemplu, la „Clean energy startups...“ API-ul a dat 503, nu s-a extras nimic și au trecut toate cele 477 de firme. Acum trec 0.
   + `Rezolvare`: Folosim catch exception si daca este o eroare de genul, se apeleaza de urgenta modul brute-force pentru a nu pierde timpul si informatie pretioasa.

 - Am corectat regula care decide dacă mai e nevoie de API (ignor punctuația și cuvintele de legătură). Pe cele 207 de query-uri, rata de apeluri a rămas 100%, pentru că fiecare query conține o parte semantică (industrie) pe care agentul local nu o poate extrage. Concluzie: API-ul nu e un „plan B“, ci o parte necesară a sistemului, iar economia reală de cost ar veni dintr-un cache sau dintr-un model local pentru industrii, nu din reguli mai bune.

 #### Nivelul de intelegere al unui query
 - La rulare a aparut problema in care api ul si nici agentul local nu au reusit sa capteze nicio informatie, iar din cauza asta nu s a facut nicio triere asupra bazei de date.(programul considera ca toate firmele au sansa sa fie compatibile, cu toate ca nu au nicio informatie de comparatie)
   - `Rezolvare` : fiecare query primeste un status (`understood`, `partial`, `failed`) in functie de ce conditii active reuseste sa inteleaga.

     + `understood` : se primeste atunci cand query ul reuseste sa determine macar o conditie, iar API ul nu a dat fail(sau pur cheia de la api nu este prezenta si modelul ruleaza 100% local), se face trierea mai departe...
     + `partial` : se primeste atunci cand query ul reuseste sa determine macar o conditie, iar API ul returneaza o eroare(pe scurt, localul a gasit ceva, iar ce a rams ptr API a ramas neadresat de catre API, iar modelul brute-force a incercat sa echivaleze, dar nu e nicio garantie ca tot textul a fost inteles), se face trierea mai departe...
     + `failed` : nu s-a determinat nicio condiție (nici obiectivă, nici interpretabilă), așa că nu returnăm nicio firmă, pentru că nu avem pe ce să ne bazăm.


 #### Dublarea conditiilor

 - LLM ul poate sa genereze informatie din context si astfel poate genera informatie ptr campuri deja adresate de modelul local.(exemplu poate sa considere ca "startup" ofera informatia year_founded => 2019 si acolo se afla o contradictie).
- Se pune problema pe care dintre ele sa le ascultam? Conteaza foarte mult de toleranta dar in contextul unei codari astfel de stricte, daca modelul capteaza informatii local de cele mai multe ori sunt sigure deci putem sa ne bazam pe o toleranta marita
  - `Rezolvare`: dacă modelul local a completat deja un câmp obiectiv (an, angajați, venit, public), API-ul nu îl mai suprascrie. Pentru restul, API-ul adaugă informația captată.

#### Geografia functioneaza mai optim in local
- Soluția locală merge bine pentru țări și regiuni scrise clar, pentru că adaugă și orașele (România → Brașov, București, Iași...), pe când API-ul lasă doar țara.
- Expansiunea geografică acum rulează mereu în local. Până acum nu era chiar așa în modul normal, doar API-ul era îmbogățit cu orașe din dicționar
  - `Rezolvare` : Apelam mereu expansiunea geografica(locala) la inceputul fazelor chiar daca cheia API este prezenta in.env iar la description in brute-force filtram cuvitnele care au facut deja match la geografie.

#### Confuzia de roluri in Brute-Force
- Modelul nu face diferenta intre ce trebuie sa **fie** firma si ce **livreaza** firma dintr-un query
  - `Rezolvare` : In Brute-Force cautam mereu cuvinte precum "for" ca sa mapam corect in traget_markets(ce livreaza firma) nu in business_model(ce este firma)


## Erori in implementarea solutiilor
 - Am incercat sa scad limita de timeout din program la sub 8 secunde, dar minimul google e de 10 secunde 
- AI ul local face foarte multe gafe cand vine vorba de intelegerea unor anumite cuvinte (ex :IT, 3D, AI) pentru ca baza de date a keywords urilor este destul de restransa

##  Solutia automatizata:
 - Pentru a completa toata lista si a ne asigura ca avem cat mai multe keywords de selectie am cerut de la un LLM sa imi genereze 200 (in 2 etape) de query uri diferite care sa testeze diferite aspecte si formulari (unele mai vagi altele mai clare si mai usor de dedus)
 - Dupa asta am rulat greping-ul LOCAL (fara vreun fel de API call) si am trimis rezultatele unui LLM care sa extraga exact cuvintele care nu au aparut in keywords-uri pentru a largi orizonturile agentului local.

Dupa cateva teste si incercari sa a ajuns la un model rapid si complex care reuseste sa imparta text in informatii punctuale despre firme

Urmatoarea etapa: testarea totala, local + API si validarea datelor expuse.

### Rezultate finale etapa de Query divizion:
- Modelul rulează și fără cheie API (brute-mode) și a produs condiții pentru toate cele 12 query-uri. Cu API-ul, când apelul eșuează (503, 429, 504), sistemul trece automat pe varianta locală: în rularea cu 207 de query-uri, au fost 148 de astfel de cazuri, toate prinse.(cifre luate din `assets/stage1_v0/STATS.md`)
- Model **RAPID** pentru agentul local (2 - 3 milisecunde), iar cu API call ~ 1 - 2 secunde
- Capteaza cat mai multa informatie, o fragmenteaza si o tipizeaza ca sa poata fi folosita dupa la compararea cu firmele din baza de date a firmelor.  

# Etapa 2 : Trierea

### Planificarea:
- Trierea se va face pe baza datelor total **OBIECTIVE** pe care le am descoperit in etapa anterioara (cum ar fi un regex despre venit sau un numar de angajati minim)
 - Vom aplica aici principiul 100% **BENEFIT OF THE DOUBT**, deci daca un astfel de camp obiectiv lipseste din compania din baza de date atunci ii oferim beneficiul de a se incadra la "candidat cu potential"
- Campul de adresa necesita niste mici abordari pentru ca este un criteriu de triere extraordinar de bun, dar necesita niste imbunatatiri pentru a deveni optim pe nivel Local.  
- Dupa asta vom aplica pe cele care au potential de companii posibile un criteriu de notare si le vom compara pe fiecare in parte.
- Informatiile de aici sunt comparate **SUBIECTIV** deci fiecare companie va primi o nota anume care va fi compusa din alte note prin relatare camp-camp
- Si aici vom impune benefit of the doubt si vom incerca sa "sapam" dupa informatii in alte campuri pentru a reusi sa deslusim informatiile lipsa carora le vom acorda la fel nota de confidence
- Se pune problema: "Oare NAICS-ul firmei este un criteriu"
### De ce eliminam(taiem) si nu le penalizam(bad scoring)
#### Avantaje :
- **Pentru a salva timp** : costul de a compara descrierile subiective ale firmelor sunt foarte costisitoare astfel noi incercam sa triem din start ce nu se potriveste din punct de vedere matematic sau logic. Cifrele si taraa sunt informatii exacte(obiective), nu pareri(subiective).
- **Scalabilitatea** : pentru o baza de date de 400 de firme costul nu e o problema asa de mare, timpul de rulare e aproape minimal, dar in cazul **SCALARII**, cand baza de date se mareste substantial, vom avea probleme mari de complexitate si orice triere logica si instanta ne va avantaja.
- **Benefit of the doubt** : firmele care au un camp obiectv lipsa vor fi adaugate in lista automat
#### Dezavantaje :
- **Greseli de intelegere a querry-ului** : Lista tarilor poate fi incompleta sau sa nu recunoasca un anumit oras sau regiune scrisa in querry.
- **Pierderea** : Dupa ce o firma este exclusa, nu mai poate fi readusa in baza de selectie.
- **Greseli de baza de date** : Detaliile din baza de date sunt noisy asa ca filtrul hard trebuie sa aiba o relativa toleranta la noise. Momentan toleranta la noise este 0, dar e o imbunatatire pe viitor.

Am ales aceasta decizie pentru ca am acceptat riscul de a pierde firme pe baza adreselor (nu are ce cauta clar o firma din India in Romania) iar scoring ul cred ca nu e sufucient de deterministic pentru aceste campuri care sunt indisputabil **obiective**(precum numarul de angajati sau venitul mediu), cu toate ca se pot pierde firme aproximativ potrivite pentru acel query.




## Trierea Hard : <br> Idei de implementare(cu + si -)
### Implementarea on the fly(greedy)

Se deschide baza de date a firmelor si se trece prin fiecare in parte. Cand ajungem la firma i vom compara criteriile obiective, daca se potriveste atunci ii vom oferi o nota in functie de restul criteriilor si daca are cea mai mare nota o memoram. La final vom face un top 20 de firme care se potrivesc deci vom trece iar prin baza de date pentru a verifica candidatii si a-i sorta.

- "+" este foarte rapida si practic ajunge sa gaseasca cea mai buna firma (care se potriveste dupa ce au gasit agentii locali si LLM, evident)
- "+" nu ocupa foarte multa memorie ram pentru ca maximul care este incarcat este de 20 de firme la final dupa sortare
- "-" nu putem face troubleshooting peste firmele din baza de date si strica putin ideea de a verifica cum gandeste sistemul de acreditare
- "-" daca baza de date detine milioane de firme atunci sa faci un top 20 atunci ar trebui sa se treaca de 2 ori prin milioanele de firme ceea ce ar ingreuna foarte tare un sistem de calcul.

### Implementarea Batching:

Se deschide baza de date a firmelor si se trece prin fiecare in parte. Cand ajungem la firma i vom compara criteriile obiective, daca se potricveste atunci o vom scrie intr un fisier temporar care memoreaza firmele care completeaza regex-urile. apoi parcurgem lista aceea nou formata si le dam note firmelor. Le sortam si apoi alegem top 20
- "+" prin aceasta metoda putem sa omitem dublurile din baza de date ca sa nu trebuiasca sa scoram de 2 sau mai multe ori aceleasi companii
- "+" putem vedea in timp real cum decide AI ul sa aleaga firmele si ce criterii a gasit el corecte sau gresite
- "+" avem un log al firmelor care totusi au trecut de trierea HARD care totusi e considerata obiectiva, deci putem relua cautarile in cazul in care rezultatele sunt incorecte
- "-" rescrierea in batch ocupa spatiu pe disk, asta nu e o problema cand e vorba de 10.000 de firme dar daca ajungem la ordinul milioanelor atunci poate deveni o problema pentru viteza si pentru spatiul de stocare(scenariu putin ireal pentru ca in viata reala nu s ar intampla ceva de genul, si chiar daca s ar intampla niciun sistem de cautare al firmelor nu ar fi prea rapid)
- "-" viteza si costul acestui sistem este foarte variat si tine clar de cat de mult reuseste query ul sa trieze HARD baza de date pentru ca poate face o reducere mare (de la milioane de firme la zeci de mii) cu suficient de multe informatii hard

---
Tinand cont ca momentan proiectul este in stagiul de dezvoltare e nevoie neaparat de un environment de debugging asa ca alegerea este clara in `Implementarea Batching`.

#### Rezultate dupa implementare 
Trierea HARD rulează pe cele 12 query-uri și produce câte un fișier de candidați pentru fiecare. Fiecare query a păstrat cel puțin o firmă.(in medie fiecare are cam 30 - 40 posibili candidati, verificati)(date luate din `assets/Hard_knockout.png`)

# Etapa 3 : Scoring-ul

## Idei generale:
Acum ca pentru fiecare query se genereaza un set de companii posibile a venit momentul sa incerc sa vad cum as putea implementa tehnica de notare si de clasificare a acestor companii.

Pentru inceput a trebuit sa fac o analiza asupra firmelor care au trecut de filtru si am inceput sa imi notez ce detalii am observat, ce trade-off uri ar trebui sa implementez in model si cum sa abordez tehnica.

## Problema : Query predominant semantic

- Cele mai multe querry uri functioneaza fara a oferi suficient de multe informatii in legatura cu veniturile firmelor si cu anul de infiintare samd. Astfel trierea actuala nu face nicio reductie in numarul firmelor, deci scoring-ul ramane la fel de parca nu am facut nicio procesare. ex: "Companies that manufacture or supply critical components for electric vehicle battery production" (`assets/Hard_knockout.png`, candidate_q12.jsonl)
- `Problema` : Pentru o lista de 500 de firme nu ar trebui sa fie un cost de timp asa de mare scorarea lor, dar daca lista ajunge la un prag de ordinul milioanelor de firme, procesarea aceasta este lunga si de cele mai multe ori destul de overkill, asa ca trebuie cumva sa ne folosim si de nisa de lucru a firmei cu care lucram, pentru a reusi sa pastram o viteza de executie care sa nu limiteze utilizatorii. Precizarea este: un singur query nu ar trebui sa puna probleme, dar mai multe query uri ar ingreuna un server si ar face user experience-ul un cosmar.
  - `Rezolvare` : Trebuie introdus un mod de a compara NAICS-urile, pentru ca ne ofera o baza solida despre modul de operare al unei firme si cum functioneaza ea, iar acest NAICS sa fie un criteriu hard de triere.

## Idee de implementare :
- La apelul API ului si al agentului local, se va incerca generarea unei liste de posibile(si foarte indulgente pentru ca NAICS-urile) de NAICS-uri (sau prefixe de NAICS-uri) care sa functioneze ca un nou criteriu de preselectie.
- Alegem ca NAICS-urile sa fie indulgente pentru ca acestea au aceeasi capacitate ca adresele de a se **MOSTENI** (exemplu : "Pharmaceutical companies in Switzerland" nu face parte doar din sectorul de retail, face parte si din sectorul de manufacturing, subsectorul "pharmaceuticals and medical manufacturing", deci o firma care e descrisa de cateva cuvinte poate aparea in mai multe sectoare, respectiv subsectoare ale unui sector) 
- Dupa aceasta triere, vom incepe sa calificam firmele pe baza a ce date contin(!=null) si cat de relevante sunt cu datele pe care query ul nostru l a retinut.
- Problema apare atunci cand acest NAICS este gresit in baza de date a firmelor(din cauze birocratice sau de introducere manuala), sau chiar din cauza modului de calculare gresit al API-ului sau agentului local, astfel avem nevoie de un backup care sa nu pedepseasca capital toate firmele care nu se potrivesc cu NAICS-ul.
### Implementare nou criteriu HARD:
- Se va verifica daca vreun NAICS din query se potriveste cu NAICS-ul din baza de date.
  - Daca se potriveste, il adaugam in lista de poisibili candidati
  - Daca NAICS-ul din baza de date lipseste sau nu se potriveste cu cel din query trecem la urmatoarea etapa si anume verificam daca din campurile `core_offerings` si `business_model` ale query ului se potrives cu ceva din descrierea firmei prin metoda **TOKEN INTERSECTION**(Jaccard Index pe siruri de cuvinte normalizate) care calculeaza un scor intre intre 0 si 1 si il comparam cu un prag de toleranta flexibil.
    - Daca trece pragul de toleranta si se regasesc astfel de cuvinte in descriere inseamna ca acea companie poate fi un candidat corect
    - Daca nu trece pragul atunci firma este respinsa total.

- Pragul de toleranta va fi unul dinamic si adaptiv, pentru ca din testele pe care le am rulat, atunci cand query ul capteaza suficiente informatii in core_offerings, daca hardcodam pragul e posibil sa fie incorect si injust fata de unele firme si sa devina prea permisim, iar la celalalt capat al balantei, putem astfel sa devenim prea robusti si rigizi si sa respingem degeaba firme care isi pot face prezenta in lista potentiala de firme, astfel am stabilit un prag adaptiv care este limitat in intervalul [0.05, 0.25] si calculul ei se face in functie de cate date contine descrierea si cate date memoreaza core_offerings-urile query ului
- `Concluzie` : Aici se face un trade off in detrimentul acuratetei pentru ca se introduce in joc o noua variabila care poate sa destabilizeze si sa alunge o companie posibil ca si candidat, dar castiga o viteza extrem de importanta la scalare care poate face user experience-ul sa se simta mult mai placut. 

#### Rezultate:
 - NAICS ca prim criteriu, apoi potrivirea de cuvinte cu prag adaptiv, iar firmele fara date in descriere trec(benefit of the doubt)
 - In total 2567 → 676 firme (−74%), iar la cele trei query-uri semantice, care înainte lăsau toate cele 477 de firme, acum rămân 58, 66 și 76(sursa : `assets/runs/test_better_naics`)
 - Ce merge : farma în Elveția, 34 de firme, toate de farma;
 - Ce **NU** merge : logistica în România, unde intră și Rompetrol și OMV, pe lângă CFR, Portul Constanța și Poșta Română.
Cauzele reale (le-am verificat): un singur cuvânt generic („process“) lasă să treacă firme de software la „food în Franța“, prefixe NAICS prea largi (3359, „45“) lasă firme fără legătură, iar „e un distribuitor de petrol logistică?“ nu are răspuns clar.
 - Idei viitoare de imbunatatiri: query ul si compania sa aiba cel puțin 2 cuvinte comune, să se trateze cuvintele generice ca slabe, să se dedubleze (44 din 676 de rânduri se repetă). Decizia finală o ia scoring-ul.
 - **SOLVED BUG** : potrivirea cuvintelor producea un bug de identificare semantica("it" era gasit in interiorul cuvantului "with"), dupa masurarea listelor gresite am reusit sa identific si sa repar.

Prin acest update, am transformat un filtru care lăsa să treacă totul pe bază semantică într-un pre-motor de căutare extrem de fin, capabil să facă diferența între intenția de afacere și modelul operațional. Acum, coșul restrâns și hiper-revelant de candidați poate fi trimis către **Etapa de Scoring**.

## SCORING-UL :

Etapa de scoring se bazeaza pe oferirea recompenselor firmelor care contin campuri relevante cu query ul si penalizarea celor care au campuri lipsa sau irelevante.


Dupa o analiza a situatiei actuale si a bazei de date a firmelor ramase candidate pentru query uri am observat cateva lucruri:

### Observatii:
 - acum fiecare firma are trecute filtrele HARD, dar ele trebuie sa fie apreciate, asa ca trebuie sa penalizam companiile care au trecut `null` in campurile de filtrare hard

 - Firmele care mi au atras cel mai mult atentia (adica trebuie notate cel mai bine) au fost cele care aveau in `core_offerings`, `description` si `target_markets`.

 - Companiile care aveau match perfect de NAICS au avut avantaje fata de celelalte companii care n au dat match pe NAICS

 - Avataj au mai avut si firmele care prezentau anumite key_words in toate campurile existente, (`primary_naics:label`, `core_offerings`, `description`)

 ### Decizii importate care trebuie luate:
- Metoda de scorare trebuie aleasa in asa fel incat sa functioneze pe oricate companii selectate, oricate date contine query si sa returneze un scor normalizat, pentru a putea compara **CORECT** firmele intre ele.
- Modul in care impartim nota finala (principiul ponderilor) va trebui sa fie **fine-tuned** din simplul motiv ca unele criterii mai putin importante sa combata scorarea unor firme care au reusit sa indeplineasca criterii mai importante. 
- Propun construirea unui soi de sandbox in care sa incercam diferite valori pentru a ne fi mai usor procesul de fine-tuning al acestor valori, in cadrul careia sa implementam si metode telemetrice pentru vizualizarea erorilor.

### Idee de implementare initiala:

- Sistemul de scorare va fi impartit in 5 etape fiecare cu punctajul ei(insumate = 100p)
   - `Notarea semantica`: 60p (relevanta core_offerings, description, target_markets)
   - `NAICS mathcing`: 20p
   - `Matching-ul pe date obiective`: 10p
   - `Coerenta si consecventa` : 10 p
---
### Notarea Semantica
- Se va baza in principiu pe compararea a ce detine query ul si a ce detine o companie oarecare din baza de date calificata.
- Modul de comparare va fi bazat pe procentul de potrivire dintre query si campurile companiei: **MENTIUNE** :
  - trebuie sa fim constienti de faptul ca pot aparea typing mismatches(query : "Pharmaceuticals", Company: "Pharmaceutical"), sau comparatii contextuale, care trebuie toate luate in considerare, pentru a evita edge-case urile.
  - trebuie sa avem grija la cum comparam descrierile pentru ca de multe ori trebuie comparat **CONTEXTUAL**, astfel trebuie sa folosim niste metode subiective de acordare a notei finale.
  - trebuie sa avem in vedere ce campuri au fost generate de query si mai mult decat atat trebuie sa avem in vedere ce campuri poate sa genereze si LLM ul si agentul local(e incorect sa incercam sa comparam companiile intre ele bazat pe `target_markets` sa zicem daca agentul nostru local nici macar nu poate scrie acolo ceva)
  - trebuie sa avem in vedere cazurile in care le lipsesc firmelor campurile acestea 3 despre care am vorbit si cum taxam firmele respective.
- Campurile vor fi cotate deiferit, iar propunerea incipienta a AI-ului a fost ca:
   - `core_offerings` : 30p (daca are 100% din ce contine si query ul, primeste 30p)
   - `description` : 15p
   - `target_markets` : 15p

- Alegerea acestor numere a fost facuta pentru cazurile in care firmelor le lipseste NAICS-ul(sau e gresit), dar ele pot avea un head-start in fata celorlalte pentru ca au demonstrat prin descriere si date subiective ca sunt suficient de apte pentru a candida.

### NAICS matching :
- Compararea directa cu lista de NAICS-uri ale query ului:
   - `MATCH` = 20p
   - `NOT MATCH` = 0p

- Daca o companie nu reuseste sa faca destule puncte din datele subiective(exista un mismatch pe datele query ului), ea nu va fi cotata prost daca are acest NAICS pentru ca va avea destul de multe puncte peste firmele care nu au restul de date relevante(ex: O companie care a nimerit un NAICS vag din întâmplare (20 pct) va fi distrusă în clasament de o companie care nu are NAICS deloc, dar are o descriere 1-la-1 cu query-ul (60 pct))

### Matching-ul pe date obiective
- Verificam daca (si cate) campuri obiective bifeaza compania noastra in raport cu ce detine query-ul si facem un procentaj. **MENTIUNE**:
   - trebuie sa avem in vedere cate campuri fantoma si cate campuri REALE a reusit sa detecteze agentul in query, pentru a putea face o idee de cate campuri ar trebui sa detina "compania perfecta"
   - penalizarea trebuie sa fie in raport cu cate date obiective are query ul si cate campuri lipsa are firma de notat

- Notarea:
   - `toate campurile obiective prezente` : 10p
   - `Niciun camp obiectiv prezent` : 0p

### Coerenta si consecventa:
- Tokenii firmei trebuie cautati (**MENTIUNE** : SEMANTIC, deci subiectiv si contextual) in 3 campuri diferite ale companiei si anume : `NAICS_LABEL`, `core_offerings`, `description`
- Daca gasim aceasta coerenta in datele firmelor, in raport cu ce se afla in query, trebuie sa oferim un total de 10p.
---
La final toate aceste valori vor fi adunate si clasate si notate(folosind indecsii fiecarei companii si nota lor), iar folosind o sortare aferenta de complexitate O(logn) vom reusi sa deducem primele k firme care au cea mai mare nota si le vom afisa in radacina proiectului intr-un fisier: `Topk.jsonl`

### Telemetria:

Am construit o metoda care sa ne ofere informatiile in legatura cu ce recompense a primit fiecare companie pe fiecare camp al scoring-ului, astfel incat sa putem sa identificam erori in logica sau de calcul.

---
### Rezultate dupa telementrie:
- **Ce merge**:
   - NAICS-ul functioneaza ca un criteriu foarte bun de departajare.
     - **EXEMPLU**: pentru query-ul: "Food and beverage manufacturers in France" toate firmele de mâncare și băuturi sunt ≥41, iar cele 6 firme fără legătură (Virtualia, Sun RH, European Pay, quarksUp...) sunt ≤21. NAICS-ul face diferența.

  - Filarea industriilor se face corect
    - **EXEMPLU**: pt query-ul: "Public software companies with more than 1,000 employees." cele 15 firme tăiate de filtrul de industrie sunt toate corect tăiate (construcții, farma, retail). Nu se văd pierderi.

  - Telemetria pe componente e exact ce trebuia, fiindcă din ea văd de ce primește fiecare firmă scorul.

- **Ce NU merge**: 
   - Scoruri nenormalizate și "plafonul de sticlă"
     - **PROBLEMA**: Scorul maxim se bloca adesea pe la 75 de puncte. De ce? Pentru că dacă un query nu cerea explicit o "piață țintă" (target markets), bugetul alocat acelui câmp (15p) se pierdea complet. Mai mult, datele obiective (ex. numărul de angajați) acordau 10 puncte din oficiu tuturor firmelor care treceau de filtrul hard, devenind un bonus inutil, generalizat, în loc să departajeze candidații. Practic, scorurile nu mai erau comparabile între diferite query-uri.
     - **Cum am rezolvat**: Am implementat o normalizare matematică dinamică. Acum, scorul brut se raportează strict la bugetul de criterii efectiv activate de query (dacă nu cere piață țintă, se împarte la bugetul rămas). Cât despre datele obiective, le-am transformat dintr-un bonus într-o penalizare: nu mai premiem firma pentru că există, ci o depunctăm proporțional doar dacă îi lipsesc datele esențiale cerute.

  - Egalități arbitrare la coada clasamentului
     - **PROBLEMA**: Sistemul genera blocuri întregi de companii cu scoruri perfect identice (grupuri de 5-7 firme cu scor fix 40.0 sau 71.0). Asta se întâmpla pentru că punctajul creștea în trepte fixe. Când aveai punctaj egal, departajarea finală se făcea total arbitrar, în funcție de ordinea în care firmele erau citite din baza de date.
     - **Cum am rezolvat**: Am "spart" aceste egalități transformând scorul într-o valoare continuă, cu zecimale. Am introdus un mecanism de Term Frequency (TF) și un Bonus de Densitate. Acum, dacă o firmă are profilul mai bogat și folosește termenii cheie de mai multe ori, primește fracțiuni de puncte în plus (ex. +0.05 per token). Ca plasă de siguranță finală, am adăugat și sortarea alfabetică.
     - **Idee de implementare pe viitor**: daca o companie abuzeaza in descriere de acelasi cuvant de exemplu : "Pharma ,Pharma ,Pharma ,Pharma ,Pharma" atunci va fi cotat ca bun deci practic trebuie introdus un sistem de anticheat
  - Umplerea artificială a listelor Top-K
     - **PROBLEMA**: Lista nu știa să se oprească la timp. Dacă pentru un query aveam doar 3 candidați cu adevărat relevanți, sistemul trăgea de la coada clasamentului firme slabe doar ca să livreze fișierul complet de 20 de firme.
     - **Cum am rezolvat**: Am introdus Dynamic Thresholding (Tăiere Dinamică). Pe lângă un prag minim de bun-simț, sistemul evaluează acum scorul liderului și elimină fără milă orice companie care cade sub un anumit procent (50%-65%) din performanța acestuia. Așa, dacă un query are doar 3 rezultate excelente, lista se oprește natural la 3.

  - Redundanța criteriului de Coerență
     - **PROBLEMA**: Vechiul sistem acorda un bonus de "coerență" dacă termenii cheie apăreau în mai multe câmpuri simultan (NAICS, oferte, descriere). În practică, asta doar dubla punctajul obținut la secțiunea semantică, fără să aducă vreo informație sau valoare nouă.
     - **Cum am rezolvat**: Am șters complet acest bonus și l-am înlocuit cu o penalizare mult mai utilă: NAICS Mismatch Penalty. Dacă o companie are un cod NAICS oficial clar definit, dar acesta contrazice flagrant industria cerută de query, aplicăm o penalizare chirurgicală (-15.0 puncte). Asta elimină rapid "intrușii" din clasament.

# FINAL

Proiectul functioneaza, returneaza firme pe care le am verificat manual sa vad daca sunt bune, dar proiectul este departe de a fi gata pentru ca momentan modul de ordonare a datelor este haotic iar afisarea lor este la fel un user displeasure.

## Etapele de "curatare" are repository-ului
1. Cand rulam aplicatia se vrea ca in consola se se afiseze exact top-ul companiilor si doar asta, iar datele vor fi salvate in `results/$datetime/`:
 - `log.txt`: va afisa tot ce a fost inteles de catre agentul local si de catre LLM, dar si ce eroare a primit acest LLM.
 - `top.txt`: va afisa query ul si topul(exact ce se va afisa si in consola)
 - `company_lists/`: un director in care se vor salva toate topurile tuturor query-urilor trimise in proces, sub forma de jsonl-uri
 - `query_list.jsonl`: un fisier in care se vor scrie toate query-urile cu toate datele care au fost captate(vechiul `assets/runs/`)
 - `telemetry_list/`: un director in care se vor salva toate datele despre notarea firmelor
