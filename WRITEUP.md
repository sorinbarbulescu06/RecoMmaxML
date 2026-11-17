# Project Inception

The starting point matters a lot, so everything must be established right from the beginning.
I propose building an application that breaks down the query into multiple subunits to be tested individually, alongside building a unique rewarding system for each company in the database.

## Specific Problems:
### PROBLEM 1 - Mismatch between query and database
- The data in the query aims to search for something, but under a different name, or simply no data pinpoint was provided (for example, the query says: "logistics company in Balkans or Romania", while in the database I have a company available in Brasov).

- Confirming the problem: After analyzing the database using Gemini, I noticed that the data is indeed saved in a non-general way. Therefore, a so-called "normalization method" must be implemented so the database and the query speak the same language.

### PROBLEM 2 - "Free-text" fields

- The database records have fields that only need to be **READ**. A company might objectively be in Brasov, and if the query says Balkans, Europe, or Romania, it still remains in Brasov. Or whether a company is public or not, that's a fixed fact. However, there are fields written by a human that must be **UNDERSTOOD**—a description or an objective, which is subjective, varies greatly depending on who writes it, and that description must be consciously understood.

### PROBLEM 3 - Missing fields in the database

- The database records have fields that contain no information. The problem arises when a query intentionally asks for that information. What should the LLM do here? Completely void the company or give it the "benefit of the doubt"? And in that case, how lenient should it be with this concept?

- A decision must be made regarding the level of leniency (tolerance): if data is missing and you are strict, you lose companies that would have been a good fit. If you are lenient, you add companies that don't match.

- Special mention: If the query doesn't mention the address or the number of employees, for instance, the "benefit of the doubt" idea drops for that respective field; it becomes an unimportant field.

### PROBLEM 4 - Trade-off (speed vs accuracy vs cost)

- The agent must have a trade-off somewhere. The variables are:
speed, cost, and accuracy. The question is: when should the overheads for all 3 be modified? Depending on what and when.

- A call to an external agent is very useful but expensive, so it must be used, but with great care and attention to avoid wasting resources. The problem arises: for which companies/situations is the external call worth it, so that there isn't a massive compromise on cost?

## Implementation Ideas

### Query division:
We "break down" the query into separate pieces of information and see what we can pick from them.

 - How? : We break the query into conditions (**CONTEXTUAL** sequences) so we can acquire information to compare with the database through a system of: local ai and api call.
 - Why 2 AI models? : The first step looks for **SAFE** and **CLEAR** arguments that narrow the search area in the database, and for what it doesn't understand, it simply says **I DON'T KNOW**. The API call will provide context and a smarter way to read the query, in places where the local agent will struggle to cover an inconclusive case. It will also store a few key pieces of information that will help us identify suitable companies based on them.

 ### First Sorting:
 After calling the 2 models, we will receive some conclusive (AND OBJECTIVE) data that we can use to reduce the number of potential companies. Interpretable fields like the website or description will remain on pause for now.

 # Stage 1: Query Division
 We begin the work by initially building the code using object-oriented programming principles to generate a working base for the query.
 I created a package that will contain the future sortings (the local one and the API call one).
 
 Structure: I want the project to have multiple stages of condition collection to ease the final sorting, so I will start implementing these stages one by one.

 I'm starting with the API call because it's the easiest to test.

 ## Problem Solving during implementation
 #### Separation of Concerns and SSOT
 - I made a package that will act as the "main lobby" of the application. It has 2 files: 1 acts as a global dictionary (config) and the other does the initial checks: the local one (not yet implemented) and the call one. After the API call, every field returned by the LLM will be of type Condition, so we always receive a valid format (the local content can be wrong).
  - I eliminated any "hardcoded" data (magic strings). Everything environment-related (API keys, model versions) is exclusively managed from an .env file and globally validated through a unique Config class.

