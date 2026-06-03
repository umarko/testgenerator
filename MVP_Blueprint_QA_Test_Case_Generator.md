# MVP Blueprint: AI QA Test Case Generator

## 1. Cilj MVP-a

Cilj MVP-a je da ubrza kreiranje manualnih test case-ova za user story-je iz Azure DevOps-a.

MVP treba da omoguci QA korisniku da:

1. Unese Azure DevOps User Story ID.
2. Sistem procita user story, acceptance criteria i relevantne linkove.
3. AI generise predlog manualnih test case-ova.
4. QA pregleda, izmeni i odobri testove.
5. Sistem kreira Azure DevOps Test Case work item-e.
6. Sistem doda kreirane test case-ove u odabrani Test Plan i Test Suite.

MVP ne treba odmah da radi potpuno autonomno. U fintech okruzenju prvi stabilan oblik treba da bude QA copilot sa obaveznim human review korakom.

## 2. Problem koji resavamo

Trenutni proces manualnog kreiranja testova obicno ukljucuje:

- citanje user story-ja,
- tumacenje acceptance criteria,
- proveru dizajna,
- razmisljanje o pozitivnim, negativnim i edge scenarijima,
- pisanje test steps i expected results,
- rucni unos u test management alat.

Najveci gubitak vremena nije samo pisanje, vec ponavljanje istog misaonog procesa za svaki story. MVP treba da automatizuje prvi nacrt testova i unos u Azure DevOps, ali da QA i dalje ostane vlasnik kvaliteta.

## 3. MVP Scope

### U scope-u

- Azure DevOps autentikacija.
- Dohvatanje jednog User Story-ja po ID-u.
- Parsiranje osnovnih polja:
  - Title
  - Description
  - Acceptance Criteria
  - Area Path
  - Iteration Path
  - Tags
  - Linked work items, ako su dostupni
- Generisanje test case-ova u strukturisanom JSON formatu.
- Prikaz generisanih testova u review ekranu.
- Rucna izmena pre importa.
- Kreiranje Test Case work item-a u Azure DevOps-u.
- Dodavanje test case-a u postojeci Test Plan/Test Suite.
- Log import rezultata.

### Van scope-a za prvi MVP

- Potpuna autonomija bez QA odobrenja.
- Automatsko citanje celog Figma file-a.
- Automatsko pokretanje testova.
- Generisanje Playwright/Selenium automatizacije.
- Pokrivanje svih Azure DevOps procesa i custom template-a.
- Kompleksan permission management unutar same aplikacije.
- Full audit/compliance modul.

## 4. Predlozena arhitektura

### Komponente

1. Web UI
   - Interni ekran za QA korisnika.
   - Unos User Story ID-a.
   - Izbor Test Plan-a i Test Suite-a.
   - Review i edit generisanih test case-ova.
   - Import dugme.

2. Backend API
   - Orkestrira ceo proces.
   - Komunicira sa Azure DevOps API-jem.
   - Komunicira sa AI modelom.
   - Validira AI output.
   - Kreira test case-ove u Azure DevOps-u.

3. Azure DevOps Connector
   - Dohvata work item.
   - Dohvata linked work item-e.
   - Kreira Test Case work item.
   - Dodaje Test Case u Test Suite.

4. AI Test Generator
   - Prima normalizovan kontekst iz user story-ja.
   - Vraca strukturisan JSON.
   - Ne poziva direktno Azure DevOps.

5. Storage
   - Za MVP moze biti lokalna SQLite baza ili jednostavna server baza.
   - Cuva generisane predloge, status, import rezultat i osnovni audit trag.

## 5. Predlozeni tehnoloski stack

### Najprakticniji MVP stack

- Frontend: React + TypeScript
- Backend: Python FastAPI ili Node.js/NestJS
- Database: SQLite za lokalni MVP, PostgreSQL za timsku verziju
- AI: OpenAI API ili Azure OpenAI, u zavisnosti od kompanijskih pravila
- Integracije: Azure DevOps REST API

### Konzervativna preporuka

Ako kompanija vec koristi Microsoft/Azure ekosistem, za produkcioni pravac ima smisla:

- Azure App Service ili Azure Container Apps
- Azure OpenAI
- Microsoft Entra ID authentication
- Key Vault za tajne
- Application Insights za logove

Za prvi lokalni prototip moze se krenuti jednostavnije.

## 6. Azure DevOps pristup

### Autentikacija

Za prototip:

- Personal Access Token, ogranicenog trajanja i minimalnih prava.

Za produkciju:

- Microsoft Entra ID app registration.
- Service principal ili delegated auth.
- Token se dobija preko MSAL-a.
- Tajne se cuvaju u Key Vault-u ili secure secret store-u.

Minimalna prava:

- Read Work Items.
- Read Test Plans.
- Write Work Items.
- Manage Test Plans/Test Suites, ako aplikacija dodaje testove u suite.

### Dohvatanje User Story-ja

Primer endpoint-a:

```http
GET https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{id}?$expand=all&api-version=7.1
```

Za pretragu po kriterijumima koristi se WIQL:

```http
POST https://dev.azure.com/{organization}/{project}/_apis/wit/wiql?api-version=7.1
```

Primer WIQL query-ja:

```sql
SELECT [System.Id], [System.Title], [System.Description]
FROM WorkItems
WHERE [System.TeamProject] = @project
AND [System.WorkItemType] = 'User Story'
AND [System.Id] = 12345
```

### Kreiranje Test Case work item-a

Azure DevOps Test Case je work item tipa `Test Case`.

Primer endpoint-a:

```http
POST https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/$Test%20Case?api-version=7.1
Content-Type: application/json-patch+json
```

Primer osnovnog JSON Patch tela:

```json
[
  {
    "op": "add",
    "path": "/fields/System.Title",
    "value": "Verify successful payment creation with valid input"
  },
  {
    "op": "add",
    "path": "/fields/System.Description",
    "value": "Generated from User Story #12345"
  },
  {
    "op": "add",
    "path": "/fields/System.Tags",
    "value": "AI-generated; manual-test; payments"
  }
]
```

### Dodavanje Test Case-a u Test Suite

Primer endpoint-a:

```http
POST https://dev.azure.com/{organization}/{project}/_apis/testplan/Plans/{planId}/Suites/{suiteId}/TestCase?api-version=7.1
```

U praksi treba prvo kreirati Test Case work item, sacuvati njegov ID, pa taj ID dodati u zeljeni suite.

## 7. AI input model

Backend ne treba da salje sirov Azure DevOps response direktno u model. Prvo treba napraviti normalizovan input.

Primer:

```json
{
  "workItem": {
    "id": 12345,
    "type": "User Story",
    "title": "As a user, I want to create a domestic payment",
    "description": "...",
    "acceptanceCriteria": "...",
    "areaPath": "Payments",
    "iterationPath": "Sprint 24",
    "tags": ["payments", "mobile", "retail"]
  },
  "linkedItems": [
    {
      "id": 12346,
      "type": "Bug",
      "title": "Payment reference validation fails for max length"
    }
  ],
  "testGenerationPolicy": {
    "domain": "fintech",
    "style": "manual",
    "includePositive": true,
    "includeNegative": true,
    "includeBoundary": true,
    "includeSecurity": true,
    "includeAudit": true,
    "maxTestCases": 12
  }
}
```

## 8. AI output model

AI mora da vrati validan JSON. Backend mora da validira JSON pre prikaza i importa.

Primer output-a:

```json
{
  "sourceWorkItemId": 12345,
  "summary": "Generated manual test coverage for domestic payment creation.",
  "assumptions": [
    "User is already authenticated.",
    "User has at least one active current account."
  ],
  "questionsForBA": [
    "Should payment reference allow special characters?"
  ],
  "testCases": [
    {
      "title": "Verify domestic payment is created with valid mandatory data",
      "priority": "High",
      "category": "Positive",
      "preconditions": [
        "User is authenticated",
        "User has active account with sufficient balance"
      ],
      "steps": [
        {
          "action": "Open domestic payment form",
          "expectedResult": "Domestic payment form is displayed"
        },
        {
          "action": "Enter valid beneficiary account, amount and payment reference",
          "expectedResult": "All fields are accepted without validation errors"
        },
        {
          "action": "Submit payment",
          "expectedResult": "Payment is created and confirmation screen is displayed"
        }
      ],
      "coverage": [
        "Acceptance criterion: user can create domestic payment"
      ],
      "tags": ["payments", "positive", "manual"]
    }
  ]
}
```