#### Benefit of the doubt
 - If a query does not explicitly mention an objective field (e.g., the founding year or the number of employees is not specified), the system automatically marks that field as a "phantom". Thus, at the company filtering stage, the engine will know not to penalize companies that have employee_count: null, because that field wasn't even a user requirement.

 #### Brute-Mode and Fault Tolerance
 - A failed API call will not stop the application. The error is caught (try/except), the phantom conditions are applied to the entire query, and the execution moves forward.

 - Brute-Mode: I built the system so it can run even without an API key configured in the .env. If an evaluator clones the repo and doesn't input a key, its absence is detected, the user is notified via a clear warning in the console, and processing continues strictly based on phase 1 (Local), thus implementing a Graceful Degradation of the system instead of a crash.

 #### Semantic Expansion
 - To avoid inconsistent and slow responses, phase 2 uses the Gemini API forced through a strict Pydantic schema. The LLM no longer has to guess companies; it just receives the piece of the query not understood locally (query.remainder) and breaks it down into semantic arrays.
For example, for "packaging materials", the model was instructed to do semantic expansion (it automatically adds: ['bottles', 'jars', 'tubes']), massively increasing the chances of a match on the free text from the company descriptions.

----
Now that the API call has been implemented and is functional, we must start building the local model, which will have 3 very important functions:
 
 - Searching for boolean flags: searches if the company is public or not, or remains inconclusive if it finds nothing.

 - Searching for founding year: It will look for keywords that mention the founding year, and then look for this year to form a regex.

 - Searching for quantitative metrics (revenue and employees): it will also form a regex about this data.

#### BONUS: Brute-Force Method
In case the API key does not exist in the file, the run mode will operate on a 100% local norm based on hardcoded keywords.

## Test Results 
I ran 3 tests using the 12 queries provided as an example (results are in `assets/`):
1. NoLocalJustApi - only the external call is used, and internally no decision is made.
2. LocalAndApi - both the local and the external call are used.
3. LocalNoAPI - the local call is used exclusively on Brute-Force mode to grep as much information as possible.

The results are decent, but a few errors and room for improvement can be observed.

## Problems and solutions in the current implementation:

#### Error when calling the API
 - If somehow the API returns error 503, meaning the model could not be accessed, this means the brute-force method wasn't called at all in the incipient stage. For example, for „Clean energy startups...“ the API gave 503, nothing was extracted and all 477 companies passed. Now 0 pass.
   + `Fix`: We use catch exception and if there is such an error, the brute-force mode is urgently called so as not to waste time and precious information.

 - I corrected the rule that decides if the API is still needed (I ignore punctuation and connecting words). On the 207 queries, the call rate remained 100%, because every query contains a semantic part (industry) that the local agent cannot extract. Conclusion: The API is not a "Plan B", but a necessary part of the system, and real cost savings would come from a cache or a local model for industries, not from better rules.

 #### The level of understanding of a query
 - During the run, a problem occurred where neither the api nor the local agent managed to capture any information, and because of this no sorting was done on the database. (the program considers that all companies have a chance to be compatible, even though they have no comparison information).
   - `Fix` : each query receives a status (`understood`, `partial`, `failed`) depending on what active conditions it manages to understand.

     + `understood` : is received when the query manages to determine at least one condition, and the API did not fail (or simply the api key is not present and the model runs 100% locally), the sorting moves forward...
     + `partial` : is received when the query manages to determine at least one condition, and the API returns an error (in short, the local found something, and what remained for the API was left unaddressed by the API, and the brute-force model tried to equate, but there's no guarantee all the text was understood), the sorting moves forward...
     + `failed` : no condition was determined (neither objective nor interpretable), so we return no company, because we have nothing to base it on.


 #### Duplication of conditions

 - The LLM can generate information from context and thus can generate information for fields already addressed by the local model. (e.g. it might consider that "startup" offers the information year_founded => 2019 and there lies a contradiction).
- The question is which one to listen to? It depends a lot on tolerance but in the context of such strict coding, if the model captures information locally, most of the time it is reliable, so we can rely on an increased tolerance.
  - `Fix`: if the local model has already filled an objective field (year, employees, revenue, public), the API does not overwrite it anymore. For the rest, the API adds the captured information.

#### Geography works more optimally in local
- The local solution works well for countries and regions written clearly, because it also adds the cities (Romania → Brasov, Bucharest, Iasi...), whereas the API only leaves the country.
- The geographical expansion now always runs in local. Until now it wasn't quite like that in normal mode, only the API was enriched with cities from the dictionary.
  - `Fix` : We always call the geographic expansion (local) at the beginning of the phases even if the API key is present in .env, and in the brute-force description we filter the words that have already matched geography.

#### Role confusion in Brute-Force
- The model doesn't differentiate between what the company must **be** and what the company **delivers** from a query.
  - `Fix` : In Brute-Force we always look for words like "for" to correctly map into target_markets (what the company delivers) not into business_model (what the company is).


## Errors in implementing the solutions
 - I tried to lower the timeout limit in the program to under 8 seconds, but google's minimum is 10 seconds. 
- The local AI makes a lot of blunders when it comes to understanding certain specific words (e.g. :IT, 3D, AI) because the keyword database is quite restricted.

##  The automated solution:
 - To complete the whole list and ensure we have as many selection keywords as possible I asked an LLM to generate 200 (in 2 stages) different queries for me that test different aspects and phrasings (some vaguer others clearer and easier to deduce).
 - After that I ran the LOCAL greping (without any kind of API call) and sent the results to an LLM to extract exactly the words that didn't appear in the keywords to broaden the local agent's horizons.

After a few tests and attempts, a fast and complex model was reached that manages to split text into pinpoint information about companies.

Next stage: total testing, local + API and validating the exposed data.

### Final results Query division stage:
- The model runs even without an API key (brute-mode) and produced conditions for all 12 queries. With the API, when the call fails (503, 429, 504), the system automatically switches to the local variant: in the run with 207 queries, there were 148 such cases, all caught. (figures taken from `assets/stage1_v0/STATS.md`)
- **FAST** model for the local agent (2 - 3 milliseconds), and with API call ~ 1 - 2 seconds.
- It captures as much information as possible, fragments it and typifies it so it can be used later when comparing with the companies in the company database.  

# Stage 2 : Sorting

### Planning:
- The sorting will be done based on the totally **OBJECTIVE** data we discovered in the previous stage (like a revenue regex or a minimum number of employees).
 - We will apply the 100% **BENEFIT OF THE DOUBT** principle here, so if such an objective field is missing from the company in the database then we offer it the benefit of qualifying as a "potential candidate".
- The address field requires some minor tweaks because it is an extraordinarily good sorting criterion, but it needs some improvements to become optimal at a Local level.  
- After that we will apply to those that have potential as possible companies a grading criterion and we will compare each one of them.
- The information here is compared **SUBJECTIVELY** so each company will receive a certain grade that will be composed of other grades through field-by-field relatability.
- Here too we will enforce the benefit of the doubt and we will try to "dig" for information in other fields to manage to unravel the missing information to which we will equally grant the confidence grade.
- The question arises: "Is the company's NAICS a criterion?"
### Why we eliminate (cut) and don't penalize (bad scoring)
#### Advantages :
- **To save time** : the cost of comparing subjective company descriptions is very expensive so we try to sort right from the start what doesn't fit mathematically or logically. Numbers and the country are exact information (objective), not opinions (subjective).
- **Scalability** : for a database of 400 companies the cost is not such a big issue, the running time is almost minimal, but in the case of **SCALING**, when the database increases substantially, we will have major complexity problems and any logical and instant sorting will benefit us.
- **Benefit of the doubt** : companies that are missing an objective field will be added to the list automatically.
#### Disadvantages :
- **Query understanding mistakes** : The list of countries might be incomplete or might not recognize a certain city or region written in the query.
- **The loss** : Once a company is excluded, it cannot be brought back into the selection base.
- **Database mistakes** : Details in the database are noisy so the hard filter must have a relative tolerance to noise. Currently the tolerance to noise is 0, but it's an improvement for the future (see 3.5).

I chose this decision because I accepted the risk of losing companies based on addresses (a company from India clearly has no business in Romania) and I believe the scoring is not deterministic enough for these fields that are indisputably **objective** (like the number of employees or the average revenue), even though approximately suitable companies might be lost for that query.




## Hard Sorting : <br> Implementation ideas (with + and -)
### On the fly (greedy) implementation

The company database is opened and it goes through each one of them. When we reach company i we will compare the objective criteria, if it fits then we will offer it a grade based on the rest of the criteria and if it has the highest grade we memorize it. At the end we will make a top 20 of companies that fit so we will go through the database again to check the candidates and sort them.

- "+" it is very fast and practically manages to find the best company (that fits after what the local agents and the LLM found, obviously)
- "+" it doesn't take up a lot of ram memory because the maximum that is loaded is 20 companies at the end after sorting
- "-" we cannot do troubleshooting over the companies in the database and it kinda ruins the idea of checking how the accreditation system thinks
- "-" if the database holds millions of companies then making a top 20 would mean going 2 times through the millions of companies which would highly burden a computing system.

### Batching Implementation:

The company database is opened and it goes through each one of them. When we reach company i we will compare the objective criteria, if it fits then we will write it in a temporary file that memorizes the companies that complete the regexes. then we traverse that newly formed list and give grades to the companies. We sort them and then choose the top 20
- "+" through this method we can omit duplicates from the database so we don't have to score the same companies 2 or more times
- "+" we can see in real time how the AI decides to choose companies and what criteria it found right or wrong
- "+" we have a log of the companies that still passed the HARD sorting which is after all considered objective, so we can resume searches in case the results are incorrect
- "-" rewriting in batch takes up space on the disk, this is not an issue when it comes to 10,000 companies but if we reach the order of millions then it can become an issue for speed and storage space (a somewhat unrealistic scenario because in real life something like this wouldn't happen, and even if it did no company search system would be very fast either)
- "-" the speed and cost of this system is very varied and strictly depends on how much the query manages to HARD sort the database because it can make a big reduction (from millions of companies to tens of thousands) with enough hard information

---
Considering that currently the project is in the development stage a debugging environment is absolutely needed so the choice is clearly in `Batching Implementation`.

#### Results after implementation 
HARD sorting runs on the 12 queries and produces a candidate file for each. Every query kept at least one company. (on average each has about 30 - 40 possible candidates, verified)(data taken from `assets/Hard_knockout.png`)

# Stage 3 : Scoring

## General ideas:
Now that for each query a set of possible companies is generated, the time has come to try to see how I could implement the grading and classification technique for these companies.

To begin with, I had to do an analysis on the companies that passed the filter and I started to note down what details I observed, what trade-offs I should implement in the model and how to approach the technique.

## Problem : Predominantly semantic query

- Most queries work without providing enough information regarding company revenues and the founding year, and so on. Thus, the current sorting makes no reduction in the number of companies, so the scoring remains the same as if we did no processing. e.g.: "Companies that manufacture or supply critical components for electric vehicle battery production" (`assets/Hard_knockout.png`, candidate_q12.jsonl)
- `Problem` : For a list of 500 companies it shouldn't be such a big time cost to score them, but if the list reaches a threshold of the order of millions of companies, this processing is long and most of the time quite overkill, so we must somehow also use the working niche of the company we are working with, to manage to maintain an execution speed that doesn't limit users. The specification is: a single query shouldn't cause problems, but multiple queries would burden a server and make the user experience a nightmare.
  - `Fix` : A way to compare NAICSes must be introduced, because it offers us a solid base about the operating model of a company and how it works, and this NAICS should be a hard sorting criterion.

## Implementation idea :
- At the call of the API and the local agent, an attempt will be made to generate a list of possible (and very lenient because the NAICSes) NAICSes (or NAICS prefixes) that act as a new preselection criterion.
- We choose the NAICSes to be lenient because they have the same capacity as addresses to be **INHERITED** (example: "Pharmaceutical companies in Switzerland" is not only part of the retail sector, it's also part of the manufacturing sector, the "pharmaceuticals and medical manufacturing" subsector, so a company that is described by a few words can appear in several sectors, respectively subsectors of a sector).
- After this sorting, we will start qualifying companies based on what data they contain (!=null) and how relevant they are with the data that our query retained.
- The problem arises when this NAICS is wrong in the company database (due to bureaucratic causes or manual entry), or even due to the wrong calculation method of the API or local agent, thus we need a backup that doesn't capitally punish all companies that don't match the NAICS.
### New HARD criterion implementation:
- It will be checked if any NAICS from the query matches the NAICS from the database.
  - If it matches, we add it to the list of possible candidates.
  - If the NAICS from the database is missing or doesn't match the one from the query we move to the next stage, namely we check if from the `core_offerings` and `business_model` fields of the query they match with anything in the company description through the **TOKEN INTERSECTION** method (Jaccard Index on normalized strings of words) which calculates a score between 0 and 1 and we compare it with a flexible tolerance threshold.
    - If it passes the tolerance threshold and such words are found in the description it means that company can be a correct candidate.
    - If it doesn't pass the threshold then the company is totally rejected.

- The tolerance threshold will be a dynamic and adaptive one, because from the tests I ran, when the query captures enough information in core_offerings, if we hardcode the threshold it might be incorrect and unfair to some companies and become too lenient, and at the other end of the balance, we can thus become too robust and rigid and reject for nothing companies that can make their presence in the potential list of companies, thus I established an adaptive threshold that is limited in the interval [0.05, 0.25] and its calculation is done depending on how much data the description contains and how much data the query's core_offerings memorize.
- `Conclusion` : Here a trade-off is made to the detriment of accuracy because a new variable is introduced into the game that can destabilize and drive away a company possibly as a candidate, but it gains an extremely important speed at scaling that can make the user experience feel much more pleasant.

#### Results:
 - NAICS as the first criterion, then matching words with an adaptive threshold, and companies without data in the description pass (benefit of the doubt).
 - In total 2567 → 676 companies (−74%), and at the three semantic queries, which previously let all 477 companies pass, now 58, 66 and 76 remain (source: `assets/runs/test_better_naics`)
 - What works: pharma in Switzerland, 34 companies, all pharma;
 - What **DOES NOT** work: logistics in Romania, where Rompetrol and OMV also enter, alongside CFR, Portul Constanta and Posta Romana.
The real causes (I verified them): a single generic word ("process") lets software companies pass to "food in France", NAICS prefixes that are too broad (3359, "45") let unrelated companies pass, and "is an oil distributor logistics?" doesn't have a clear answer.
 - Future improvement ideas: the query and the company should have at least 2 common words, treat generic words as weak, deduplicate (44 out of 676 rows repeat). The final decision is taken by the scoring.
 - **SOLVED BUG** : word matching produced a semantic identification bug ("it" was found inside the word "with"), after measuring the wrong lists I managed to identify and fix it.

Through this update, I transformed a filter that let everything pass on a semantic basis into an extremely fine pre-search engine, capable of distinguishing between the business intention and the operational model. Now, the narrowed and hyper-relevant basket of candidates can be sent to the **Scoring Stage**.

## THE SCORING :

The scoring stage is based on offering rewards to companies that contain fields relevant to the query and penalizing those that have missing or irrelevant fields.


After an analysis of the current situation and the database of companies remaining candidates for queries I noticed a few things:

### Observations:
 - now every company has passed the HARD filters, but they must be appreciated, so we must penalize the companies that passed `null` in the hard filtering fields.

 - The companies that caught my attention the most (meaning they must be graded the best) were the ones that had in `core_offerings`, `description` and `target_markets`.

 - Companies that had a perfect NAICS match had advantages over the other companies that didn't match on NAICS.

 - Companies that presented certain key_words in all existing fields also had an advantage, (`primary_naics:label`, `core_offerings`, `description`)

 ### Important decisions to be made:
- The scoring method must be chosen in such a way that it works on however many companies selected, however much data the query contains and returns a normalized score, to be able to **CORRECTLY** compare companies against each other.
- The way we divide the final grade (the weighting principle) will have to be **fine-tuned** for the simple reason that some less important criteria might combat the scoring of some companies that managed to fulfill more important criteria.
- I propose building some sort of sandbox where we can try different values to make our fine-tuning process of these values easier, within which we also implement telemetric methods to visualize errors.

### Initial implementation idea:

- The scoring system will be divided into 5 stages each with its points (summed = 100p)
   - `Semantic grading`: 60p (relevance core_offerings, description, target_markets)
   - `NAICS matching`: 20p
   - `Matching on objective data`: 10p
   - `Coherence and consistency` : 10 p
---
### Semantic Grading
- It will essentially be based on comparing what the query holds and what any given company from the qualified database holds.
- The comparison method will be based on the matching percentage between the query and the company's fields: **MENTION** :
  - we must be aware of the fact that typing mismatches can appear (query: "Pharmaceuticals", Company: "Pharmaceutical"), or contextual comparisons, which must all be taken into consideration, to avoid edge-cases.
  - we must be careful how we compare descriptions because many times it must be compared **CONTEXTUALLY**, thus we must use some subjective methods of granting the final grade.
  - we must keep in mind what fields were generated by the query and even more than that we must keep in mind what fields the LLM and the local agent can generate (it's incorrect to try to compare companies among themselves based on `target_markets` let's say if our local agent can't even write anything there).
  - we must consider the cases where companies are missing these 3 fields we talked about and how we tax those respective companies.
- The fields will be quoted differently, and the AI's incipient proposal was that:
   - `core_offerings` : 30p (if it has 100% of what the query contains, it receives 30p)
   - `description` : 15p
   - `target_markets` : 15p

- The choice of these numbers was made for the cases where companies are missing the NAICS (or it's wrong), but they can have a head-start over the others because they demonstrated through the description and subjective data that they are capable enough to be candidates.

### NAICS matching :
- Direct comparison with the query's list of NAICSes:
   - `MATCH` = 20p
   - `NOT MATCH` = 0p

- If a company doesn't manage to make enough points from the subjective data (there is a mismatch on the query's data), it won't be poorly quoted if it has this NAICS because it will have quite a few points over companies that don't have the rest of the relevant data (e.g.: A company that hit a vague NAICS by chance (20 pts) will be destroyed in the ranking by a company that has no NAICS at all, but has a 1-to-1 description with the query (60 pts))

### Matching on objective data
- We check if (and how many) objective fields our company ticks in relation to what the query holds and we make a percentage. **MENTION**:
   - we must consider how many phantom fields and how many REAL fields the agent managed to detect in the query, to be able to get an idea of how many fields the "perfect company" should hold.
   - the penalty must be in relation to how much objective data the query has and how many missing fields the company to be graded has.

- Grading:
   - `all objective fields present` : 10p
   - `No objective field present` : 0p

### Coherence and consistency:
- The company's tokens must be searched for (**MENTION** : SEMANTICALLY, so subjectively and contextually) in 3 different fields of the company namely : `NAICS_LABEL`, `core_offerings`, `description`
- If we find this coherence in the companies' data, in relation to what is in the query, we must offer a total of 10p.
---
In the end all these values will be added up and classified and graded (using the indices of each company and their grade), and using a corresponding O(logn) complexity sorting we will manage to deduce the first k companies that have the highest grade and we will display them in the project's root in a file: `Topk.jsonl`

### Telemetry:

I built a method to offer us the information regarding what rewards each company received on each scoring field, so that we can identify logic or calculation errors.

---
### Results after telemetry:
- **What works**:
   - The NAICS functions as a very good tie-breaking criterion.
     - **EXAMPLE**: for the query: "Food and beverage manufacturers in France" all food and beverage companies are ≥41, while the 6 unrelated companies (Virtualia, Sun RH, European Pay, quarksUp...) are ≤21. The NAICS makes the difference.

  - The filtering of industries is done correctly.
    - **EXAMPLE**: for the query: "Public software companies with more than 1,000 employees." the 15 companies cut by the industry filter are all correctly cut (construction, pharma, retail). No losses are seen.

  - The telemetry on components is exactly what was needed, because from it I see why each company receives the score.

- **What DOES NOT work**: 
   - Unnormalized scores and the "glass ceiling"
     - **PROBLEM**: The maximum score often got stuck around 75 points. Why? Because if a query didn't explicitly ask for a "target market" (target markets), the budget allocated to that field (15p) was completely lost. Moreover, the objective data (e.g. number of employees) granted 10 points by default to all companies that passed the hard filter, becoming a useless, generalized bonus, instead of separating the candidates. Basically, the scores were no longer comparable across different queries.
     - **How I fixed it**: I implemented a dynamic mathematical normalization. Now, the raw score relates strictly to the budget of criteria effectively activated by the query (if it doesn't ask for a target market, it divides by the remaining budget). As for the objective data, I transformed them from a bonus into a penalty: we no longer reward the company because it exists, but we penalize it proportionally only if it lacks the essential requested data.

  - Arbitrary ties at the bottom of the ranking
     - **PROBLEM**: The system generated entire blocks of companies with perfectly identical scores (groups of 5-7 companies with a fixed score of 40.0 or 71.0). This happened because the score increased in fixed steps. When you had an equal score, the final tie-breaking was done totally arbitrarily, depending on the order in which the companies were read from the database.
     - **How I fixed it**: I "broke" these ties by transforming the score into a continuous value, with decimals. I introduced a Term Frequency (TF) mechanism and a Density Bonus. Now, if a company has a richer profile and uses the key terms multiple times, it receives fractions of extra points (e.g. +0.05 per token). As a final safety net, I also added alphabetical sorting.
     - **Future implementation idea**: if a company abuses the same word in the description for example: "Pharma ,Pharma ,Pharma ,Pharma ,Pharma" then it will be rated as good so basically an anticheat system needs to be introduced (see 3.5).
  - Artificial filling of Top-K lists
     - **PROBLEM**: The list didn't know how to stop in time. If for a query we only had 3 truly relevant candidates, the system pulled weak companies from the bottom of the ranking just to deliver the complete file of 20 companies.
     - **How I fixed it**: I introduced Dynamic Thresholding (Dynamic Cutting). Besides a common-sense minimum threshold, the system now evaluates the leader's score and ruthlessly eliminates any company that falls below a certain percentage (50%-65%) of its performance. That way, if a query only has 3 excellent results, the list stops naturally at 3.

  - The redundancy of the Coherence criterion
     - **PROBLEM**: The old system awarded a "coherence" bonus if the key terms appeared in multiple fields simultaneously (NAICS, offerings, description). In practice, this just doubled the score obtained in the semantic section, without bringing any new information or value.
     - **How I fixed it**: I completely deleted this bonus and replaced it with a much more useful penalty: NAICS Mismatch Penalty. If a company has a clearly defined official NAICS code, but it flagrantly contradicts the industry requested by the query, we apply a surgical penalty (-15.0 points). This quickly eliminates the "intruders" from the ranking.

# FINAL

The project works, it returns companies that I manually checked to see if they are good, but the project is far from ready because currently the way data is ordered is chaotic and displaying them is also a user displeasure.

## The repository "cleaning" stages
1. When we run the application we want the exact top of the companies to be displayed in the console and only that, and the data will be saved in `results/$datetime/`:
 - `log.txt`: it will display everything that was understood by the local agent and by the LLM, but also what error this LLM received.
 - `top.txt`: it will display the query and the top (exactly what will also be displayed in the console)
 - `company_lists/`: a directory where all the tops of all the queries sent in the process will be saved, in the form of jsonls.
 - `query_list.jsonl`: a file where all the queries with all the data that was captured will be written (the old `assets/runs/`).
 - `telemetry_list/`: a directory where all the data about company grading will be saved.

 ## 3.4 Scaling
**If the system needed to handle 100,000 companies per query instead of 500, what would you change?**

In its current state, the system sequentially reads a `.jsonl` file and applies filtering and tokenization rules in memory (O(N)). For 500-2500 companies, the *Batching* approach with writing to temporary files is acceptable, but at 100,000+ companies, the disk I/O and text processing in Python would generate a huge overhead. 

To scale, I would implement the following architectural changes:
*   **Migration to Elasticsearch (ES):** I would abandon the linear traversal of the `companies.jsonl` file. Elasticsearch is built exactly for this kind of problem. The criteria from the HARD sorting (employees, revenue, location, is_public) would instantly turn into pre-calculated boolean filters.
*   **Replacing Token Intersection with BM25 / Vector Search:** The current *Jaccard Index* algorithm and the normalization of texts in Python would be replaced by native indexing from ES. For advanced scaling, I would add a vector database (e.g. Pinecone or Milvus). Instead of the LLM generating a list of keywords for *core_offerings*, I would transform the query into an *embedding* and do a semantic similarity search (K-Nearest Neighbors), dropping the response time to under 50ms per query.
*   **Asynchronous / Parallel Scoring:** For the few hundred companies that pass the database filter, the detailed scoring engine (which applies the NAICS and consumer penalties) would run distributed using a process pool (`concurrent.futures` in Python or a framework like Ray), reducing the evaluation time to a few tenths of a second.

## 3.5 Failure Modes
**When might your system produce confident but incorrect results? What would you monitor in production to detect these failures?**

The current system is robust, but there are a few scenarios (Failure Modes) where it can award an artificially high score to a wrong company:

1.  **Keyword Stuffing & TF (Term Frequency) Anomalies:**
    *   *The Problem:* Because the scoring engine offers a bonus proportional to the density and frequency of the requested tokens (to break ties), a company that does "SEO" on its own description (e.g. repeats the word *AI* 15 times) will be erroneously propelled to the top, obtaining a confident score, even though its quality is poor.
    *   *Monitoring:* I would implement an alert on the score distribution. If a company recurrently obtains maximum scores on disjoint queries, or if its *Term Frequency* bonus exceeds a statistical threshold of 3 standard deviations (Z-score > 3), the system would send an anomaly log to a dashboard (e.g. Grafana/Datadog) for manual review.

2.  **Over-expansion (Noise induced by LLM):**
    *   *The Problem:* When the LLM is asked to "semantically expand" a very specific query (e.g. *"software for deep space nanosatellites"*), it can return a list that is too generous in `value_list` (e.g. *aerospace, planes, helicopters*). Thus, the adaptive HARD sorting will let helicopter manufacturers pass, awarding them a high score because they "match" the generated expansion, but completely missing the user's strict intention.
    *   *Monitoring:* I would constantly log the edit/semantic distance between the raw query and the list of conditions generated by the LLM. If the expansion explodes in the number of tokens (e.g. from 3 tokens in the query to 50 industry tokens), the system should raise a *Semantic Drift Warning* flag.

3.  **Silent Graceful Degradation (Hidden quality degradation):**
    *   *The Problem:* If the external API returns 429 (Rate Limit) or 503 (Unavailable), the system uses `LocalConditionExtractor` in *Brute-Force* mode. From the outside, the user sees a valid and fast result, but the accuracy is much lower. If this degradation persists, trust in the system drops without the application actually "falling" (crash).
    *   *Monitoring:* I would instrument metrics based on the query status (`api_error`, `status: partial`). If the fallback rate exceeds a tolerance threshold (e.g. >5% of requests in the last 5 minutes use Brute-Force mode), the system must immediately trigger a PagerDuty incident to investigate the API quota limits.