## 9. Test generation pravila

Prompt za AI mora eksplicitno da trazi:

- pozitivne scenarije,
- negativne scenarije,
- boundary value testove,
- mandatory field validacije,
- role/permission scenarije,
- error handling,
- audit/logging ocekivanja,
- security/privacy provere,
- regression impact,
- pitanja za BA/PO kada story nije dovoljno jasan.

AI ne sme da izmislja poslovna pravila. Ako pravilo nije navedeno, treba da ga stavi u `assumptions` ili `questionsForBA`.

## 10. Review workflow

Predlozeni workflow:

1. QA unosi User Story ID.
2. Sistem prikazuje procitani story summary.
3. QA klikne `Generate`.
4. Sistem prikazuje generisane testove.
5. QA moze da:
   - izmeni title,
   - izmeni preconditions,
   - izmeni steps,
   - promeni priority,
   - obrise test case,
   - doda novi test case,
   - oznaci test kao smoke/regression/security.
6. QA klikne `Import to Azure DevOps`.
7. Sistem kreira test case-ove i prikazuje Azure DevOps ID-eve.

## 11. Validacije pre importa

Backend treba da proveri:

- svaki test case ima title,
- svaki test case ima bar jedan step,
- svaki step ima action i expected result,
- priority je iz dozvoljenog skupa,
- nema ociglednih duplikata,
- broj testova nije prevelik,
- Test Plan ID i Suite ID postoje,
- korisnik ima prava za import.

## 12. Minimalni ekrani

### Screen 1: Generate

Polja:

- Organization
- Project
- User Story ID
- Test Plan
- Test Suite
- Generate button

### Screen 2: Review

Sekcije:

- Story summary
- Assumptions
- Questions for BA
- Generated test cases
- Edit controls
- Import button

### Screen 3: Import Result

Prikaz:

- Created test case IDs
- Failed imports
- Error details
- Linkovi ka Azure DevOps test case-ovima

## 13. Podaci koje cuvamo

Za MVP:

```json
{
  "generationId": "uuid",
  "sourceWorkItemId": 12345,
  "createdBy": "qa.user@company.com",
  "createdAt": "2026-06-03T10:30:00Z",
  "model": "selected-model-name",
  "inputHash": "hash-of-normalized-story",
  "generatedJson": {},
  "reviewedJson": {},
  "importStatus": "Imported",
  "createdAzureTestCaseIds": [55501, 55502]
}
```

Za fintech produkciju kasnije dodati:

- audit trail promena,
- approval history,
- masking sensitive data,
- retention policy,
- role-based access.

## 14. Predlozene faze implementacije

### Faza 1: Lokalni prototip

Trajanje: 1 do 2 nedelje.

Isporuka:

- CLI ili jednostavan web ekran.
- Unos User Story ID-a.
- Dohvatanje story-ja iz Azure DevOps-a.
- Generisanje test case JSON-a.
- Cuvanje rezultata u fajl ili SQLite.

Bez importa u Azure DevOps u ovoj fazi.

### Faza 2: Review UI

Trajanje: 1 do 2 nedelje.

Isporuka:

- Web UI za pregled i izmenu testova.
- Validacija strukture.
- Export u JSON/CSV.
- Feedback loop za prompt poboljsanje.

### Faza 3: Azure DevOps import

Trajanje: 1 do 2 nedelje.

Isporuka:

- Kreiranje Test Case work item-a.
- Dodavanje u Test Suite.
- Prikaz rezultata importa.
- Error handling.

### Faza 4: Figma kontekst

Trajanje: 2 do 3 nedelje.

Isporuka:

- Citanje Figma frame linka iz story-ja.
- Ekstrakcija relevantnog UI teksta i strukture.
- Dodavanje Figma konteksta u AI prompt.
- UI-specific test scenariji.

### Faza 5: Hardened internal pilot

Trajanje: 2 do 4 nedelje.

Isporuka:

- Entra ID auth.
- Role-based access.
- Audit log.
- Secure secret management.
- Pilot sa jednim QA timom.

## 15. Rizici i mitigacije

### Rizik: AI generise netacne testove

Mitigacija:

- Obavezan QA review.
- Jasno prikazane assumptions i questions.
- Backend validacija.
- Prompt pravila protiv izmisljanja poslovnih pravila.

### Rizik: losi ili nepotpuni user story-ji

Mitigacija:

- AI generise pitanja za BA/PO.
- Score kvaliteta story-ja.
- Oznacavanje nepokrivenih acceptance criteria.

### Rizik: sensitive data u promptu

Mitigacija:

- Redakcija podataka pre slanja modelu.
- Ne slati produkcione korisnicke podatke.
- Koristiti kompanijski odobren AI provider.
- Logovati hash inputa, ne kompletan sensitive payload kada nije neophodno.

### Rizik: Azure DevOps custom polja

Mitigacija:

- Napraviti konfiguraciju mapiranja polja.
- Prvo podrzati minimum polja.
- Dodati project-specific adapter kasnije.

### Rizik: test steps format u Azure DevOps-u

Mitigacija:

- Prvo kreirati title, description i tags.
- Zatim dodati podrsku za formalne test steps.
- Testirati na sandbox projektu pre produkcije.

## 16. Definition of Done za MVP

MVP je gotov kada:

- QA moze da unese validan User Story ID.
- Sistem procita story iz Azure DevOps-a.
- Sistem generise najmanje 5 smislenih test case-ova.
- QA moze da pregleda i izmeni testove.
- Sistem moze da kreira Test Case work item-e u Azure DevOps-u.
- Sistem moze da doda test case-ove u izabrani Test Suite.
- Svaki import rezultat ima log sa created ID-evima.
- Postoji fallback kada AI output nije validan.
- Postoji dokumentovana procedura za podesavanje Azure pristupa.

## 17. Prvi konkretni sledeci koraci

1. Napraviti Azure DevOps sandbox project ili koristiti neprodukcioni project.
2. Definisati jedan reprezentativan User Story sa dobrim acceptance criteria.
3. Odluciti da li prototip koristi PAT ili Entra ID.
4. Napraviti backend funkciju `get_work_item(story_id)`.
5. Napraviti prompt i JSON schema za test generation.
6. Napraviti validaciju AI output-a.
7. Napraviti prvi review ekran.
8. Tek nakon toga dodati import u Azure DevOps.

## 18. Preporuceni MVP backlog

### Epic: Azure DevOps Integration

- Kao QA korisnik, zelim da unesem User Story ID i dobijem podatke iz Azure DevOps-a.
- Kao QA korisnik, zelim da izaberem Test Plan i Test Suite.
- Kao sistem, zelim da kreiram Test Case work item-e.
- Kao sistem, zelim da dodam kreirane test case-ove u izabrani suite.

### Epic: AI Test Generation

- Kao QA korisnik, zelim da sistem generise testove na osnovu story-ja.
- Kao QA korisnik, zelim da vidim assumptions.
- Kao QA korisnik, zelim da vidim pitanja za BA/PO.
- Kao QA korisnik, zelim da generisani testovi imaju steps i expected results.

### Epic: QA Review

- Kao QA korisnik, zelim da izmenim generisani test case pre importa.
- Kao QA korisnik, zelim da obrisem los predlog.
- Kao QA korisnik, zelim da dodam novi test case.
- Kao QA korisnik, zelim da odobrim finalnu listu za import.

### Epic: Audit and Reliability

- Kao sistem, zelim da sacuvam generation ID.
- Kao sistem, zelim da sacuvam created Azure Test Case ID-eve.
- Kao sistem, zelim da prijavim greske pri importu.
- Kao admin, zelim da znam koji story je bio izvor za svaki generisani test.

